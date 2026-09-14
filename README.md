# Berlin Urban Mobility Twin

A reproducible, explainable and test-driven research digital twin of Berlin's mobility system. The project integrates genuine public-transport, traffic-detector and disruption data while keeping provenance, freshness, quality and missing-data semantics explicit.

## Research motivation

Urban mobility data is heterogeneous: timetable data describes planned service, GTFS-Realtime describes only the realtime information currently published by operators, detector archives contain raw measurements that may include errors, and disruption feeds describe events rather than guaranteed network-edge effects. Treating these sources as one complete and perfectly current picture would be scientifically misleading.

This project therefore models an **observable mobility state** rather than an assumed ground truth. Every state is timestamped; unavailable, stale and unknown information stays visible; and no synthetic observation is inserted into production state to make the map appear complete.

## Objectives

The twin is designed to:

- ingest and validate VBB GTFS static schedules;
- ingest VBB GTFS-Realtime trip updates with feed-age/freshness semantics;
- ingest Berlin traffic-detector locations and explicitly mapped historical detector CSVs;
- ingest official Berlin roadworks, closures and relevant traffic disruptions;
- construct point-in-time `MobilitySnapshot` objects without future-data leakage;
- compute transparent transit, traffic and disruption analytics;
- expose versioned REST and machine-readable integration contracts;
- provide an interactive map that renders only actually available API data;
- degrade explicitly when sources are unavailable instead of substituting fake data.

## Data sources

| Source | Use | Licence |
| --- | --- | --- |
| VBB GTFS static | stops, routes, trips, stop times, service calendars | CC BY 4.0 |
| VBB GTFS-Realtime | current trip-update observations, delays/cancellations when published | CC BY 4.0 |
| Berlin Verkehrsdetektion detector locations | traffic-detector metadata and positions | dl-de-by-2.0 |
| Berlin Verkehrsdetektion archive | historical vehicle counts, speed and composition where present | dl-de-by-2.0 |
| Berlin traffic disruptions | roadworks, closures and relevant traffic events | dl-de-by-2.0 |

Exact URLs, retrieval behaviour, update information and known limitations are documented in [`docs/data-sources.md`](docs/data-sources.md).

## Architecture

```text
Authoritative providers
        |
        v
  ingestion adapters  ---- raw/source diagnostics
        |
        v
  typed domain models
        |
        +----> processing: temporal, spatial, quality, snapshots
        |
        +----> analytics: transit, traffic, baselines, disruptions
        |
        +----> integration contracts / JSON schemas
        |
        v
 versioned FastAPI  ----> browser map
```

HTTP/provider concerns are isolated in ingestion code. Core domain, processing and analytics code does not fetch remote resources directly. See [`docs/architecture.md`](docs/architecture.md).

## Installation

Python 3.11+ and Node.js 22 are used by CI.

```bash
python -m pip install -e ".[dev]"
cd frontend
npm ci
npm run build
cd ..
```

Copy `.env.example` only when configuration overrides are needed. The documented public sources require no repository secret.

## Run the system

Start the API without external retrieval:

```bash
berlin-mobility-twin serve
```

Retrieve supported public sources once and then serve:

```bash
berlin-mobility-twin serve --live
```

A provider failure leaves the service in a visible degraded state. It does not trigger a synthetic fallback.

After `frontend/dist` has been built, FastAPI serves the map at `http://localhost:8000/`. OpenAPI documentation is available at `http://localhost:8000/docs` and the schema at `/openapi.json`.

### Docker

```bash
docker compose up --build
```

The image builds and tests the frontend in a Node build stage and runs the Python API in a separate runtime stage.

## CLI

```bash
berlin-mobility-twin sources
berlin-mobility-twin refresh --snapshot snapshot.json
berlin-mobility-twin inspect-traffic-csv path/to/archive.csv --delimiter ";"
berlin-mobility-twin export-schemas --output-dir schemas
berlin-mobility-twin serve --live
```

Historical detector CSV semantics are **not guessed**. Inspect the real archive header first and use an explicit `TrafficCsvSchema` mapping in code/workflows consuming such files.

