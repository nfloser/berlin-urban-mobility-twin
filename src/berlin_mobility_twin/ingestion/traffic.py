from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from io import StringIO
from typing import Any

from berlin_mobility_twin.domain.models import (
    DataAvailability,
    DataQuality,
    FreshnessStatus,
    Provenance,
    QualitySeverity,
    TrafficDetector,
    TrafficObservation,
)
from berlin_mobility_twin.processing.temporal import local_to_utc

BERLIN_TRAFFIC_PROVIDER = "Digitale Plattform Stadtverkehr Berlin"
BERLIN_TRAFFIC_LICENCE = "dl-de-by-2.0"


@dataclass(frozen=True)
class TrafficCsvSchema:
    detector_id: str
    timestamp: str
    vehicle_count: str | None
    heavy_vehicle_count: str | None
    speed_kmh: str | None
    delimiter: str = ";"
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    source_timezone: str = "Europe/Berlin"
    timestamp_fold: int | None = None

    @property
    def required_columns(self) -> set[str]:
        columns = {self.detector_id, self.timestamp}
        columns.update(
            field_name
            for field_name in (self.vehicle_count, self.heavy_vehicle_count, self.speed_kmh)
            if field_name is not None
        )
        return columns


@dataclass(frozen=True)
class RejectedTrafficRow:
    row_number: int
    raw: dict[str, str]
    reasons: list[str]


@dataclass(frozen=True)
class TrafficIngestionDiagnostics:
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    warning_count: int


@dataclass(frozen=True)
class TrafficIngestionResult:
    raw_rows: list[dict[str, str]]
    observations: list[TrafficObservation]
    rejected_rows: list[RejectedTrafficRow]
    diagnostics: TrafficIngestionDiagnostics


def _require_aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _traffic_provenance(
    *,
    retrieved_at: datetime,
    source_url: str,
    title: str,
    observation_at: datetime | None = None,
) -> Provenance:
    return Provenance(
        source_id="berlin-traffic-detectors",
        provider=BERLIN_TRAFFIC_PROVIDER,
        dataset_title=title,
        retrieved_at=_require_aware(retrieved_at, "retrieved_at"),
        observation_at=observation_at,
        source_url=source_url,
        licence=BERLIN_TRAFFIC_LICENCE,
        freshness=FreshnessStatus.UNKNOWN,
    )


def parse_detector_locations(
    payload: dict[str, Any],
    *,
    retrieved_at: datetime,
    source_url: str,
) -> list[TrafficDetector]:
    """Parse the current official TEU detector GeoJSON schema published by Berlin."""
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("detector payload must be a GeoJSON FeatureCollection")

    provenance = _traffic_provenance(
        retrieved_at=retrieved_at,
        source_url=source_url,
        title="Standorte der Verkehrsdetektion in Berlin",
    )
    detectors: list[TrafficDetector] = []
    for index, feature in enumerate(payload["features"], start=1):
        if feature.get("type") != "Feature":
            raise ValueError(f"feature {index} is not a GeoJSON Feature")
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            raise ValueError(f"feature {index} has non-Point geometry")
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError(f"feature {index} has invalid coordinates")
        detector_id = properties.get("teuID")
        if not detector_id:
            raise ValueError(f"feature {index} is missing teuID")
        operation_date = None
        if properties.get("Start of Operation"):
            operation_date = date.fromisoformat(properties["Start of Operation"])
        detectors.append(
            TrafficDetector(
                detector_id=str(detector_id),
                road=properties.get("Position") or None,
                location_description=properties.get("Location") or None,
                direction=properties.get("Direction") or None,
                lane=properties.get("Lane") or None,
                start_of_operation=operation_date,
                longitude=float(coordinates[0]),
                latitude=float(coordinates[1]),
                crs="EPSG:4326",
                provenance=provenance,
            )
        )
    return detectors


def inspect_traffic_csv_schema(payload: bytes, *, delimiter: str = ";") -> list[str]:
    """Return source headers without guessing their semantics."""
    text = payload.decode("utf-8-sig")
    reader = csv.reader(StringIO(text), delimiter=delimiter)
    try:
        return [item.strip() for item in next(reader)]
    except StopIteration:
        return []


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(float(value.replace(",", ".")))


def _parse_optional_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value.replace(",", "."))


