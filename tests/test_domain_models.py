from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from berlin_mobility_twin.domain.models import (
    DataAvailability,
    DataQuality,
    FreshnessStatus,
    Provenance,
    TrafficObservation,
    TransitObservation,
)


def provenance() -> Provenance:
    now = datetime(2026, 9, 14, 10, tzinfo=UTC)
    return Provenance(
        source_id="berlin-traffic-detectors",
        provider="Land Berlin",
        dataset_title="Verkehrsdetektion Berlin",
        retrieved_at=now,
        source_url="https://daten.berlin.de/datensaetze/verkehrsdetektion-berlin",
        licence="dl-de-by-2.0",
        freshness=FreshnessStatus.FRESH,
    )


def test_provenance_rejects_naive_retrieval_timestamp() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_id="x",
            provider="x",
            dataset_title="x",
            retrieved_at=datetime(2026, 9, 14, 10),
            source_url="https://example.test",
            licence="test",
            freshness=FreshnessStatus.UNKNOWN,
        )


def test_traffic_observation_preserves_raw_and_rejects_impossible_values() -> None:
    with pytest.raises(ValidationError):
        TrafficObservation(
            detector_id="TEU00002_Det0",
            observed_at=datetime(2026, 9, 14, 10, tzinfo=UTC),
            vehicle_count=-1,
            speed_kmh=42.0,
            heavy_vehicle_count=1,
            availability=DataAvailability.OBSERVED,
            quality=DataQuality(),
            provenance=provenance(),
            raw={"vehicle_count": "-1"},
        )


def test_transit_realtime_absence_can_be_unknown_not_on_time() -> None:
    obs = TransitObservation(
        trip_id="trip-1",
        stop_id="stop-1",
        observed_at=datetime(2026, 9, 14, 10, tzinfo=UTC),
        scheduled_arrival=datetime(2026, 9, 14, 10, 5, tzinfo=UTC),
        predicted_arrival=None,
        delay_seconds=None,
        availability=DataAvailability.UNKNOWN,
        quality=DataQuality(warnings=["no realtime entity for trip"]),
        provenance=provenance(),
    )
    assert obs.delay_seconds is None
    assert obs.availability is DataAvailability.UNKNOWN
