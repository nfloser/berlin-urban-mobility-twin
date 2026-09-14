from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from berlin_mobility_twin.domain.models import (
    DataAvailability,
    Disruption,
    IntegrationMobilitySnapshot,
    MobilityDomain,
    MobilitySnapshot,
    MobilityStateRecord,
    NetworkDisruption,
    TrafficDetector,
    TransitStop,
)


def _point(longitude: float, latitude: float) -> dict[str, object]:
    return {"type": "Point", "coordinates": [longitude, latitude]}


def export_network_disruption(
    disruption: Disruption,
    *,
    timestamp: datetime,
) -> NetworkDisruption:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("integration timestamp must be timezone-aware")
    return NetworkDisruption(
        disruption_id=disruption.disruption_id,
        timestamp=timestamp,
        valid_from=disruption.valid_from,
        valid_until=disruption.valid_until,
        description=disruption.description,
        geometry=disruption.geometry,
        crs=disruption.crs,
        category=disruption.category,
        observation_status=DataAvailability.OBSERVED,
        provenance=disruption.provenance,
        freshness=disruption.provenance.freshness,
        quality=disruption.quality,
        confidence=disruption.network_match_confidence,
    )


def export_mobility_snapshot(
    snapshot: MobilitySnapshot,
    *,
    stops: Iterable[TransitStop] = (),
    detectors: Iterable[TrafficDetector] = (),
) -> IntegrationMobilitySnapshot:
    stop_by_id = {item.stop_id: item for item in stops}
    detector_by_id = {item.detector_id: item for item in detectors}
    states: list[MobilityStateRecord] = []

    for observation in snapshot.transit:
        stop = stop_by_id.get(observation.stop_id or "")
        states.append(
            MobilityStateRecord(
                domain=MobilityDomain.TRANSIT,
                entity_id=observation.trip_id,
                location_reference=observation.stop_id,
                timestamp=observation.observed_at,
                geometry=_point(stop.longitude, stop.latitude) if stop is not None else None,
                observation_status=observation.availability,
                provenance=observation.provenance,
                freshness=observation.provenance.freshness,
                quality=observation.quality,
                metrics={
                    "delay_seconds": observation.delay_seconds,
                    "cancelled": observation.cancelled,
                },
            )
        )

    for observation in snapshot.traffic:
        detector = detector_by_id.get(observation.detector_id)
        states.append(
            MobilityStateRecord(
                domain=MobilityDomain.TRAFFIC,
                entity_id=observation.detector_id,
                location_reference=observation.detector_id,
                timestamp=observation.observed_at,
                geometry=(
                    _point(detector.longitude, detector.latitude) if detector is not None else None
                ),
                observation_status=observation.availability,
                provenance=observation.provenance,
                freshness=observation.provenance.freshness,
                quality=observation.quality,
                metrics={
                    "vehicle_count": observation.vehicle_count,
                    "heavy_vehicle_count": observation.heavy_vehicle_count,
                    "speed_kmh": observation.speed_kmh,
                },
            )
        )

    return IntegrationMobilitySnapshot(
        timestamp=snapshot.timestamp,
        states=states,
        disruptions=[
            export_network_disruption(item, timestamp=snapshot.timestamp)
            for item in snapshot.disruptions
        ],
        source_status=snapshot.source_status,
        source_errors=snapshot.source_errors,
        missing_sources=snapshot.missing_sources,
        warnings=snapshot.warnings,
    )
