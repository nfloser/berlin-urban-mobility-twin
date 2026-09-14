from __future__ import annotations

from datetime import datetime

from berlin_mobility_twin.domain.models import (
    DataAvailability,
    Disruption,
    IntegrationMobilitySnapshot,
    MobilitySnapshot,
    NetworkDisruption,
)


def export_mobility_snapshot(snapshot: MobilitySnapshot) -> IntegrationMobilitySnapshot:
    return IntegrationMobilitySnapshot(snapshot=snapshot)


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
