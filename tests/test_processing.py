from datetime import UTC, datetime

import pytest

from berlin_mobility_twin.domain.models import (
    DataAvailability,
    DataQuality,
    Disruption,
    DisruptionCategory,
    FreshnessStatus,
    Provenance,
    TrafficObservation,
)
from berlin_mobility_twin.processing.snapshot import build_snapshot
from berlin_mobility_twin.processing.spatial import distance_meters
from berlin_mobility_twin.processing.temporal import (
    AmbiguousLocalTime,
    NonexistentLocalTime,
    local_to_utc,
)


def provenance(at: datetime) -> Provenance:
    return Provenance(
        source_id="test",
        provider="test",
        dataset_title="test",
        retrieved_at=at,
        observation_at=at,
        source_url="https://example.test",
        licence="test",
        freshness=FreshnessStatus.FRESH,
    )


def traffic(detector: str, at: datetime, count: int) -> TrafficObservation:
    return TrafficObservation(
        detector_id=detector,
        observed_at=at,
        vehicle_count=count,
        availability=DataAvailability.OBSERVED,
        quality=DataQuality(),
        provenance=provenance(at),
    )


def test_dst_spring_gap_is_not_silently_interpreted() -> None:
    naive = datetime(2026, 3, 29, 2, 30)
    with pytest.raises(NonexistentLocalTime):
        local_to_utc(naive, "Europe/Berlin")


def test_dst_autumn_overlap_requires_explicit_fold() -> None:
    naive = datetime(2026, 10, 25, 2, 30)
    with pytest.raises(AmbiguousLocalTime):
        local_to_utc(naive, "Europe/Berlin")

    first = local_to_utc(naive, "Europe/Berlin", fold=0)
    second = local_to_utc(naive, "Europe/Berlin", fold=1)
    assert int((second - first).total_seconds()) == 3600


def test_metric_distance_uses_projected_coordinates() -> None:
    distance = distance_meters((13.4132, 52.5219), (13.4232, 52.5219))
    assert 650 < distance < 750


def test_snapshot_uses_latest_known_observation_only_and_blocks_future_leakage() -> None:
    timestamp = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    observations = [
        traffic("D1", datetime(2026, 9, 14, 10, tzinfo=UTC), 90),
        traffic("D1", datetime(2026, 9, 14, 11, tzinfo=UTC), 100),
        traffic("D1", datetime(2026, 9, 14, 13, tzinfo=UTC), 999),
    ]
    disruption = Disruption(
        disruption_id="x",
        category=DisruptionCategory.CLOSURE,
        valid_from=datetime(2026, 9, 9, tzinfo=UTC),
        valid_until=datetime(2026, 9, 15, tzinfo=UTC),
        geometry={"type": "Point", "coordinates": [13.4, 52.5]},
        provenance=provenance(datetime(2026, 9, 9, tzinfo=UTC)),
    )

    snapshot = build_snapshot(
        timestamp=timestamp,
        transit_observations=[],
        traffic_observations=observations,
        disruptions=[disruption],
        source_status={"traffic": FreshnessStatus.FRESH},
        required_sources={"traffic", "transit"},
    )

    assert len(snapshot.traffic) == 1
    assert snapshot.traffic[0].vehicle_count == 100
    assert snapshot.disruptions == [disruption]
    assert snapshot.missing_sources == ["transit"]
