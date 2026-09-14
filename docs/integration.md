# Integration contract

The mobility twin is intended to be consumed by a wider Berlin Urban Intelligence Platform without requiring downstream repositories to import its internal implementation modules. Stable, versioned export models and JSON Schemas form that boundary.

## Contracts

### `IntegrationMobilitySnapshot`

A versioned envelope containing:

- `schema_version`;
- snapshot timestamp;
- mobility state records;
- normalised network disruptions;
- source freshness status;
- source retrieval/parse errors;
- missing required sources;
- human-readable warnings.

Each `MobilityStateRecord` includes:

- domain (`transit` or `traffic`);
- entity identifier;
- optional location reference;
- timezone-aware timestamp;
- optional GeoJSON-style Point geometry in EPSG:4326;
- observation availability/status;
- provenance;
- freshness;
- data-quality metadata;
- explicit metric fields in a transparent metric dictionary.

Transit geometry is resolved through stop metadata when a stop identifier is available. Traffic geometry is resolved through detector metadata. If location metadata cannot be resolved, geometry remains `null`; no coordinate is invented.

### `NetworkDisruption`

Contains:

- `schema_version`;
- disruption identifier;
- export timestamp;
- validity interval;
- description;
- geometry and CRS;
- normalised category;
- observation status;
- provenance;
- freshness;
- quality;
- optional confidence.

Confidence is only populated when a meaningful confidence exists. The current disruption adapter does not fabricate road-edge matching confidence.

## API endpoints

```text
GET /api/v1/integration/mobility-snapshot
GET /api/v1/integration/network-disruptions
```

Both support the same point-in-time semantics as the internal snapshot engine. The mobility-snapshot endpoint resolves known stop/detector geometry from the runtime metadata loaded with the state.

## JSON Schemas

Committed machine-readable schemas live in:

```text
schemas/mobility-snapshot.schema.json
schemas/network-disruption.schema.json
```

Regenerate them with:

```bash
berlin-mobility-twin export-schemas --output-dir schemas
```

CI performs schema-drift checking by regenerating the files and diffing them against the committed contracts.

## Versioning policy

The current integration schema version is `1.0.0`.

Downstream consumers should bind to the explicit schema rather than internal module layout. A future breaking change to required fields or semantics should increment the major schema version. Backwards-compatible optional additions should still be documented and schema-regenerated.

## Joining with other urban twins

Recommended downstream join dimensions are:

- UTC timestamp / requested snapshot time;
- WGS84 geometry where present;
- stable source/entity identifiers;
- provenance/source identifiers;
- explicit quality/freshness states.

Consumers should not discard `missing_sources`, `source_errors`, freshness or quality metadata before cross-domain analysis. A cross-domain model that uses an unknown/stale mobility state as if it were complete would defeat the transparency guarantees of this component.

## Non-coupling rule

Other twins should consume API/JSON-schema outputs rather than importing provider parsers, `RuntimeState`, or ingestion internals. This keeps source-provider changes local to the mobility repository and prevents coupling the wider platform to VBB/Berlin implementation details.
