from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from pydantic import AwareDatetime

from berlin_mobility_twin.api.state import RuntimeState
from berlin_mobility_twin.domain.models import (
    DataSource,
    Disruption,
    IntegrationMobilitySnapshot,
    MobilitySnapshot,
    NetworkDisruption,
    TrafficDetector,
    TrafficObservation,
    TransitObservation,
    TransitRoute,
    TransitStop,
    TransitTrip,
)
from berlin_mobility_twin.ingestion.sources import SOURCES
from berlin_mobility_twin.integration.contracts import (
    export_mobility_snapshot,
    export_network_disruption,
)


def _resolve_frontend_dir() -> Path:
    configured = os.getenv("MOBILITY_FRONTEND_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app(state: RuntimeState | None = None, *, serve_frontend: bool = True) -> FastAPI:
    runtime = state or RuntimeState()
    app = FastAPI(
        title="Berlin Urban Mobility Twin API",
        version="1.0.0",
        description="Versioned, provenance-aware access to available Berlin mobility state.",
    )
    app.state.mobility = runtime

    @app.get("/api/v1/health")
    def health() -> dict[str, object]:
        return {
            "status": runtime.health_status,
            "missing_sources": runtime.missing_sources,
            "source_errors": runtime.source_errors,
        }

    @app.get("/api/v1/sources")
    def sources() -> list[DataSource]:
        return list(SOURCES)

    @app.get("/api/v1/status")
    def status() -> dict[str, object]:
        return {
            "status": runtime.health_status,
            "source_status": {key: value.value for key, value in runtime.source_status.items()},
            "source_errors": dict(runtime.source_errors),
            "missing_sources": runtime.missing_sources,
            "entity_counts": {
                "stops": len(runtime.stops),
                "routes": len(runtime.routes),
                "trips": len(runtime.trips),
                "detectors": len(runtime.traffic_detectors),
            },
            "observation_counts": {
                "transit": len(runtime.transit_observations),
                "traffic": len(runtime.traffic_observations),
                "disruptions": len(runtime.disruptions),
            },
            "synthetic_production_data": False,
        }

    @app.get("/api/v1/transit/stops")
    def transit_stops() -> list[TransitStop]:
        return runtime.stops

    @app.get("/api/v1/transit/routes")
    def transit_routes() -> list[TransitRoute]:
        return runtime.routes

    @app.get("/api/v1/transit/trips")
    def transit_trips() -> list[TransitTrip]:
        return runtime.trips

    @app.get("/api/v1/transit/state")
    def transit_state() -> list[TransitObservation]:
        return runtime.transit_observations

    @app.get("/api/v1/traffic/detectors")
    def traffic_detectors() -> list[TrafficDetector]:
        return runtime.traffic_detectors

    @app.get("/api/v1/traffic/state")
    def traffic_state() -> list[TrafficObservation]:
        return runtime.traffic_observations

    @app.get("/api/v1/disruptions")
    def disruptions() -> list[Disruption]:
        return runtime.disruptions

    @app.get("/api/v1/mobility/snapshot", response_model=MobilitySnapshot)
    def mobility_snapshot(
        at: AwareDatetime | None = Query(default=None, description="Timezone-aware point in time"),
    ) -> MobilitySnapshot:
        moment = at.astimezone(UTC) if at is not None else datetime.now(UTC)
        return runtime.snapshot(moment)

    @app.get(
        "/api/v1/integration/mobility-snapshot",
        response_model=IntegrationMobilitySnapshot,
    )
    def integration_mobility_snapshot(
        at: AwareDatetime | None = Query(default=None, description="Timezone-aware point in time"),
    ) -> IntegrationMobilitySnapshot:
        moment = at.astimezone(UTC) if at is not None else datetime.now(UTC)
        return export_mobility_snapshot(
            runtime.snapshot(moment),
            stops=runtime.stops,
            detectors=runtime.traffic_detectors,
        )

    @app.get(
        "/api/v1/integration/network-disruptions",
        response_model=list[NetworkDisruption],
    )
    def integration_network_disruptions(
        at: AwareDatetime | None = Query(default=None, description="Timezone-aware point in time"),
    ) -> list[NetworkDisruption]:
        moment = at.astimezone(UTC) if at is not None else datetime.now(UTC)
        active = runtime.snapshot(moment).disruptions
        return [export_network_disruption(item, timestamp=moment) for item in active]

    frontend_dir = _resolve_frontend_dir()
    if serve_frontend and frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app


app = create_app()
