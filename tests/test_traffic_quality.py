from datetime import UTC, datetime

from berlin_mobility_twin.domain.models import (
    DataAvailability,
    DataQuality,
    FreshnessStatus,
    Provenance,
    TrafficObservation,
)
from berlin_mobility_twin.processing.traffic_quality import annotate_temporal_quality


def observation(hour: int, minute: int = 0) -> TrafficObservation:
    timestamp = datetime(2026, 1, 15, hour, minute, tzinfo=UTC)
    return TrafficObservation(
        detector_id="D1",
        observed_at=timestamp,
        vehicle_count=100,
        speed_kmh=40,
        availability=DataAvailability.HISTORICAL,
        quality=DataQuality(),
        provenance=Provenance(
            source_id="berlin-traffic-detectors",
            provider="Berlin",
            dataset_title="Traffic",
            retrieved_at=datetime(2026, 1, 16, tzinfo=UTC),
            observation_at=timestamp,
            source_url="https://example.invalid",
            licence="dl-de-by-2.0",
            freshness=FreshnessStatus.UNKNOWN,
        ),
    )


def test_temporal_quality_flags_gaps_without_repairing_measurements() -> None:
    result = annotate_temporal_quality(
        [observation(10), observation(12, 30)],
        expected_interval_seconds=3600,
    )
    assert [issue.kind for issue in result.issues] == ["gap"]
    assert result.observations[1].vehicle_count == 100
    assert "temporal gap" in result.observations[1].quality.warnings[0]


def test_temporal_quality_flags_non_monotonic_source_order() -> None:
    result = annotate_temporal_quality(
        [observation(11), observation(10)],
        expected_interval_seconds=3600,
    )
    assert any(issue.kind == "non_monotonic" for issue in result.issues)
    assert any(
        "precedes previous source row" in warning
        for warning in result.observations[1].quality.warnings
    )


def test_temporal_quality_requires_explicit_positive_expected_interval() -> None:
    try:
        annotate_temporal_quality([observation(10)], expected_interval_seconds=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected ValueError")
