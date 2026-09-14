# Methodology

The project favours transparent descriptive and baseline analytics over opaque mobility scores. Every implemented metric is defined below with inputs and limitations.

## Transit delay distribution

Input: `TransitObservation` values with known `delay_seconds`.

Unknown delays are excluded rather than imputed as zero. The output exposes the number of eligible observations, unknown observations, mean, median, minimum and maximum delay.

For known delays \(d_1, ..., d_n\):

\[
\bar d = \frac{1}{n}\sum_{i=1}^{n} d_i
\]

Limitation: the distribution describes only realtime observations actually published and ingested. It is not a complete distribution for all scheduled VBB services when realtime coverage is incomplete.

## Service reliability

Input: observations with known delays and an explicit non-negative tolerance \(T\) in seconds.

\[
R(T)=\frac{\#\{i: |d_i| \le T\}}{n_{known}}
\]

The result exposes the tolerance, eligible count, unknown count, numerator and rate. No universal tolerance is asserted by the project; callers must choose one appropriate to their research question.

## Observed headway deviation

Input: timezone-aware observed event times and an explicit scheduled headway \(H > 0\).

For ordered observed times \(t_i\):

\[
h_i=t_i-t_{i-1}, \qquad \Delta_i=h_i-H
\]

The output contains the raw observed headways and each deviation. It does not infer a scheduled headway from incomplete realtime observations.

## Detector traffic summary

Input: a collection of `TrafficObservation` objects.

Vehicle-count and speed means are calculated independently over fields that are actually present. Their sample sizes are returned separately. Missing values do not become zeros.

\[
\bar q = \frac{1}{n_q}\sum q_i, \qquad
\bar v = \frac{1}{n_v}\sum v_i
\]

Limitation: the result inherits detector/source measurement quality and is not a network-wide flow estimator.

## Historical detector anomaly

Input: one current detector observation plus historical observations and a minimum sample threshold.

Eligible baseline observations must have:

- the same detector identifier;
- a timestamp strictly before the evaluated observation;
- the same weekday;
- the same UTC hour;
- a known vehicle count.

Future observations are excluded by construction.

When the baseline sample is large enough:

\[
\Delta=q_{current}-\bar q, \qquad
\Delta_{rel}=\frac{\Delta}{\bar q}\quad(\bar q\ne0)
\]

and, when population standard deviation \(\sigma>0\):

\[
z=\frac{q_{current}-\bar q}{\sigma}
\]

The result is marked unavailable when the configured minimum sample count is not met. This is a transparent statistical comparison, not a trained anomaly model.

Limitation: matching by UTC hour is reproducible but may not perfectly correspond to local civil-time behavioural periods across DST seasons. Research using long seasonal windows should consider an explicit local-time baseline design.

## Active disruption count

Input: disruptions and a timezone-aware analysis timestamp \(t\).

A disruption is active when:

\[
(valid\_from \le t \text{ or missing}) \land (valid\_until \ge t \text{ or missing})
\]

The result reports total supplied disruptions and active count. Missing validity bounds are also represented by source-quality warnings during ingestion.

## Spatial disruption concentration

Input: active disruption geometries, timestamp and positive grid size \(g\) metres.

1. Select active disruptions.
2. Compute each usable geometry centroid.
3. Project centroid coordinates from EPSG:4326 to EPSG:25833.
4. Assign projected points to square grid cells of side length \(g\).
5. Let \(m\) be the largest cell count and \(n\) the number of eligible active geometries.

\[
C_g=\frac{m}{n}
\]

The output also exposes active, eligible and excluded geometry counts, grid size, maximum cell count and CRS. `None` is returned when no geometry is eligible.

Limitations: the metric is grid-origin and grid-size dependent and uses geometric centroids, not affected road length or population exposure. It is a spatial concentration descriptor, not an impact score.

## Mobility-state summary

Input: one `MobilitySnapshot`.

The summary returns explicit counts of transit observations, traffic observations, active disruptions, records with quality warnings, source freshness categories, missing sources and source errors. No weighted composite mobility-health score is produced.

## Traffic temporal-quality annotation

Input: detector observations plus an expected interval in seconds.

The process flags:

- source-order non-monotonic timestamps for the same detector;
- gaps where consecutive sorted observations differ by more than the configured interval.

Warnings are added to copied quality metadata. Measurement values are not interpolated, reordered in the source record, or repaired.

## Snapshot temporal integrity

Point-in-time snapshots include only information whose observation timestamp is not later than the requested snapshot time. This prevents future observations from leaking into retrospective state or anomaly evaluation.

## Spatial calculations

External location exchange uses EPSG:4326. All implemented metric distance/grid calculations first transform to EPSG:25833; latitude/longitude degrees are never treated as metres.
