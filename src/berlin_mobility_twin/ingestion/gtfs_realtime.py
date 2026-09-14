from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from berlin_mobility_twin.domain.models import (
    DataAvailability,
    DataQuality,
    FreshnessStatus,
    Provenance,
    QualitySeverity,
    TransitObservation,
)

VBB_GTFS_RT_SOURCE_ID = "vbb-gtfs-rt"
VBB_GTFS_RT_PROVIDER = "Verkehrsverbund Berlin-Brandenburg GmbH"
VBB_GTFS_RT_TITLE = "VBB GTFS Realtime Feed"
VBB_GTFS_RT_LICENCE = "CC BY 4.0"
CANCELLED_RELATIONSHIP = 3


@dataclass(frozen=True)
class RealtimeFeedResult:
    observations: list[TransitObservation]
    feed_timestamp: datetime | None
    retrieved_at: datetime
    feed_age_seconds: int | None
    freshness: FreshnessStatus
    entity_count: int
    warnings: list[str] = field(default_factory=list)


def _has(message: Any, field: str) -> bool:
    try:
        return bool(message.HasField(field))
    except (AttributeError, ValueError):
        return hasattr(message, field) and getattr(message, field) not in (None, "")


def _event_value(event: Any, field: str) -> int | None:
    if event is None or not _has(event, field):
        return None
    value = int(getattr(event, field))
    if field == "time" and value <= 0:
        return None
    return value


def _feed_freshness(
    feed_timestamp: datetime | None,
    retrieved_at: datetime,
    stale_after_seconds: int,
) -> tuple[FreshnessStatus, int | None, list[str]]:
    if feed_timestamp is None:
        return FreshnessStatus.UNKNOWN, None, ["feed header has no timestamp"]
    age = int((retrieved_at - feed_timestamp).total_seconds())
    if age < -60:
        return FreshnessStatus.UNKNOWN, age, ["feed timestamp is unexpectedly in the future"]
    if age > stale_after_seconds:
        return FreshnessStatus.STALE, age, [f"feed is stale ({age}s old)"]
    return FreshnessStatus.FRESH, max(age, 0), []


def parse_feed_message(
    feed: Any,
    *,
    retrieved_at: datetime,
    source_url: str,
    stale_after_seconds: int = 120,
) -> RealtimeFeedResult:
    """Convert a decoded GTFS-RT FeedMessage into explicit realtime observations."""
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    retrieved_at = retrieved_at.astimezone(UTC)

    header = getattr(feed, "header", None)
    timestamp_value = None
    if header is not None and _has(header, "timestamp"):
        raw_timestamp = int(getattr(header, "timestamp"))
        if raw_timestamp > 0:
            timestamp_value = datetime.fromtimestamp(raw_timestamp, tz=UTC)

    freshness, feed_age, warnings = _feed_freshness(
        timestamp_value, retrieved_at, stale_after_seconds
    )
    warnings.append(
        "absence of a trip update is treated as unknown realtime coverage, not on-time service"
    )

    schema_version = getattr(header, "gtfs_realtime_version", None) if header else None
    provenance = Provenance(
        source_id=VBB_GTFS_RT_SOURCE_ID,
        provider=VBB_GTFS_RT_PROVIDER,
        dataset_title=VBB_GTFS_RT_TITLE,
        retrieved_at=retrieved_at,
        observation_at=timestamp_value,
        source_url=source_url,
        licence=VBB_GTFS_RT_LICENCE,
        schema_version=schema_version or None,
        freshness=freshness,
        quality_warnings=list(warnings),
    )

    observations: list[TransitObservation] = []
    entities = list(getattr(feed, "entity", []))
    observed_at = timestamp_value or retrieved_at
    for entity in entities:
        if not _has(entity, "trip_update"):
            continue
        update = entity.trip_update
        trip = getattr(update, "trip", None)
        trip_id = getattr(trip, "trip_id", "") if trip is not None else ""
        if not trip_id:
            continue
        relationship = int(getattr(trip, "schedule_relationship", 0) or 0)
        cancelled = relationship == CANCELLED_RELATIONSHIP
        stop_updates = list(getattr(update, "stop_time_update", []))

        if not stop_updates and cancelled:
            observations.append(
                TransitObservation(
                    trip_id=trip_id,
                    stop_id=None,
                    observed_at=observed_at,
                    cancelled=True,
                    availability=DataAvailability.REALTIME,
                    quality=DataQuality(),
                    provenance=provenance,
                )
            )
            continue

        for stop_update in stop_updates:
            arrival = getattr(stop_update, "arrival", None)
            departure = getattr(stop_update, "departure", None)
            arrival_time = _event_value(arrival, "time")
            delay = _event_value(arrival, "delay")
            if delay is None:
                delay = _event_value(departure, "delay")
            predicted_arrival = (
                datetime.fromtimestamp(arrival_time, tz=UTC) if arrival_time is not None else None
            )
            quality = DataQuality()
            if freshness is FreshnessStatus.STALE:
                quality = DataQuality(
                    warnings=["derived from stale realtime feed"],
                    severity=QualitySeverity.WARNING,
                )
            observations.append(
                TransitObservation(
                    trip_id=trip_id,
                    stop_id=getattr(stop_update, "stop_id", None) or None,
                    observed_at=observed_at,
                    predicted_arrival=predicted_arrival,
                    delay_seconds=delay,
                    cancelled=cancelled,
                    availability=DataAvailability.REALTIME,
                    quality=quality,
                    provenance=provenance,
                )
            )

    return RealtimeFeedResult(
        observations=observations,
        feed_timestamp=timestamp_value,
        retrieved_at=retrieved_at,
        feed_age_seconds=feed_age,
        freshness=freshness,
        entity_count=len(entities),
        warnings=warnings,
    )


def parse_gtfs_rt(
    payload: bytes,
    *,
    retrieved_at: datetime,
    source_url: str = "https://production.gtfsrt.vbb.de/data",
    stale_after_seconds: int = 120,
) -> RealtimeFeedResult:
    """Decode binary GTFS-Realtime data using the official Python bindings."""
    try:
        from google.transit import gtfs_realtime_pb2
    except ImportError as exc:  # pragma: no cover - exercised in installed environments
        raise RuntimeError(
            "gtfs-realtime-bindings is required to decode binary GTFS-RT payloads"
        ) from exc

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(payload)
    except Exception as exc:
        raise ValueError("invalid GTFS-Realtime protobuf payload") from exc
    return parse_feed_message(
        feed,
        retrieved_at=retrieved_at,
        source_url=source_url,
        stale_after_seconds=stale_after_seconds,
    )
