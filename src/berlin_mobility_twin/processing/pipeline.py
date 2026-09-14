from __future__ import annotations

import json
from datetime import datetime
from typing import Protocol

from berlin_mobility_twin.api.state import RuntimeState
from berlin_mobility_twin.domain.models import FreshnessStatus
from berlin_mobility_twin.ingestion.disruptions import parse_disruptions
from berlin_mobility_twin.ingestion.gtfs_realtime import RealtimeFeedResult, parse_gtfs_rt
from berlin_mobility_twin.ingestion.gtfs_static import IngestionDiagnostics, parse_gtfs_zip
from berlin_mobility_twin.ingestion.http_client import FetchResult
from berlin_mobility_twin.ingestion.sources import SOURCE_BY_ID
from berlin_mobility_twin.ingestion.traffic import (
    TrafficCsvSchema,
    TrafficIngestionResult,
    parse_detector_locations,
    parse_traffic_csv,
)


class FetchClient(Protocol):
    def fetch(self, url: str, *, etag: str | None = None) -> FetchResult: ...


def load_gtfs_static(state: RuntimeState, payload: bytes) -> IngestionDiagnostics:
    """Validate and load a real GTFS schedule payload into runtime state."""
    dataset = parse_gtfs_zip(payload, strict=True)
    state.stops = sorted(dataset.stops.values(), key=lambda item: item.stop_id)
    state.routes = sorted(dataset.routes.values(), key=lambda item: item.route_id)
    state.trips = sorted(dataset.trips.values(), key=lambda item: item.trip_id)
    state.source_status["vbb-gtfs-static"] = FreshnessStatus.FRESH
    return dataset.diagnostics


def refresh_berlin_road_sources(
    state: RuntimeState,
    client: FetchClient,
) -> None:
    """Refresh official detector locations and published Berlin road disruptions."""
    detector_source = SOURCE_BY_ID["berlin-traffic-detector-locations"]
    disruption_source = SOURCE_BY_ID["berlin-road-disruptions"]
    detector_fetch = client.fetch(detector_source.source_url)
    disruption_fetch = client.fetch(disruption_source.source_url)
    if detector_fetch.content is None or disruption_fetch.content is None:
        raise RuntimeError("road source returned no content")

    detector_payload = json.loads(detector_fetch.content)
    disruption_payload = json.loads(disruption_fetch.content)
    state.traffic_detectors = parse_detector_locations(
        detector_payload,
        retrieved_at=detector_fetch.retrieved_at,
        source_url=detector_fetch.url,
    )
    result = parse_disruptions(
        disruption_payload,
        retrieved_at=disruption_fetch.retrieved_at,
        source_url=disruption_fetch.url,
        strict=False,
    )
    state.disruptions = result.disruptions
    state.source_status["berlin-traffic-detector-locations"] = FreshnessStatus.UNKNOWN
    state.source_status["berlin-road-disruptions"] = FreshnessStatus.UNKNOWN


def refresh_vbb_realtime(
    state: RuntimeState,
    client: FetchClient,
    *,
    stale_after_seconds: int = 120,
) -> RealtimeFeedResult:
    source = SOURCE_BY_ID["vbb-gtfs-rt"]
    fetch = client.fetch(source.source_url)
    if fetch.content is None:
        raise RuntimeError("VBB GTFS-Realtime source returned no content")
    result = parse_gtfs_rt(
        fetch.content,
        retrieved_at=fetch.retrieved_at,
        source_url=fetch.url,
        stale_after_seconds=stale_after_seconds,
    )
    state.transit_observations = result.observations
    state.source_status["vbb-gtfs-rt"] = result.freshness
    return result


def load_traffic_archive(
    state: RuntimeState,
    payload: bytes,
    *,
    schema: TrafficCsvSchema,
    retrieved_at: datetime,
    source_url: str,
) -> TrafficIngestionResult:
    """Load historical detector observations with an explicit, inspected CSV mapping."""
    result = parse_traffic_csv(
        payload,
        schema=schema,
        retrieved_at=retrieved_at,
        source_url=source_url,
    )
    state.traffic_observations = result.observations
    state.source_status["berlin-traffic-detectors"] = FreshnessStatus.UNKNOWN
    return result
