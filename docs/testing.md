# Testing and quality assurance

## Test strategy

The repository was developed incrementally with Red → Green → Refactor commits for meaningful capabilities. Deterministic tests do not require live provider availability.

Coverage includes:

- typed domain validation;
- GTFS static parsing and reference integrity;
- GTFS service-day times beyond 24:00;
- malformed/missing references;
- GTFS-Realtime freshness, cancellation and unknown-coverage semantics;
- official-shape detector and disruption parsing fixtures;
- traffic missing/duplicate/impossible/suspicious values;
- Berlin DST gaps/ambiguous local times;
- CRS projection and metric distance behaviour;
- point-in-time snapshots without future observations;
- traffic temporal gaps/non-monotonic source order;
- delay/reliability/headway/detector analytics;
- historical anomaly leakage prevention;
- disruption/state analytics;
- API/OpenAPI/status behaviour;
- integration transformations and JSON snapshot persistence;
- HTTP metadata/ETag behaviour;
- frontend data-state/rendering helpers.

Synthetic values are used only in tests/fixtures and are explicitly isolated there. They are never loaded as production observations.

## Local quality gate

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src/berlin_mobility_twin
pytest --cov=berlin_mobility_twin --cov-report=term-missing
cd frontend && npm ci && npm test && npm run build
```

The same operations are available through `make` targets.

## CI

`.github/workflows/ci.yml` executes mandatory deterministic jobs on pushes to `main` and pull requests:

### Backend

1. fresh checkout;
2. Python 3.11 setup;
3. editable install with development dependencies;
4. Ruff lint;
5. Ruff formatting check;
6. strict mypy;
7. pytest with branch-aware coverage collection;
8. regenerate integration JSON schemas and compare them with committed schemas.

Any failure in these steps fails the mandatory backend job.

### Frontend

1. fresh checkout;
2. Node.js 22 setup;
3. `npm ci`;
4. Node test runner;
5. deterministic production build.

### Docker

The Docker image is built only after mandatory backend and frontend jobs succeed. The Dockerfile itself repeats frontend test/build in its build stage and then installs the Python package in the runtime stage.

### Real-data smoke job

The live smoke test is intentionally separated from deterministic correctness gates because external providers can be unavailable or rate-limited independently of repository quality. It retrieves real public source endpoints and parses them rather than using fixtures. The CI job is marked `continue-on-error` so a provider outage does not falsely classify deterministic code as broken.

A live-smoke failure must still be inspected and reported as an external/data-adapter issue; it must never cause fake fallback data to be generated.

## Schema drift

`berlin-mobility-twin export-schemas --output-dir ...` regenerates the stable integration schemas. CI compares generated output to `schemas/`. A code change that alters the contract without updating the committed schema therefore fails the backend job.

## Fresh-clone reproducibility

CI is the canonical fresh-clone check: every job starts from `actions/checkout` on a clean hosted runner and installs dependencies from repository configuration before running gates. Docker provides an additional isolated build path.

## Quality principles

- Never describe a gate as passed unless its command was executed.
- Do not make live services the only test path for an adapter.
- Do not weaken lint/type rules to hide implementation errors.
- Preserve explicit unknown/missing states in assertions.
- Treat source-data plausibility and software correctness as separate questions.
