from __future__ import annotations

from berlin_mobility_twin.domain.models import DataSource

VERIFIED_ON = "2026-09-14"

SOURCES: tuple[DataSource, ...] = (
    DataSource(
        source_id="vbb-gtfs-static",
        provider="Verkehrsverbund Berlin-Brandenburg GmbH",
        dataset_title="VBB GTFS static",
        source_url="https://unternehmen.vbb.de/gtfs",
        licence="CC BY 4.0",
        update_frequency="2x weekly (German VBB dataset page, verified 2026-09-14)",
        temporal_coverage="published schedule feed",
        spatial_coverage="VBB service area (Berlin and Brandenburg)",
        limitations=["schedule data may contain errors or be incomplete per VBB disclaimer"],
    ),
    DataSource(
        source_id="vbb-gtfs-rt",
        provider="Verkehrsverbund Berlin-Brandenburg GmbH",
        dataset_title="VBB GTFS Realtime",
        source_url="https://production.gtfsrt.vbb.de/data",
        licence="CC BY 4.0",
        update_frequency="realtime feed; freshness evaluated from feed header timestamp",
        temporal_coverage="current realtime feed",
        spatial_coverage="VBB service area; coverage depends on contributing operators",
        limitations=[
            "absence of a realtime entity does not imply on-time operation",
            "VBB reported limited realtime coverage from 2026-06-04 at verification time",
        ],
    ),
    DataSource(
        source_id="berlin-traffic-detector-locations",
        provider="Digitale Plattform Stadtverkehr Berlin",
        dataset_title="Standorte der Verkehrsdetektion in Berlin",
        source_url="https://api.viz.berlin.de/daten/verkehrsdetektion/teu_standorte.json",
        licence="dl-de-by-2.0",
        update_frequency="not specified by source metadata",
        temporal_coverage="detector metadata",
        spatial_coverage="Berlin; more than 240 detector locations described by portal",
        limitations=["location metadata is distinct from archived detector observations"],
    ),
    DataSource(
        source_id="berlin-traffic-detectors",
        provider="Digitale Plattform Stadtverkehr Berlin",
        dataset_title="Verkehrsdetektion Berlin",
        source_url="https://api.viz.berlin.de/daten/verkehrsdetektion",
        licence="dl-de-by-2.0",
        update_frequency="archived hourly observations",
        temporal_coverage="historical archive by detector and period",
        spatial_coverage="Berlin; more than 240 detector locations described by portal",
        limitations=[
            "source describes records as raw data that may contain measurement errors",
            "archive CSV column mapping must be inspected/configured rather than guessed",
        ],
    ),
    DataSource(
        source_id="berlin-road-disruptions",
        provider="Digitale Plattform Stadtverkehr Berlin",
        dataset_title=(
            "Baustellen, Sperrungen und sonstige Störungen von besonderem verkehrlichem Interesse"
        ),
        source_url="https://api.viz.berlin.de/tic3/baustellen_sperrungen_tic.json",
        licence="dl-de-by-2.0",
        update_frequency="hourly granularity in Berlin Open Data metadata",
        temporal_coverage="current/published validity intervals",
        spatial_coverage="Berlin city area",
        limitations=[
            "not a complete inventory of all traffic restrictions",
            "Berlin Open Data currently describes two parallel disruption datasets",
            "network-edge effects require spatial matching and are not inferred from text alone",
        ],
    ),
)

SOURCE_BY_ID = {source.source_id: source for source in SOURCES}
