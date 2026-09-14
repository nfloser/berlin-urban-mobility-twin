# Data sources and provenance

Source metadata is also available at `GET /api/v1/sources` and is defined centrally in `src/berlin_mobility_twin/ingestion/sources.py`.

## VBB GTFS static

- Provider: Verkehrsverbund Berlin-Brandenburg GmbH (VBB)
- Retrieval URL: `https://unternehmen.vbb.de/gtfs`
- Licence: CC BY 4.0
- Purpose: scheduled stops, routes, trips, stop times and service calendars
- Update information at source verification: twice weekly
- Spatial coverage: VBB service area, including Berlin and Brandenburg
- Temporal role: published schedule feed

The ingestion reads the GTFS tables actually used by this project: `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, `calendar.txt`, and `calendar_dates.txt` when present. Cross-table references are validated. Strict ingestion raises on broken references rather than silently discarding substantial invalid input.

GTFS service-day times beyond 24:00 are supported as elapsed service-day seconds and are not incorrectly parsed as civil wall-clock timestamps.

Known limitation: schedule data is planned service, not proof that a service actually operated as scheduled.

## VBB GTFS-Realtime

- Provider: Verkehrsverbund Berlin-Brandenburg GmbH (VBB)
- Retrieval URL: `https://production.gtfsrt.vbb.de/data`
- Licence: CC BY 4.0
- Purpose: current trip updates, predicted arrivals, delays and cancellations when published
- Freshness: evaluated from the feed header timestamp
- Spatial coverage: depends on contributing VBB operators and current feed coverage

The parser reports feed timestamp, retrieval timestamp, calculated feed age and freshness. A missing trip update is treated as **unknown realtime coverage**, never as evidence that the scheduled trip is on time.

At source verification on 2026-09-14, VBB reported limited realtime coverage dating from 2026-06-04. That limitation is recorded in the source registry and must be considered when interpreting network-wide realtime completeness.

The retrieval client sends an informative project `User-Agent` and follows redirects. Provider responses may be cached conditionally via ETag.

## Berlin traffic-detector locations

- Provider: Digitale Plattform Stadtverkehr Berlin
- Retrieval URL: `https://api.viz.berlin.de/daten/verkehrsdetektion/teu_standorte.json`
- Licence: dl-de-by-2.0
- Purpose: TEU detector identifiers, positions, directions/lanes and available metadata
- CRS: source geometry is treated as EPSG:4326
- Spatial coverage: Berlin detector network

The adapter follows the observed GeoJSON feature structure and validates Point geometry plus detector identifier. Location metadata and measurement observations remain distinct concepts.

## Berlin traffic-detector observations

- Provider: Digitale Plattform Stadtverkehr Berlin
- Archive entry point: `https://api.viz.berlin.de/daten/verkehrsdetektion`
- Licence: dl-de-by-2.0
- Purpose: historical detector observations such as vehicle counts, speed and composition where fields are actually present
- Temporal role: historical archive

The provider describes these measurements as raw data that may contain errors. The project therefore does **not** infer column meanings from a changing archive. `TrafficCsvSchema` is an explicit mapping supplied after inspecting the real source header.

Quality handling includes:

- raw row preservation;
- missing-value warnings;
- duplicate detector/timestamp rejection;
- impossible negative/count-composition values rejection;
- impossible speeds rejection;
- suspicious high-speed warning without altering the value;
- explicit DST validation for source-local timestamps;
- optional temporal gap and non-monotonic-order annotation.

Questionable observations are never silently repaired.

## Berlin road disruptions

- Provider: Digitale Plattform Stadtverkehr Berlin
- Retrieval URL: `https://api.viz.berlin.de/tic3/baustellen_sperrungen_tic.json`
- Licence: dl-de-by-2.0
- Purpose: published roadworks, closures and other traffic-relevant disruptions
- Temporal representation: source validity intervals
- Spatial coverage: Berlin city area

The current adapter normalises source identifiers, category, description, validity and GeoJSON geometry. Missing validity bounds become quality warnings.

This feed is not assumed to be a complete inventory of every restriction. The project also does not claim a disruption affects a particular network edge unless a real spatial network-matching method provides that evidence. `affected_network_segment` and matching confidence therefore remain unresolved when no such match exists.

## Provenance model

Observational models carry a `Provenance` object where technically meaningful. It contains:

- source identifier;
- provider;
- dataset title;
- retrieval timestamp;
- observation timestamp when available;
- source URL and optional metadata URL;
- licence;
- schema/version information when available;
- freshness status;
- source/quality warnings.

Downstream systems should preserve this metadata when joining mobility observations with other urban domains.
