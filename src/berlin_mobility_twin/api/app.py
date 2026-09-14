from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, Query

from berlin_mobility_twin.api.state import RuntimeState
from berlin_mobility_twin.domain.models import (
    DataSource,
    Disruption,
    MobilitySnapshot,
    TrafficDetector,
    TrafficObservation,
    TransitObservation,
    TransitRoute,
    TransitStop,
)
from berlin_mobility_twin.ingestion.sources import SOURCES


def create_app(state: RuntimeState | None = None) -> FastAPI:
    runtime = state or RuntimeState()
    app = FastAPI(
        title="Berlin Urban Mobility Twin API",
        version="1.0.0",
        description="Versioned, provenance-aware access to available Berlin mobility state.",
    )
    app.state.mobility = runtime

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        has_any = bool(
            runtime.transit_observations
            or runtime.traffic_observations
            or runtime.disruptions
        )
        return {"status": "ok" if has_any else "degraded"}

    @app.get("/api/v1/sources")
    def sources() -> list[DataSource]:
        return list(SOURCES)

    @app.get("/api/v1/status")
    def status() -> dict[str, object]:
        return {
            "status": "ok" if runtime.source_status else "degraded",
            "source_status": {key: value.value for key, value in runtime.source_status.items()},
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
        at: datetime | None = Query(default=None, description="Timezone-aware point in time"),
    ) -> MobilitySnapshot:
        moment = at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("snapshot query timestamp must include a timezone offset")
        return runtime.snapshot(moment.astimezone(UTC))

    return app


app = create_app()
