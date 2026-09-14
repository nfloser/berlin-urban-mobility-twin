from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from datetime import datetime

from berlin_mobility_twin.domain.models import (
    Disruption,
    FreshnessStatus,
    MobilitySnapshot,
    TrafficObservation,
    TransitObservation,
)


def _latest_transit(
    observations: Iterable[TransitObservation], timestamp: datetime
) -> list[TransitObservation]:
    latest: dict[tuple[str, str | None], TransitObservation] = {}
    for observation in observations:
        if observation.observed_at > timestamp:
            continue
        key = (observation.trip_id, observation.stop_id)
        current = latest.get(key)
        if current is None or observation.observed_at > current.observed_at:
            latest[key] = observation
    return sorted(latest.values(), key=lambda item: (item.trip_id, item.stop_id or ""))


def _latest_traffic(
    observations: Iterable[TrafficObservation], timestamp: datetime
) -> list[TrafficObservation]:
    latest: dict[str, TrafficObservation] = {}
    for observation in observations:
        if observation.observed_at > timestamp:
            continue
        current = latest.get(observation.detector_id)
        if current is None or observation.observed_at > current.observed_at:
            latest[observation.detector_id] = observation
    return sorted(latest.values(), key=lambda item: item.detector_id)


def _active_disruptions(disruptions: Iterable[Disruption], timestamp: datetime) -> list[Disruption]:
    active = []
    for disruption in disruptions:
        if disruption.valid_from is not None and disruption.valid_from > timestamp:
            continue
        if disruption.valid_until is not None and disruption.valid_until < timestamp:
            continue
        active.append(disruption)
    return sorted(active, key=lambda item: item.disruption_id)


def build_snapshot(
    *,
    timestamp: datetime,
    transit_observations: Iterable[TransitObservation],
    traffic_observations: Iterable[TrafficObservation],
    disruptions: Iterable[Disruption],
    source_status: Mapping[str, FreshnessStatus],
    source_errors: Mapping[str, str] | None = None,
    required_sources: Set[str] | set[str] | frozenset[str] = frozenset(),
) -> MobilitySnapshot:
    """Construct a point-in-time state using only information known by the timestamp."""
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("snapshot timestamp must be timezone-aware")
    errors = dict(source_errors or {})
    missing_sources = sorted(source for source in required_sources if source not in source_status)
    warnings = [f"source {source} is missing" for source in missing_sources]
    for source, status in sorted(source_status.items()):
        if status in (
            FreshnessStatus.STALE,
            FreshnessStatus.EXPIRED,
            FreshnessStatus.UNKNOWN,
        ):
            warnings.append(f"source {source} freshness is {status.value}")
    for source, message in sorted(errors.items()):
        warnings.append(f"source {source} failed: {message}")

    return MobilitySnapshot(
        timestamp=timestamp,
        transit=_latest_transit(transit_observations, timestamp),
        traffic=_latest_traffic(traffic_observations, timestamp),
        disruptions=_active_disruptions(disruptions, timestamp),
        source_status=dict(source_status),
        source_errors=errors,
        missing_sources=missing_sources,
        warnings=warnings,
    )
