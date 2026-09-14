from datetime import UTC, datetime, timedelta

from berlin_mobility_twin.analytics.state import (
    active_disruption_count,
    disruption_spatial_concentration,
    mobility_state_summary,
)
from berlin_mobility_twin.domain.models import (
    DataAvailability,
    DataQuality,
    Disruption,
    DisruptionCategory,
    FreshnessStatus,
    MobilitySnapshot,
    Provenance,
    QualitySeverity,
    TrafficObservation,
    TransitObservation,
)


def provenance(at: datetime, *, freshness: FreshnessStatus = FreshnessStatus.FRESH) -> Provenance:
    return Provenance(
        source_id="fixture",
        provider="fixture",
        dataset_title="fixture",
        retrieved_at=at,
        observation_at=at,
        source_url="https://example.test",
        licence="fixture",
        freshness=freshness,
    )


def disruption(
    disruption_id: str,
    longitude: float,
    latitude: float,
    at: datetime,
    *,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> Disruption:
    return Disruption(
        disruption_id=disruption_id,
        category=DisruptionCategory.CONSTRUCTION,
        valid_from=valid_from,
        valid_until=valid_until,
        geometry={"type": "Point", "coordinates": [longitude, latitude]},
        provenance=provenance(at),
    )


def test_active_disruption_count_uses_validity_interval() -> None:
    at = datetime(2026, 9, 14, 12, tzinfo=UTC)
    disruptions = [
        disruption("active", 13.4, 52.5, at, valid_from=at - timedelta(hours=1)),
        disruption("future", 13.41, 52.51, at, valid_from=at + timedelta(hours=1)),
        disruption("expired", 13.42, 52.52, at, valid_until=at - timedelta(seconds=1)),
    ]

    result = active_disruption_count(disruptions, at=at)

    assert result.active_count == 1
    assert result.total_count == 3


def test_spatial_concentration_reports_dominant_metric_grid_cell() -> None:
    at = datetime(2026, 9, 14, 12, tzinfo=UTC)
    disruptions = [
        disruption("a", 13.4050, 52.5200, at),
        disruption("b", 13.4051, 52.5201, at),
        disruption("c", 13.45, 52.55, at),
    ]

    result = disruption_spatial_concentration(disruptions, at=at, grid_size_m=1000)

    assert result.eligible_disruptions == 3
    assert result.excluded_disruptions == 0
    assert result.max_cell_count == 2
    assert result.concentration == 2 / 3
    assert result.crs == "EPSG:25833"


def test_mobility_state_summary_exposes_counts_without_composite_score() -> None:
    at = datetime(2026, 9, 14, 12, tzinfo=UTC)
    transit = TransitObservation(
        trip_id="T1",
        stop_id="S1",
        observed_at=at,
        delay_seconds=60,
        availability=DataAvailability.REALTIME,
        quality=DataQuality(),
        provenance=provenance(at),
    )
    traffic = TrafficObservation(
        detector_id="D1",
        observed_at=at,
        vehicle_count=100,
        speed_kmh=35,
        availability=DataAvailability.HISTORICAL,
        quality=DataQuality(warnings=["source warning"], severity=QualitySeverity.WARNING),
        provenance=provenance(at, freshness=FreshnessStatus.UNKNOWN),
    )
    snapshot = MobilitySnapshot(
        timestamp=at,
        transit=[transit],
        traffic=[traffic],
        disruptions=[disruption("X1", 13.4, 52.5, at)],
        source_status={
            "vbb-gtfs-rt": FreshnessStatus.FRESH,
            "berlin-traffic-detectors": FreshnessStatus.UNKNOWN,
        },
        missing_sources=["vbb-gtfs-static"],
    )

    result = mobility_state_summary(snapshot)

    assert result.transit_observations == 1
    assert result.traffic_observations == 1
    assert result.active_disruptions == 1
    assert result.quality_warning_observations == 1
    assert result.fresh_sources == 1
    assert result.unknown_freshness_sources == 1
    assert result.missing_sources == 1
