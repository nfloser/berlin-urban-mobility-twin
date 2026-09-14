from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from berlin_mobility_twin.domain.models import DataQuality, QualitySeverity, TrafficObservation


@dataclass(frozen=True)
class TemporalQualityIssue:
    detector_id: str
    observed_at: datetime
    kind: str
    message: str


@dataclass(frozen=True)
class TemporalQualityResult:
    observations: list[TrafficObservation]
    issues: list[TemporalQualityIssue]


def annotate_temporal_quality(
    observations: list[TrafficObservation],
    *,
    expected_interval_seconds: int,
) -> TemporalQualityResult:
    """Flag source-order discontinuities and gaps without changing measurement values."""
    if expected_interval_seconds <= 0:
        raise ValueError("expected_interval_seconds must be positive")

    issues: list[TemporalQualityIssue] = []
    previous_in_source_order: dict[str, datetime] = {}
    by_detector: dict[str, list[TrafficObservation]] = defaultdict(list)

    for observation in observations:
        previous_timestamp = previous_in_source_order.get(observation.detector_id)
        if previous_timestamp is not None and observation.observed_at < previous_timestamp:
            issues.append(
                TemporalQualityIssue(
                    detector_id=observation.detector_id,
                    observed_at=observation.observed_at,
                    kind="non_monotonic",
                    message="timestamp precedes previous source row for detector",
                )
            )
        previous_in_source_order[observation.detector_id] = observation.observed_at
        by_detector[observation.detector_id].append(observation)

    for detector_id, detector_observations in by_detector.items():
        ordered = sorted(detector_observations, key=lambda item: item.observed_at)
        for previous_observation, current_observation in zip(
            ordered,
            ordered[1:],
            strict=False,
        ):
            interval = int(
                (current_observation.observed_at - previous_observation.observed_at).total_seconds()
            )
            if interval > expected_interval_seconds:
                issues.append(
                    TemporalQualityIssue(
                        detector_id=detector_id,
                        observed_at=current_observation.observed_at,
                        kind="gap",
                        message=(
                            f"temporal gap {interval}s exceeds configured expected interval "
                            f"{expected_interval_seconds}s"
                        ),
                    )
                )

    messages_by_key: dict[tuple[str, datetime], list[str]] = defaultdict(list)
    for issue in issues:
        messages_by_key[(issue.detector_id, issue.observed_at)].append(issue.message)

    annotated: list[TrafficObservation] = []
    for observation in observations:
        new_messages = messages_by_key.get((observation.detector_id, observation.observed_at), [])
        if not new_messages:
            annotated.append(observation)
            continue
        warnings = [*observation.quality.warnings, *new_messages]
        quality = DataQuality(
            warnings=warnings,
            severity=QualitySeverity.WARNING,
            is_valid=observation.quality.is_valid,
        )
        annotated.append(observation.model_copy(update={"quality": quality}))

    return TemporalQualityResult(observations=annotated, issues=issues)