## API

Important endpoints include:

```text
GET /api/v1/health
GET /api/v1/sources
GET /api/v1/status
GET /api/v1/transit/stops
GET /api/v1/transit/routes
GET /api/v1/transit/trips
GET /api/v1/transit/state
GET /api/v1/traffic/detectors
GET /api/v1/traffic/state
GET /api/v1/disruptions
GET /api/v1/mobility/snapshot?at=<timezone-aware timestamp>
GET /api/v1/integration/mobility-snapshot
GET /api/v1/integration/network-disruptions
```

A missing GTFS-Realtime entity is not interpreted as an on-time service. It remains absent/unknown. Snapshot requests accept timezone-aware timestamps and internally use UTC.

## Analytics

Implemented analytics are deliberately transparent:

- delay distributions over observations with known delay values;
- service reliability for an explicit delay tolerance;
- observed headway deviation against an explicit scheduled headway;
- detector-level mean flow and speed over present measurements;
- historical same-detector/weekday/hour anomaly baselines without future leakage;
- active-disruption counts;
- metric-grid disruption concentration in EPSG:25833;
- mobility-state summaries using explicit counts rather than a composite score.

Definitions, inputs and limitations are in [`docs/methodology.md`](docs/methodology.md).

## Data integrity and time/space semantics

- Domain timestamps are timezone-aware; source-local Berlin times are resolved with explicit `Europe/Berlin` DST handling and normalised to UTC.
- External interchange uses EPSG:4326 unless a source states otherwise.
- Metric Berlin computations use EPSG:25833; distances are never computed directly from latitude/longitude degrees.
- Raw traffic rows are retained by the parser result; impossible values are rejected, suspicious values are warned, and questionable values are never silently repaired.
- Temporal detector gaps/non-monotonic source order can be annotated without changing measurements.
- Disruptions do not receive an affected network edge unless a real spatial matching step supports it; the current ingestion therefore leaves that field unresolved.

## Testing and quality gates

Local quality commands:

```bash
make lint
make format-check
make typecheck
make test
make frontend-test
make frontend-build
make quality
```

GitHub Actions repeats backend lint/format/type/test/schema checks, frontend tests/build, a Docker build and a non-blocking real-provider smoke job. See [`docs/testing.md`](docs/testing.md) for the distinction between mandatory deterministic gates and externally dependent smoke checks.

## Integration with the Berlin digital-twin ecosystem

The repository is intentionally a specialised mobility component rather than a monolithic urban platform. Versioned `MobilitySnapshot` and `NetworkDisruption` representations, accompanied by generated JSON Schemas, are designed for later consumption by projects such as the Berlin urban live/resilience twins and other domain-specific twins without importing this repository's internal classes.

See [`docs/integration.md`](docs/integration.md) and the committed schemas in [`schemas/`](schemas/).

## Visualisation

The frontend is a dependency-light browser application with API-backed layers for transit stops, detector locations and disruptions. It shows source/freshness/missing-data information and does not populate the map with demo observations.

No screenshot is committed at present because this repository does not yet contain a captured, provenance-verifiable real-data UI artefact. This avoids presenting a staged or synthetic screenshot as an observed result.

## Scientific limitations

This twin cannot be more complete than its source feeds. Realtime operator coverage can be incomplete, detector archives are raw observations, disruption feeds are not guaranteed to enumerate every local restriction, and the current project does not perform authoritative road-edge map matching. The analytics describe the available observations and must not be interpreted as a complete causal model of Berlin traffic.

See [`docs/limitations.md`](docs/limitations.md).

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/data-sources.md`](docs/data-sources.md)
- [`docs/data-model.md`](docs/data-model.md)
- [`docs/methodology.md`](docs/methodology.md)
- [`docs/testing.md`](docs/testing.md)
- [`docs/integration.md`](docs/integration.md)
- [`docs/limitations.md`](docs/limitations.md)

## Licence

Project source code is released under the MIT License. Upstream data remains subject to the licences and terms of its respective providers; those dataset licences are recorded separately in the source registry and documentation.
