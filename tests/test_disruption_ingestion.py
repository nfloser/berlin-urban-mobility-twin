from datetime import UTC, datetime

from berlin_mobility_twin.domain.models import DisruptionCategory
from berlin_mobility_twin.ingestion.disruptions import parse_disruptions


def payload() -> dict:
    return {
        "type": "FeatureCollection",
        "name": "baustellen",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "LMS-BR/example",
                    "tstore": "2026-09-07T04:00:00.443Z",
                    "objectState": "modified",
                    "subtype": "Sperrung",
                    "icon": "sperrung",
                    "severity": None,
                    "validity": {
                        "from": "07.09.2026 06:00",
                        "to": "19.09.2026 23:59",
                    },
                    "street": "Berlin, Nordufer zwischen Föhrer Brücke und Buchstraße",
                    "section": "Berlin, Nordufer zwischen Föhrer Brücke und Buchstraße",
                    "content": "gesperrt, Baustelle",
                },
                "geometry": {
                    "type": "GeometryCollection",
                    "geometries": [
                        {"type": "Point", "coordinates": [13.34514, 52.53909]},
                        {
                            "type": "LineString",
                            "coordinates": [[13.34514, 52.53909], [13.34566, 52.53903]],
                        },
                    ],
                },
            }
        ],
    }


def test_disruption_parser_uses_official_fields_and_local_validity_timezone() -> None:
    result = parse_disruptions(
        payload(),
        retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_url="https://api.viz.berlin.de/tic3/baustellen_sperrungen_tic.json",
    )

    disruption = result.disruptions[0]
    assert disruption.disruption_id == "LMS-BR/example"
    assert disruption.category is DisruptionCategory.CLOSURE
    assert disruption.valid_from == datetime(2026, 9, 7, 4, 0, tzinfo=UTC)
    assert disruption.geometry["type"] == "GeometryCollection"
    assert disruption.affected_network_segment is None
    assert disruption.network_match_confidence is None


def test_missing_validity_is_explicit_not_fabricated() -> None:
    data = payload()
    data["features"][0]["properties"]["validity"] = {"from": "", "to": ""}

    result = parse_disruptions(
        data,
        retrieved_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        source_url="https://api.viz.berlin.de/tic3/baustellen_sperrungen_tic.json",
    )

    disruption = result.disruptions[0]
    assert disruption.valid_from is None
    assert disruption.valid_until is None
    assert "missing validity start" in disruption.quality.warnings
    assert "missing validity end" in disruption.quality.warnings
