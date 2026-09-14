from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from berlin_mobility_twin.domain.models import (
    Disruption,
    FreshnessStatus,
    MobilitySnapshot,
    TrafficDetector,
    TrafficObservation,
    TransitObservation,
    TransitRoute,
    TransitStop,
)
from berlin_mobility_twin.processing.snapshot import build_snapshot


@dataclass
class RuntimeState:
    stops: list[TransitStop] = field(default_factory=list)
    routes: list[TransitRoute] = field(default_factory=list)
    transit_observations: list[TransitObservation] = field(default_factory=list)
    traffic_detectors: list[TrafficDetector] = field(default_factory=list)
    traffic_observations: list[TrafficObservation] = field(default_factory=list)
    disruptions: list[Disruption] = field(default_factory=list)
    source_status: dict[str, FreshnessStatus] = field(default_factory=dict)
    required_sources: set[str] = field(
        default_factory=lambda: {
            "vbb-gtfs-static",
            "vbb-gtfs-rt",
            "berlin-traffic-detectors",
            "berlin-road-disruptions",
        }
    )

    def snapshot(self, timestamp: datetime | None = None) -> MobilitySnapshot:
        moment = timestamp or datetime.now(UTC)
        return build_snapshot(
            timestamp=moment,
            transit_observations=self.transit_observations,
            traffic_observations=self.traffic_observations,
            disruptions=self.disruptions,
            source_status=self.source_status,
            required_sources=self.required_sources,
        )
