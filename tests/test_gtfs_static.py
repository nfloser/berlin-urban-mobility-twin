from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from berlin_mobility_twin.ingestion.gtfs_static import (
    GtfsIntegrityError,
    parse_gtfs_time,
    parse_gtfs_zip,
)


def build_gtfs(stop_id_in_times: str = "S1") -> bytes:
    files = {
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon,parent_station\n"
            "S1,Alexanderplatz,52.5219,13.4132,\n"
        ),
        "routes.txt": (
            "route_id,agency_id,route_short_name,route_long_name,route_type\n"
            "R1,VBB,U2,Pankow - Ruhleben,1\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id,trip_headsign,direction_id\n"
            "R1,WK,T1,Ruhleben,0\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            f"T1,25:10:00,25:10:30,{stop_id_in_times},1\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "WK,1,1,1,1,1,0,0,20260901,20261231\n"
        ),
        "calendar_dates.txt": "service_id,date,exception_type\nWK,20261003,2\n",
    }
    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buf.getvalue()


def test_gtfs_parser_loads_required_tables_and_diagnostics() -> None:
    dataset = parse_gtfs_zip(build_gtfs(), strict=True)

    assert dataset.stops["S1"].name == "Alexanderplatz"
    assert dataset.routes["R1"].short_name == "U2"
    assert dataset.trips["T1"].route_id == "R1"
    assert dataset.stop_times[0].arrival_seconds == 25 * 3600 + 10 * 60
    assert dataset.calendar["WK"].monday is True
    assert dataset.calendar_dates[0].exception_type == 2
    assert dataset.diagnostics.invalid_rows == 0


def test_gtfs_parser_rejects_missing_stop_reference() -> None:
    with pytest.raises(GtfsIntegrityError, match="unknown stop_id"):
        parse_gtfs_zip(build_gtfs(stop_id_in_times="MISSING"), strict=True)


def test_gtfs_time_allows_service_day_times_beyond_24_hours() -> None:
    assert parse_gtfs_time("25:10:30") == 90630


def test_gtfs_time_rejects_malformed_values() -> None:
    with pytest.raises(ValueError):
        parse_gtfs_time("25:70:00")
