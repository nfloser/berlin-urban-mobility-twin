# Data model

The primary domain model is typed with Pydantic. Provider dictionaries are accepted only at ingestion boundaries and are converted into explicit domain objects before processing or API export.

## Cross-cutting metadata

### `DataSource`
Describes a configured upstream dataset: identifier, provider, title, URL, licence, update frequency, temporal/spatial coverage and known limitations.

### `Provenance`
Tracks the origin of an observation: source/provider/title, timezone-aware retrieval and observation timestamps, URL/metadata reference, licence, optional schema version, freshness and source warnings.

### `DataQuality`
Stores warnings, severity (`info`, `warning`, `error`) and validity. Quality is not encoded by mutating the original measurement value.

### `DataAvailability`
Distinguishes scheduled, observed, realtime, historical, missing and unknown information.

### `FreshnessStatus`
Distinguishes fresh, stale, expired and unknown freshness.

## Transit

### `TransitStop`
GTFS stop identifier, name, WGS84 coordinates and optional parent station.

### `TransitRoute`
Route identifier, optional agency/short/long names and GTFS route type.

### `TransitTrip`
Trip identifier plus route, service, headsign and optional direction.

### `TransitObservation`
Timestamped realtime/observational state for a trip and optional stop. It can carry predicted arrival, delay and cancellation when the source actually supplies them. Missing values remain `None`; a missing realtime entity is not converted into a zero delay.

## Traffic

### `TrafficDetector`
Detector identifier, descriptive road/location/direction/lane metadata, operation date, coordinates, CRS and metadata provenance.

### `TrafficObservation`
Timestamped vehicle count, heavy-vehicle count and speed fields, each optional because availability depends on source schema. The model validates non-negative/range constraints and vehicle-composition consistency. Parsed source rows can be retained in `raw`.

## Disruptions

### `Disruption`
Identifier, category, description, validity interval, geometry, CRS, optional resolved network segment/matching confidence, provenance and quality.

The interval validator prevents an end before the start. Network matching is optional by design; textual road names are not sufficient evidence for an edge assignment.

## State

### `MobilitySnapshot`
A point-in-time collection of the latest known transit/traffic observations and active disruptions, plus source freshness, provider errors, missing sources and warnings. Snapshot construction excludes observations from the future relative to the requested timestamp.

## Stable integration models

### `MobilityStateRecord`
A language-neutral downstream record with domain, entity/location reference, timestamp, optional geometry, observation status, provenance, freshness, quality and transparent metrics.

### `IntegrationMobilitySnapshot`
Versioned export envelope containing timestamped mobility state records, network disruptions and source-health metadata.

### `NetworkDisruption`
Versioned downstream representation of a disruption containing temporal validity, spatial geometry/CRS, category, provenance, freshness, quality and optional confidence.

Generated JSON Schemas in `schemas/` are the contract artefacts for these integration models.

## Validation philosophy

Validation is intentionally conservative:

- impossible inputs are rejected;
- suspicious but plausible values can be retained with warnings;
- unavailable data remains absent/unknown;
- derived analytics operate on explicitly eligible subsets and expose sample sizes;
- production paths never generate synthetic observations to satisfy a model field.
