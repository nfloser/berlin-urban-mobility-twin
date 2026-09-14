from datetime import UTC, datetime

from berlin_mobility_twin.ingestion.traffic import (
    TrafficCsvSchema,
    parse_detector_locations,
    parse_traffic_csv,
)


def test_detector_location_parser_matches_official_geojson_shape() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "teuID": "TEU00002_Det0",
                    "Position": "A115",
                    "Location": "AS Spanische Allee – Brücke",
                    "Direction": "Südwest",
                    "Start of Operation": "2003-02-18",
                    "Lane": "Hauptfahrbahn rechte Spur",
                },
                "geometry": {"type": "Point", "coordinates": [13.19257, 52.43386]},
            }
        ],
    }

    detectors = parse_detector_locations(
        payload,
        retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_url="https://api.viz.berlin.de/daten/verkehrsdetektion/teu_standorte.json",
    )

    assert detectors[0].detector_id == "TEU00002_Det0"
    assert detectors[0].road == "A115"
    assert detectors[0].longitude == 13.19257
    assert detectors[0].crs == "EPSG:4326"


def schema() -> TrafficCsvSchema:
    return TrafficCsvSchema(
        detector_id="detector",
        timestamp="timestamp",
        vehicle_count="count",
        heavy_vehicle_count="heavy",
        speed_kmh="speed",
        delimiter=";",
        timestamp_format="%Y-%m-%d %H:%M:%S",
        source_timezone="Europe/Berlin",
    )


def test_traffic_csv_preserves_raw_rows_and_separates_rejected_values() -> None:
    csv_payload = (
        "detector;timestamp;count;heavy;speed\n"
        "D1;2026-01-15 10:00:00;100;10;42.5\n"
        "D1;2026-01-15 11:00:00;-1;0;40\n"
    ).encode()

    result = parse_traffic_csv(
        csv_payload,
        schema=schema(),
        retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_url="https://api.viz.berlin.de/daten/verkehrsdetektion",
    )

    assert len(result.raw_rows) == 2
    assert len(result.observations) == 1
    assert len(result.rejected_rows) == 1
    assert "negative vehicle count" in result.rejected_rows[0].reasons
    assert result.observations[0].observed_at.tzinfo is not None


def test_duplicate_detector_timestamp_is_not_silently_kept_twice() -> None:
    csv_payload = (
        "detector;timestamp;count;heavy;speed\n"
        "D1;2026-01-15 10:00:00;100;10;42\n"
        "D1;2026-01-15 10:00:00;101;10;43\n"
    ).encode()

    result = parse_traffic_csv(
        csv_payload,
        schema=schema(),
        retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_url="https://api.viz.berlin.de/daten/verkehrsdetektion",
    )

    assert len(result.observations) == 1
    assert any("duplicate observation" in reason for reason in result.rejected_rows[0].reasons)


def test_suspicious_speed_is_retained_with_quality_warning_not_repaired() -> None:
    csv_payload = (
        "detector;timestamp;count;heavy;speed\n"
        "D1;2026-01-15 10:00:00;100;10;180\n"
    ).encode()

    result = parse_traffic_csv(
        csv_payload,
        schema=schema(),
        retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_url="https://api.viz.berlin.de/daten/verkehrsdetektion",
    )

    observation = result.observations[0]
    assert observation.speed_kmh == 180
    assert "suspicious speed > 160 km/h" in observation.quality.warnings


def test_traffic_csv_rejects_nonexistent_berlin_dst_timestamp() -> None:
    csv_payload = (
        "detector;timestamp;count;heavy;speed\n"
        "D1;2026-03-29 02:30:00;100;10;42\n"
    ).encode()

    result = parse_traffic_csv(
        csv_payload,
        schema=schema(),
        retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_url="https://api.viz.berlin.de/daten/verkehrsdetektion",
    )

    assert result.observations == []
    assert "does not exist" in result.rejected_rows[0].reasons[0]
