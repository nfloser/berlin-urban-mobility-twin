from datetime import UTC, datetime

from fastapi.testclient import TestClient

from berlin_mobility_twin.api.app import create_app
from berlin_mobility_twin.domain.models import FreshnessStatus, MobilitySnapshot
from berlin_mobility_twin.storage.json_store import JsonSnapshotStore


def test_empty_api_is_explicitly_degraded_and_contains_no_fake_observations(tmp_path) -> None:
    client = TestClient(create_app())
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "degraded"

    status = client.get("/api/v1/status").json()
    assert status["observation_counts"] == {"transit": 0, "traffic": 0, "disruptions": 0}
    assert status["synthetic_production_data"] is False

    snapshot = client.get("/api/v1/mobility/snapshot").json()
    assert snapshot["transit"] == []
    assert snapshot["traffic"] == []
    assert snapshot["disruptions"] == []


def test_sources_endpoint_exposes_verified_provenance_metadata() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    sources = {item["source_id"]: item for item in response.json()}
    assert "vbb-gtfs-static" in sources
    assert sources["vbb-gtfs-static"]["licence"] == "CC BY 4.0"
    assert "berlin-traffic-detectors" in sources
    assert sources["berlin-traffic-detectors"]["licence"] == "dl-de-by-2.0"


def test_openapi_contains_versioned_mobility_routes() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/transit/stops" in paths
    assert "/api/v1/traffic/detectors" in paths
    assert "/api/v1/disruptions" in paths
    assert "/api/v1/mobility/snapshot" in paths


def test_json_snapshot_store_round_trips_typed_snapshot(tmp_path) -> None:
    path = tmp_path / "snapshot.json"
    store = JsonSnapshotStore(path)
    snapshot = MobilitySnapshot(
        timestamp=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_status={"traffic": FreshnessStatus.FRESH},
    )
    store.write(snapshot)
    loaded = store.read()
    assert loaded == snapshot
