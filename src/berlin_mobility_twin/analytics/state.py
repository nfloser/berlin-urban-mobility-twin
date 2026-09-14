from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import floor

from shapely.geometry import shape

from berlin_mobility_twin.domain.models import (
    Disruption,
    FreshnessStatus,
    MobilitySnapshot,
    QualitySeverity,
)
from berlin_mobility_twin.processing.spatial import BERLIN_METRIC_CRS, project_point


@dataclass(frozen=True)
class ActiveDisruptionCount:
    total_count: int
    active_count: int


@dataclass(frozen=True)
class DisruptionSpatialConcentration:
    active_disruptions: int
    eligible_disruptions: int
    excluded_disruptions: int
    grid_size_m: float
    max_cell_count: int
    concentration: float | None
    crs: str = BERLIN_METRIC_CRS
    definition: str = "share of eligible active disruption centroids in the most occupied grid cell"


@dataclass(frozen=True)
class MobilityStateSummary:
    transit_observations: int
    traffic_observations: int
    active_disruptions: int
    quality_warning_observations: int
    fresh_sources: int
    stale_sources: int
    expired_sources: int
    unknown_freshness_sources: int
    missing_sources: int
    source_errors: int


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("analysis timestamp must be timezone-aware")


def _is_active(disruption: Disruption, at: datetime) -> bool:
    if disruption.valid_from is not None and disruption.valid_from > at:
        return False
    return disruption.valid_until is None or disruption.valid_until >= at


def active_disruption_count(
    disruptions: list[Disruption],
    *,
    at: datetime,
) -> ActiveDisruptionCount:
    """Count disruptions whose validity intervals include the analysis timestamp."""
    _require_aware(at)
    return ActiveDisruptionCount(
        total_count=len(disruptions),
        active_count=sum(_is_active(item, at) for item in disruptions),
    )


def disruption_spatial_concentration(
    disruptions: list[Disruption],
    *,
    at: datetime,
    grid_size_m: float = 1000.0,
) -> DisruptionSpatialConcentration:
    """Measure concentration using active disruption centroids in a metric Berlin grid."""
    _require_aware(at)
    if grid_size_m <= 0:
        raise ValueError("grid_size_m must be positive")

    active = [item for item in disruptions if _is_active(item, at)]
    cells: dict[tuple[int, int], int] = {}
    excluded = 0
    for disruption in active:
        try:
            geometry = shape(disruption.geometry)
            if geometry.is_empty:
                excluded += 1
                continue
            centroid = geometry.centroid
            x, y = project_point((float(centroid.x), float(centroid.y)))
        except (TypeError, ValueError, KeyError):
            excluded += 1
            continue
        cell = (floor(x / grid_size_m), floor(y / grid_size_m))
        cells[cell] = cells.get(cell, 0) + 1

    eligible = len(active) - excluded
    maximum = max(cells.values(), default=0)
    return DisruptionSpatialConcentration(
        active_disruptions=len(active),
        eligible_disruptions=eligible,
        excluded_disruptions=excluded,
        grid_size_m=grid_size_m,
        max_cell_count=maximum,
        concentration=maximum / eligible if eligible else None,
    )


def mobility_state_summary(snapshot: MobilitySnapshot) -> MobilityStateSummary:
    """Summarise observable state with explicit counts and no opaque composite score."""
    quality_items = [
        *(item.quality for item in snapshot.transit),
        *(item.quality for item in snapshot.traffic),
        *(item.quality for item in snapshot.disruptions),
    ]
    warning_count = sum(
        bool(item.warnings) or item.severity in {QualitySeverity.WARNING, QualitySeverity.ERROR}
        for item in quality_items
    )
    statuses = list(snapshot.source_status.values())
    return MobilityStateSummary(
        transit_observations=len(snapshot.transit),
        traffic_observations=len(snapshot.traffic),
        active_disruptions=len(snapshot.disruptions),
        quality_warning_observations=warning_count,
        fresh_sources=statuses.count(FreshnessStatus.FRESH),
        stale_sources=statuses.count(FreshnessStatus.STALE),
        expired_sources=statuses.count(FreshnessStatus.EXPIRED),
        unknown_freshness_sources=statuses.count(FreshnessStatus.UNKNOWN),
        missing_sources=len(snapshot.missing_sources),
        source_errors=len(snapshot.source_errors),
    )
