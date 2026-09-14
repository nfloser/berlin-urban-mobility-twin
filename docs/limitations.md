# Limitations

This document separates software guarantees from limitations of observational coverage and research interpretation.

## Source completeness

The twin represents the data that authoritative providers publish; it does not infer missing observations.

### Public transport realtime

GTFS-Realtime coverage depends on contributing operators and the current VBB feed. The absence of a trip update is not evidence of an on-time trip. Network-wide reliability estimates may therefore be biased toward services for which realtime information is available.

At the source verification date (2026-09-14), VBB reported limited realtime coverage dating from 2026-06-04. This warning is recorded in the source registry.

### Traffic detectors

The Berlin detector archive contains raw measurements and may include source measurement errors. Detector coverage is spatially selective and cannot be treated as a complete observation of all Berlin road traffic.

Archive CSV layouts are not assumed stable. This project requires explicit field mapping after inspecting source headers rather than guessing semantics. Consequently, the generic live refresh does not pretend to automatically ingest an unknown historical archive schema.

### Disruptions

The official published disruption dataset is not assumed to contain every restriction on every Berlin road. The current project normalises event geometry and validity but does not maintain an authoritative road-network edge graph for matching.

`affected_network_segment` and matching confidence remain empty unless a real matching process can support them. Street text alone is not treated as proof of network-edge impact.

## Temporal limitations

The system resolves Berlin-local timestamps through `Europe/Berlin` and stores comparable values in UTC. Ambiguous autumn timestamps require an explicit fold when the source provides no offset. This prevents silent ambiguity but means a source with genuinely ambiguous local timestamps cannot be automatically disambiguated without additional evidence.

The anomaly baseline groups historical observations by UTC weekday/hour for reproducibility. Around DST seasons, this is not identical to matching local civil hour. Long-horizon behavioural studies may need a deliberately local-time baseline.

## Spatial limitations

External interchange and source geometries use EPSG:4326; metric computations use EPSG:25833.

The implemented spatial disruption-concentration measure is based on geometry centroids and a configurable square metric grid. Results depend on grid size/origin and do not measure affected road length, traffic exposure, population exposure or causal impact.

## Analytics limitations

The project implements descriptive and transparent comparative analytics, not a causal traffic model and not a network simulator.

- Delay/reliability metrics include only observations with known delay values.
- Headway deviation requires observed event times plus an explicit scheduled headway; it does not reconstruct missing services.
- Detector summaries are detector-level statistics, not network flow estimates.
- Anomaly z-scores assume the selected historical reference sample is meaningful; no distributional normality claim is made.
- Mobility-state summaries are counts, not a weighted health index.

No model accuracy or benchmark performance is claimed because this repository does not implement a predictive ML model requiring such evaluation.

## Runtime/state limitations

`RuntimeState` is an in-process state container suitable for this research software and API demonstration. It is not a distributed event store. JSON snapshot persistence is provided for reproducible state artefacts, but high-volume production streaming/storage infrastructure is outside current scope.

The default live refresh retrieves supported current public sources once; it is not a continuously scheduled ingestion daemon.

## UI limitations

The map visualises API-backed data available in the current runtime. It does not fabricate route conditions, speeds or station observations to fill empty areas. A sparse/empty layer can therefore be the correct visual output when no corresponding data has been loaded.

The interface is an inspection/research UI, not a passenger journey planner or operational traffic-control application.

## External-service availability

Real-data smoke tests depend on external network access and provider availability. Deterministic CI uses schema-faithful fixtures so repository correctness is testable during provider outages. A failed external smoke test must be investigated but must not be hidden by synthetic fallback observations.

## Scope

This repository is one mobility component intended for a wider Berlin digital-twin ecosystem. Environmental exposure, energy forecasting, urban heat, socioeconomic effects and resilience routing belong in their respective domain twins or later integration layers rather than being duplicated here.
