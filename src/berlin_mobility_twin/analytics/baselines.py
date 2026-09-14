from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, pstdev

from berlin_mobility_twin.domain.models import TrafficObservation


@dataclass(frozen=True)
class DetectorAnomaly:
    detector_id: str
    available: bool
    baseline_sample_size: int
    baseline_mean: float | None
    baseline_stddev: float | None
    observed_value: int | None
    absolute_deviation: float | None
    relative_deviation: float | None
    z_score: float | None
    comparison_rule: str = "same detector, weekday and UTC hour; historical observations only"


def detector_anomaly(
    current: TrafficObservation,
    history: list[TrafficObservation],
    *,
    min_samples: int = 4,
) -> DetectorAnomaly:
    """Compare current flow with a historical same-detector/weekday/hour baseline."""
    if min_samples < 1:
        raise ValueError("min_samples must be positive")
    if current.vehicle_count is None:
        return DetectorAnomaly(
            detector_id=current.detector_id,
            available=False,
            baseline_sample_size=0,
            baseline_mean=None,
            baseline_stddev=None,
            observed_value=None,
            absolute_deviation=None,
            relative_deviation=None,
            z_score=None,
        )

    values = [
        item.vehicle_count
        for item in history
        if item.detector_id == current.detector_id
        and item.observed_at < current.observed_at
        and item.observed_at.weekday() == current.observed_at.weekday()
        and item.observed_at.hour == current.observed_at.hour
        and item.vehicle_count is not None
    ]
    numeric = [float(value) for value in values]
    if len(numeric) < min_samples:
        return DetectorAnomaly(
            detector_id=current.detector_id,
            available=False,
            baseline_sample_size=len(numeric),
            baseline_mean=fmean(numeric) if numeric else None,
            baseline_stddev=pstdev(numeric) if len(numeric) > 1 else None,
            observed_value=current.vehicle_count,
            absolute_deviation=None,
            relative_deviation=None,
            z_score=None,
        )

    mean = fmean(numeric)
    stddev = pstdev(numeric)
    deviation = current.vehicle_count - mean
    return DetectorAnomaly(
        detector_id=current.detector_id,
        available=True,
        baseline_sample_size=len(numeric),
        baseline_mean=mean,
        baseline_stddev=stddev,
        observed_value=current.vehicle_count,
        absolute_deviation=deviation,
        relative_deviation=deviation / mean if mean != 0 else None,
        z_score=deviation / stddev if stddev > 0 else None,
    )
