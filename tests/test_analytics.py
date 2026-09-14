from datetime import UTC, datetime, timedelta

import pytest

from berlin_mobility_twin.analytics.baselines import detector_anomaly
from berlin_mobility_twin.analytics.mobility import (
    delay_distribution,
    detector_summary,
    headway_deviation,
    reliability,
)
from berlin_mobility_twin.domain.models import (
    DataAvailability,
    DataQuality,
    FreshnessStatus,
    Provenance,
    TrafficObservation,
    TransitObservation,
)


def provenance(at: datetime) -> Provenance:
    return Provenance(
        source_id="fixture",
        provider="fixture",
        dataset_title="fixture",
        retrieved_at=at,
        observation_at=at,
        source_url="https://example.test",
        licence="fixture",
        freshness=FreshnessStatus.FRESH,
    )


def transit(delay: int | None, minute: int) -> TransitObservation:
    at = datetime(2026, 9, 14, 10, minute, tzinfo=UTC)
    return TransitObservation(
        trip_id=f"T{minute}",
        stop_id="S1",
        observed_at=at,
        delay_seconds=delay,
        availability=DataAvailability.REALTIME,
        quality=DataQuality(),
        provenance=provenance(at),
    )


def traffic(at: datetime, count: int, speed: float = 40.0) -> TrafficObservation:
    return TrafficObservation(
        detector_id="D1",
        observed_at=at,
        vehicle_count=count,
        speed_kmh=speed,
        availability=DataAvailability.HISTORICAL,
        quality=DataQuality(),
        provenance=provenance(at),
    )


def test_delay_distribution_ignores_unknown_delay_instead_of_treating_it_as_zero() -> None:
    result = delay_distribution([transit(0, 0), transit(60, 1), transit(None, 2), transit(300, 3)])
    assert result.sample_size == 3
    assert result.median_seconds == 60
    assert result.mean_seconds == 120
    assert result.unknown_count == 1


def test_reliability_exposes_formula_components() -> None:
    result = reliability(
        [transit(30, 0), transit(90, 1), transit(None, 2), transit(300, 3)],
        tolerance_seconds=120,
    )
    assert result.eligible_observations == 3
    assert result.within_tolerance == 2
    assert result.rate == pytest.approx(2 / 3)
    assert result.tolerance_seconds == 120


def test_headway_deviation_uses_consecutive_observed_times() -> None:
    times = [
        datetime(2026, 9, 14, 10, 0, tzinfo=UTC),
        datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
        datetime(2026, 9, 14, 10, 12, tzinfo=UTC),
    ]
    result = headway_deviation(times, scheduled_headway_seconds=300)
    assert result.observed_headways_seconds == [300, 420]
    assert result.deviations_seconds == [0, 120]


def test_detector_summary_keeps_missing_measurements_out_of_denominators() -> None:
    at = datetime(2026, 9, 14, 10, tzinfo=UTC)
    missing_speed = traffic(at + timedelta(hours=1), 120).model_copy(
        update={"speed_kmh": None}
    )
    result = detector_summary([traffic(at, 100, 40), missing_speed])
    assert result.observation_count == 2
    assert result.mean_vehicle_count == 110
    assert result.speed_sample_size == 1
    assert result.mean_speed_kmh == 40


def test_anomaly_baseline_uses_only_past_same_weekday_and_hour() -> None:
    evaluation_time = datetime(2026, 9, 14, 10, tzinfo=UTC)
    history = [
        traffic(evaluation_time - timedelta(days=7), 100),
        traffic(evaluation_time - timedelta(days=14), 110),
        traffic(evaluation_time - timedelta(days=21), 90),
        traffic(evaluation_time - timedelta(days=7, hours=-1), 999),
        traffic(evaluation_time + timedelta(days=7), 9999),
    ]
    current = traffic(evaluation_time, 150)
    result = detector_anomaly(current, history, min_samples=3)
    assert result.baseline_sample_size == 3
    assert result.baseline_mean == 100
    assert result.absolute_deviation == 50
    assert result.relative_deviation == pytest.approx(0.5)


def test_anomaly_reports_unavailable_when_history_is_insufficient() -> None:
    evaluation_time = datetime(2026, 9, 14, 10, tzinfo=UTC)
    current = traffic(evaluation_time, 150)
    result = detector_anomaly(current, [], min_samples=3)
    assert result.available is False
    assert result.baseline_sample_size == 0
