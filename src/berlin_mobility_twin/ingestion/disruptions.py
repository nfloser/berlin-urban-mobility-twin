from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from berlin_mobility_twin.domain.models import (
    DataQuality,
    Disruption,
    DisruptionCategory,
    FreshnessStatus,
    Provenance,
    QualitySeverity,
)

BERLIN_TZ = ZoneInfo("Europe/Berlin")
SOURCE_ID = "berlin-road-disruptions"
PROVIDER = "Digitale Plattform Stadtverkehr Berlin"
DATASET_TITLE = (
    "Baustellen, Sperrungen und sonstige Störungen von besonderem verkehrlichem Interesse"
)
LICENCE = "dl-de-by-2.0"


@dataclass(frozen=True)
class DisruptionIngestionResult:
    disruptions: list[Disruption]
    rejected_features: list[dict[str, Any]]


def _parse_source_local(value: str | None) -> datetime | None:
    if value is None or value.strip() == "":
        return None
    local = datetime.strptime(value.strip(), "%d.%m.%Y %H:%M").replace(tzinfo=BERLIN_TZ)
    return local.astimezone(UTC)


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _category(subtype: str | None) -> DisruptionCategory:
    normalized = (subtype or "").strip().casefold()
    if normalized == "baustelle":
        return DisruptionCategory.CONSTRUCTION
    if normalized == "sperrung":
        return DisruptionCategory.CLOSURE
    if normalized == "gefahr":
        return DisruptionCategory.OTHER
    return DisruptionCategory.UNKNOWN


def parse_disruptions(
    payload: dict[str, Any],
    *,
    retrieved_at: datetime,
    source_url: str,
    strict: bool = True,
) -> DisruptionIngestionResult:
    """Normalise the current VIZ GeoJSON disruption schema without inferring road-edge matches."""
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    retrieved_at = retrieved_at.astimezone(UTC)
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("disruption payload must be a GeoJSON FeatureCollection")

    disruptions: list[Disruption] = []
    rejected: list[dict[str, Any]] = []
    for index, feature in enumerate(payload["features"], start=1):
        try:
            if feature.get("type") != "Feature":
                raise ValueError("not a GeoJSON Feature")
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry")
            if not isinstance(geometry, dict) or not geometry.get("type"):
                raise ValueError("missing geometry")
            disruption_id = properties.get("id")
            if not disruption_id:
                raise ValueError("missing properties.id")

            validity = properties.get("validity") or {}
            valid_from = _parse_source_local(validity.get("from"))
            valid_until = _parse_source_local(validity.get("to"))
            quality_warnings: list[str] = []
            if valid_from is None:
                quality_warnings.append("missing validity start")
            if valid_until is None:
                quality_warnings.append("missing validity end")

            stored_at = _parse_iso_utc(properties.get("tstore"))
            provenance = Provenance(
                source_id=SOURCE_ID,
                provider=PROVIDER,
                dataset_title=DATASET_TITLE,
                retrieved_at=retrieved_at,
                observation_at=stored_at,
                source_url=source_url,
                licence=LICENCE,
                freshness=FreshnessStatus.UNKNOWN,
                quality_warnings=quality_warnings,
            )
            street = str(properties.get("street") or "").strip()
            content = str(properties.get("content") or "").strip()
            description: str | None
            if street and content:
                description = f"{street}: {content}"
            else:
                description = street or content or None

            disruptions.append(
                Disruption(
                    disruption_id=str(disruption_id),
                    category=_category(properties.get("subtype")),
                    description=description,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    geometry=geometry,
                    crs="EPSG:4326",
                    affected_network_segment=None,
                    network_match_confidence=None,
                    provenance=provenance,
                    quality=DataQuality(
                        warnings=quality_warnings,
                        severity=(
                            QualitySeverity.WARNING if quality_warnings else QualitySeverity.INFO
                        ),
                    ),
                )
            )
        except (TypeError, ValueError) as exc:
            rejected.append({"feature_index": index, "reason": str(exc), "feature": feature})
            if strict:
                raise ValueError(f"invalid disruption feature {index}: {exc}") from exc

    return DisruptionIngestionResult(disruptions=disruptions, rejected_features=rejected)
