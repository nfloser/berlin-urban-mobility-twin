from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import fmean, median

from berlin_mobility_twin.domain.models import TrafficObservation, TransitObservation


@dataclass(frozen=True)
class DelayDistribution:
    sample_size: int
    unknown_count: int
    mean_seconds: float | None
    median_seconds: float | None
    minimum_seconds: int | None
    maximum_seconds: int | None


@dataclass(frozen=True)
class ReliabilityResult:
    eligible_observations: int
    unknown_observations: int
    within_tolerance: int
    tolerance_seconds: int
    rate: float | None


@dataclass(frozen=True)
class HeadwayDeviation:
    scheduled_headway_seconds: int
    observed_headways_seconds: list[int]
    deviations_seconds: list[int]


@dataclass(frozen=True)
class DetectorSummary:
    observation_count: int
    count_sample_size: int
    speed_sample_size: int
    mean_vehicle_count: float | None
    mean_speed_kmh: float | None


def delay_distribution(observations: list[TransitObservation]) -> DelayDistribution:
    """Summarise known GTFS-RT delays; missing delay is never imputed as zero."""
    delays = [item.delay_seconds for item in observations if item.delay_seconds is not None]
    unknown = len(observations) - len(delays)
    if not delays:
        return DelayDistribution(0, unknown, None, None, None, None)
    return DelayDistribution(
        sample_size=len(delays),
        unknown_count=unknown,
        mean_seconds=fmean(delays),
        median_seconds=median(delays),
        minimum_seconds=min(delays),
        maximum_seconds=max(delays),
    )


def reliability(
    observations: list[TransitObservation], *, tolerance_seconds: int = 120
) -> ReliabilityResult:
    """Return P(|delay| <= tolerance) over observations with a known delay value."""
    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be non-negative")
    known = [item.delay_seconds for item in observations if item.delay_seconds is not None]
    within = sum(abs(delay) <= tolerance_seconds for delay in known)
    return ReliabilityResult(
        eligible_observations=len(known),
        unknown_observations=len(observations) - len(known),
        within_tolerance=within,
        tolerance_seconds=tolerance_seconds,
        rate=within / len(known) if known else None,
    )


def headway_deviation(
    observed_times: list[datetime], *, scheduled_headway_seconds: int
) -> HeadwayDeviation:
    """Compare consecutive observed headways with one explicit scheduled headway."""
    if scheduled_headway_seconds <= 0:
        raise ValueError("scheduled_headway_seconds must be positive")
    for value in observed_times:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed times must be timezone-aware")
    ordered = sorted(observed_times)
    headways = [
        int((current - previous).total_seconds())
        for previous, current in zip(ordered, ordered[1:], strict=False)
    ]
    return HeadwayDeviation(
        scheduled_headway_seconds=scheduled_headway_seconds,
        observed_headways_seconds=headways,
        deviations_seconds=[value - scheduled_headway_seconds for value in headways],
    )


def detector_summary(observations: list[TrafficObservation]) -> DetectorSummary:
    """Compute detector-level means using only present measurement fields."""
    counts = [item.vehicle_count for item in observations if item.vehicle_count is not None]
    speeds = [item.speed_kmh for item in observations if item.speed_kmh is not None]
    return DetectorSummary(
        observation_count=len(observations),
        count_sample_size=len(counts),
        speed_sample_size=len(speeds),
        mean_vehicle_count=fmean(counts) if counts else None,
        mean_speed_kmh=fmean(speeds) if speeds else None,
    )