def _parse_source_timestamp(value: str, schema: TrafficCsvSchema) -> datetime:
    naive = datetime.strptime(value, schema.timestamp_format)
    return local_to_utc(
        naive,
        schema.source_timezone,
        fold=schema.timestamp_fold,
    )


def parse_traffic_csv(
    payload: bytes,
    *,
    schema: TrafficCsvSchema,
    retrieved_at: datetime,
    source_url: str,
) -> TrafficIngestionResult:
    """Parse archived detector rows using an explicit source schema and preserve raw input."""
    retrieved_at = _require_aware(retrieved_at, "retrieved_at")
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text), delimiter=schema.delimiter)
    headers = set(reader.fieldnames or [])
    missing_columns = schema.required_columns - headers
    if missing_columns:
        raise ValueError(f"traffic CSV is missing configured columns: {sorted(missing_columns)!r}")

    raw_rows: list[dict[str, str]] = []
    observations: list[TrafficObservation] = []
    rejected_rows: list[RejectedTrafficRow] = []
    seen: set[tuple[str, datetime]] = set()
    warning_count = 0

    for row_number, source_row in enumerate(reader, start=2):
        row = {key: (value or "") for key, value in source_row.items() if key is not None}
        raw_rows.append(dict(row))
        reasons: list[str] = []
        quality_warnings: list[str] = []

        detector_id = row.get(schema.detector_id, "").strip()
        if not detector_id:
            reasons.append("missing detector id")

        observed_at: datetime | None = None
        timestamp_raw = row.get(schema.timestamp, "").strip()
        if not timestamp_raw:
            reasons.append("missing timestamp")
        else:
            try:
                observed_at = _parse_source_timestamp(timestamp_raw, schema)
            except ValueError as exc:
                reasons.append(f"invalid timestamp: {exc}")

        try:
            count = _parse_optional_int(row.get(schema.vehicle_count)) if schema.vehicle_count else None
            heavy = (
                _parse_optional_int(row.get(schema.heavy_vehicle_count))
                if schema.heavy_vehicle_count
                else None
            )
            speed = _parse_optional_float(row.get(schema.speed_kmh)) if schema.speed_kmh else None
        except ValueError:
            reasons.append("non-numeric measurement value")
            count = heavy = None
            speed = None

        if count is not None and count < 0:
            reasons.append("negative vehicle count")
        if heavy is not None and heavy < 0:
            reasons.append("negative heavy vehicle count")
        if count is not None and heavy is not None and heavy > count:
            reasons.append("heavy vehicle count exceeds vehicle count")
        if speed is not None and (speed < 0 or speed > 250):
            reasons.append("impossible speed outside 0..250 km/h")
        elif speed is not None and speed > 160:
            quality_warnings.append("suspicious speed > 160 km/h")

        if count is None:
            quality_warnings.append("missing vehicle count")
        if speed is None:
            quality_warnings.append("missing speed")
        if count is None and heavy is None and speed is None:
            reasons.append("all configured measurements are missing")

        if detector_id and observed_at is not None:
            key = (detector_id, observed_at)
            if key in seen:
                reasons.append("duplicate observation for detector and timestamp")
            elif not reasons:
                seen.add(key)

        if reasons or observed_at is None:
            rejected_rows.append(
                RejectedTrafficRow(row_number=row_number, raw=dict(row), reasons=reasons)
            )
            continue

        warning_count += len(quality_warnings)
        quality = DataQuality(
            warnings=quality_warnings,
            severity=QualitySeverity.WARNING if quality_warnings else QualitySeverity.INFO,
            is_valid=True,
        )
        provenance = _traffic_provenance(
            retrieved_at=retrieved_at,
            source_url=source_url,
            title="Verkehrsdetektion Berlin",
            observation_at=observed_at,
        )
        observations.append(
            TrafficObservation(
                detector_id=detector_id,
                observed_at=observed_at,
                vehicle_count=count,
                heavy_vehicle_count=heavy,
                speed_kmh=speed,
                availability=DataAvailability.HISTORICAL,
                quality=quality,
                provenance=provenance,
                raw=dict(row),
            )
        )

    return TrafficIngestionResult(
        raw_rows=raw_rows,
        observations=observations,
        rejected_rows=rejected_rows,
        diagnostics=TrafficIngestionDiagnostics(
            rows_read=len(raw_rows),
            rows_accepted=len(observations),
            rows_rejected=len(rejected_rows),
            warning_count=warning_count,
        ),
    )
