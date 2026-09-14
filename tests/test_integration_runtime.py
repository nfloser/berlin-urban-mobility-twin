from datetime import UTC, datetime

from fastapi.testclient import TestClient

from berlin_mobility_twin.api.app import create_app
from berlin_mobility_twin.api.state import RuntimeState
from berlin_mobility_twin.cli import export_schemas
from berlin_mobility_twin.domain.models import (
    DataAvailability,
    DataQuality,
    Disruption,
    DisruptionCategory,
    FreshnessStatus,
    Provenance,
)
from berlin_mobility_twin.integration.contracts import export_network_disruption
from berlin_mobility_twin.processing.pipeline import refresh_live_sources


def provenance() -> Provenance:
    return Provenance(
        source_id="berlin-road-disruptions",
        provider="Digitale Plattform Stadtverkehr Berlin",
        dataset_title="Road disruptions",
        retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_url="https://example.invalid/source",
        licence="dl-de-by-2.0",
        freshness=FreshnessStatus.FRESH,
    )


def test_network_disruption_contract_preserves_provenance_and_confidence() -> None:
    disruption = Disruption(
        disruption_id="D1",
        category=DisruptionCategory.CLOSURE,
        description="closed",
        geometry={"type": "Point", "coordinates": [13.4, 52.5]},
        network_match_confidence=None,
        provenance=provenance(),
        quality=DataQuality(),
    )
    exported = export_network_disruption(
        disruption,
        timestamp=datetime(2026, 9, 14, 13, tzinfo=UTC),
    )
    assert exported.schema_version == "1.0.0"
    assert exported.disruption_id == "D1"
    assert exported.observation_status == DataAvailability.OBSERVED
    assert exported.provenance.source_id == "berlin-road-disruptions"
    assert exported.confidence is None


def test_integration_endpoints_and_aware_timestamp_validation() -> None:
    state = RuntimeState(required_sources=set())
    state.disruptions = [
        Disruption(
            disruption_id="D1",
            category=DisruptionCategory.CLOSURE,
            geometry={"type": "Point", "coordinates": [13.4, 52.5]},
            provenance=provenance(),
        )
    ]
    client = TestClient(create_app(state, serve_frontend=False))

    snapshot = client.get(
        "/api/v1/integration/mobility-snapshot",
        params={"at": "2026-09-14T13:00:00+00:00"},
    )
    assert snapshot.status_code == 200
    assert snapshot.json()["schema_version"] == "1.0.0"

    disruptions = client.get(
        "/api/v1/integration/network-disruptions",
        params={"at": "2026-09-14T13:00:00+00:00"},
    )
    assert disruptions.status_code == 200
    assert disruptions.json()[0]["disruption_id"] == "D1"

    naive = client.get(
        "/api/v1/mobility/snapshot",
        params={"at": "2026-09-14T13:00:00"},
    )
    assert naive.status_code == 422


def test_refresh_failures_are_explicit_and_never_create_observations() -> None:
    class BrokenClient:
        def fetch(self, url: str, *, etag: str | None = None):
            del url, etag
            raise RuntimeError("provider unavailable")

    state = RuntimeState()
    report = refresh_live_sources(state, BrokenClient(), include_static=False)
    assert set(report.failed) == {
        "vbb-gtfs-rt",
        "berlin-traffic-detector-locations",
        "berlin-road-disruptions",
    }
    assert state.transit_observations == []
    assert state.traffic_observations == []
    assert state.disruptions == []
    snapshot = state.snapshot(datetime(2026, 9, 14, 13, tzinfo=UTC))
    assert snapshot.source_errors
    assert any("provider unavailable" in warning for warning in snapshot.warnings)


def test_schema_export_contains_stable_contract_fields(tmp_path) -> None:
    paths = export_schemas(tmp_path)
    assert {path.name for path in paths} == {
        "mobility-snapshot.schema.json",
        "network-disruption.schema.json",
        "internal-mobility-snapshot.schema.json",
    }
    mobility = (tmp_path / "mobility-snapshot.schema.json").read_text(encoding="utf-8")
    disruption = (tmp_path / "network-disruption.schema.json").read_text(encoding="utf-8")
    assert '"schema_version"' in mobility
    assert '"source_errors"' in mobility
    assert '"disruption_id"' in disruption
