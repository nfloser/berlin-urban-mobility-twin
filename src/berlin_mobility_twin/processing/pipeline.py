from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from berlin_mobility_twin.api.state import RuntimeState
from berlin_mobility_twin.domain.models import FreshnessStatus
from berlin_mobility_twin.ingestion.disruptions import DisruptionIngestionResult, parse_disruptions
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
from berlin_mobility_twin.processing.traffic_quality import annotate_temporal_quality


class FetchClient(Protocol):
    def fetch(self, url: str, *, etag: str | None = None) -> FetchResult: ...


@dataclass(frozen=True)
class RefreshReport:
    succeeded: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def is_degraded(self) -> bool:
        return bool(self.failed)


def _content_or_raise(fetch: FetchResult, source_id: str) -> bytes:
    if fetch.content is None:
        raise RuntimeError(f"{source_id} returned no content")
    return fetch.content


def _clear_source_error(state: RuntimeState, source_id: str) -> None:
    state.source_errors.pop(source_id, None)


def _record_source_error(state: RuntimeState, source_id: str, exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    state.source_errors[source_id] = message
    return message


def load_gtfs_static(state: RuntimeState, payload: bytes) -> IngestionDiagnostics:
    """Validate and load a real GTFS schedule payload into runtime state."""
    dataset = parse_gtfs_zip(payload, strict=True)
    state.stops = sorted(dataset.stops.values(), key=lambda item: item.stop_id)
    state.routes = sorted(dataset.routes.values(), key=lambda item: item.route_id)
    state.trips = sorted(dataset.trips.values(), key=lambda item: item.trip_id)
    state.source_status["vbb-gtfs-static"] = FreshnessStatus.FRESH
    _clear_source_error(state, "vbb-gtfs-static")
    return dataset.diagnostics


def refresh_vbb_static(state: RuntimeState, client: FetchClient) -> IngestionDiagnostics:
    source = SOURCE_BY_ID["vbb-gtfs-static"]
    fetch = client.fetch(source.source_url)
    return load_gtfs_static(state, _content_or_raise(fetch, source.source_id))


def refresh_detector_locations(state: RuntimeState, client: FetchClient) -> int:
    source = SOURCE_BY_ID["berlin-traffic-detector-locations"]
    fetch = client.fetch(source.source_url)
    payload = json.loads(_content_or_raise(fetch, source.source_id))
    state.traffic_detectors = parse_detector_locations(
        payload,
        retrieved_at=fetch.retrieved_at,
        source_url=fetch.url,
    )
    state.source_status[source.source_id] = FreshnessStatus.UNKNOWN
    _clear_source_error(state, source.source_id)
    return len(state.traffic_detectors)


def refresh_disruptions(state: RuntimeState, client: FetchClient) -> DisruptionIngestionResult:
    source = SOURCE_BY_ID["berlin-road-disruptions"]
    fetch = client.fetch(source.source_url)
    payload = json.loads(_content_or_raise(fetch, source.source_id))
    result = parse_disruptions(
        payload,
        retrieved_at=fetch.retrieved_at,
        source_url=fetch.url,
        strict=False,
    )
    state.disruptions = result.disruptions
    state.source_status[source.source_id] = FreshnessStatus.UNKNOWN
    _clear_source_error(state, source.source_id)
    return result


def refresh_berlin_road_sources(state: RuntimeState, client: FetchClient) -> None:
    """Refresh detector locations and disruptions; retained as a convenience wrapper."""
    refresh_detector_locations(state, client)
    refresh_disruptions(state, client)


def refresh_vbb_realtime(
    state: RuntimeState,
    client: FetchClient,
    *,
    stale_after_seconds: int = 120,
) -> RealtimeFeedResult:
    source = SOURCE_BY_ID["vbb-gtfs-rt"]
    fetch = client.fetch(source.source_url)
    result = parse_gtfs_rt(
        _content_or_raise(fetch, source.source_id),
        retrieved_at=fetch.retrieved_at,
        source_url=fetch.url,
        stale_after_seconds=stale_after_seconds,
    )
    state.transit_observations = result.observations
    state.source_status[source.source_id] = result.freshness
    _clear_source_error(state, source.source_id)
    return result


def refresh_live_sources(
    state: RuntimeState,
    client: FetchClient,
    *,
    include_static: bool = True,
    stale_after_seconds: int = 120,
) -> RefreshReport:
    """Refresh independently retrievable sources without substituting synthetic data on failure."""
    succeeded: list[str] = []
    failed: dict[str, str] = {}

    operations: list[tuple[str, Callable[[], object]]] = []
    if include_static:
        operations.append(("vbb-gtfs-static", lambda: refresh_vbb_static(state, client)))
    operations.extend(
        [
            (
                "vbb-gtfs-rt",
                lambda: refresh_vbb_realtime(
                    state,
                    client,
                    stale_after_seconds=stale_after_seconds,
                ),
            ),
            (
                "berlin-traffic-detector-locations",
                lambda: refresh_detector_locations(state, client),
            ),
            ("berlin-road-disruptions", lambda: refresh_disruptions(state, client)),
        ]
    )

    for source_id, operation in operations:
        try:
            operation()
        except Exception as exc:  # provider failures must degrade, not fabricate data
            failed[source_id] = _record_source_error(state, source_id, exc)
        else:
            succeeded.append(source_id)

    return RefreshReport(succeeded=succeeded, failed=failed)


def load_traffic_archive(
    state: RuntimeState,
    payload: bytes,
    *,
    schema: TrafficCsvSchema,
    retrieved_at: datetime,
    source_url: str,
    expected_interval_seconds: int | None = None,
) -> TrafficIngestionResult:
    """Load historical detector observations with an explicit, inspected CSV mapping."""
    result = parse_traffic_csv(
        payload,
        schema=schema,
        retrieved_at=retrieved_at,
        source_url=source_url,
    )
    if expected_interval_seconds is not None:
        temporal = annotate_temporal_quality(
            result.observations,
            expected_interval_seconds=expected_interval_seconds,
        )
        result = TrafficIngestionResult(
            raw_rows=result.raw_rows,
            observations=temporal.observations,
            rejected_rows=result.rejected_rows,
            diagnostics=result.diagnostics,
        )
    state.traffic_observations = result.observations
    state.source_status["berlin-traffic-detectors"] = FreshnessStatus.UNKNOWN
    _clear_source_error(state, "berlin-traffic-detectors")
    return result
