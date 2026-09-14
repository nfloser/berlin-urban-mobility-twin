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

    for transit_observation in snapshot.transit:
        stop = stop_by_id.get(transit_observation.stop_id or "")
        states.append(
            MobilityStateRecord(
                domain=MobilityDomain.TRANSIT,
                entity_id=transit_observation.trip_id,
                location_reference=transit_observation.stop_id,
                timestamp=transit_observation.observed_at,
                geometry=_point(stop.longitude, stop.latitude) if stop is not None else None,
                observation_status=transit_observation.availability,
                provenance=transit_observation.provenance,
                freshness=transit_observation.provenance.freshness,
                quality=transit_observation.quality,
                metrics={
                    "delay_seconds": transit_observation.delay_seconds,
                    "cancelled": transit_observation.cancelled,
                },
            )
        )

    for traffic_observation in snapshot.traffic:
        detector = detector_by_id.get(traffic_observation.detector_id)
        states.append(
            MobilityStateRecord(
                domain=MobilityDomain.TRAFFIC,
                entity_id=traffic_observation.detector_id,
                location_reference=traffic_observation.detector_id,
                timestamp=traffic_observation.observed_at,
                geometry=(
                    _point(detector.longitude, detector.latitude) if detector is not None else None
                ),
                observation_status=traffic_observation.availability,
                provenance=traffic_observation.provenance,
                freshness=traffic_observation.provenance.freshness,
                quality=traffic_observation.quality,
                metrics={
                    "vehicle_count": traffic_observation.vehicle_count,
                    "heavy_vehicle_count": traffic_observation.heavy_vehicle_count,
                    "speed_kmh": traffic_observation.speed_kmh,
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
