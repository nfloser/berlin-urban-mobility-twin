import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from berlin_mobility_twin.api.state import RuntimeState
from berlin_mobility_twin.ingestion.http_client import FetchResult
from berlin_mobility_twin.processing.pipeline import load_gtfs_static, refresh_berlin_road_sources


def gtfs() -> bytes:
    files = {
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nS1,Alexanderplatz,52.5219,13.4132\n",
        "routes.txt": "route_id,route_short_name,route_long_name,route_type\nR1,U2,Pankow - Ruhleben,1\n",
        "trips.txt": "route_id,service_id,trip_id\nR1,WK,T1\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT1,10:00:00,10:00:30,S1,1\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWK,1,1,1,1,1,0,0,20260101,20261231\n",
    }
    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buf.getvalue()


class StubClient:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses

    def fetch(self, url: str, *, etag: str | None = None) -> FetchResult:
        del etag
        return FetchResult(
            url=url,
            status_code=200,
            retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
            content=self.responses[url],
            content_type="application/json",
            etag=None,
        )


def test_load_gtfs_static_populates_only_real_schedule_entities() -> None:
    state = RuntimeState()
    diagnostics = load_gtfs_static(state, gtfs())
    assert [stop.stop_id for stop in state.stops] == ["S1"]
    assert [route.route_id for route in state.routes] == ["R1"]
    assert diagnostics.invalid_rows == 0


def test_refresh_berlin_road_sources_populates_detectors_and_disruptions() -> None:
    detector_url = "https://api.viz.berlin.de/daten/verkehrsdetektion/teu_standorte.json"
    disruption_url = "https://api.viz.berlin.de/tic3/baustellen_sperrungen_tic.json"
    detectors = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"teuID": "D1", "Position": "A100"},
                "geometry": {"type": "Point", "coordinates": [13.4, 52.5]},
            }
        ],
    }
    disruptions = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "X1",
                    "subtype": "Sperrung",
                    "validity": {"from": "14.09.2026 00:00", "to": "15.09.2026 00:00"},
                    "content": "gesperrt",
                },
                "geometry": {"type": "Point", "coordinates": [13.41, 52.51]},
            }
        ],
    }
    state = RuntimeState()
    refresh_berlin_road_sources(
        state,
        StubClient(
            {
                detector_url: json.dumps(detectors).encode(),
                disruption_url: json.dumps(disruptions).encode(),
            }
        ),
    )
    assert state.traffic_detectors[0].detector_id == "D1"
    assert state.disruptions[0].disruption_id == "X1"
    assert state.traffic_observations == []
