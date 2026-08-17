# Hierarchical Confidence Ranking V3 Design

**Date:** 2026-08-17
**Status:** Approved architecture, pending written-spec review
**Scope:** Train and one-shot validation research only; no production selection,
orders, holdings, notifications, or investment-memory writes

## Problem Statement

The frozen V2 train diagnosis produced `NO_TRAIN_CANDIDATE`. This was not a
qualification-threshold false negative. The train evidence showed a structural
collapse before ranking:

- 19,920 evaluation plan rows entered the two train folds;
- 18,677 were removed before ranking;
- all 1,243 surviving rows belonged to
  `BREAKOUT_TRIGGER__STRUCTURE_ATR`, `FIRST_LAUNCH_PULLBACK`, and `LIMITED`;
- the survivors used only two calibration buckets, distinguished by sector
  resonance;
- K30 and K60 produced the same score percentiles, and all six BASE policies
  selected the same Top-3 plans;
- the hard-coded `STABLE_NEGATIVE` setup exclusion then removed every survivor;
- every sufficiently sampled profile/setup group had negative raw net
  expectancy in both train evaluation folds, apart from very small
  `PRE_BREAKOUT` samples.

The causal failure is therefore a policy-family mismatch with the evidence:
coarse calibration buckets and positive-edge hard gates collapse the candidate
cross-section, while within-date percentiles discard the magnitude changes
introduced by shrinkage. Weight changes cannot recover information that was
removed before ranking.

V3 must restore an auditable candidate cross-section without relaxing the
formal strategy acceptance thresholds or forcing trades.

## Goals

V3 must:

1. preserve the existing four execution profiles, entries, stops, five-session
   exits, costs, structure de-duplication, capacity admission, and no-backfill
   behavior;
2. use only fields already present in the canonical parent research artifact;
3. build all evidence point-in-time within each train fold;
4. replace single-bucket lookup with hierarchical partial pooling;
5. move uncertain calibration evidence from hard gating into a signed score;
6. hard-reject only sufficiently sampled, cross-window stable negative evidence;
7. register a small, interpretable set of eight policies rather than search a
   large parameter space;
8. permit zero to three daily selections through an absolute edge floor and a
   selection-boundary margin;
9. retain the V2 fold, sample, expectancy, Profit Factor, and rank-monotonicity
   acceptance standards;
10. fail closed when the policy family itself is not behaviorally distinct.

V3 does not promise a train winner, a validation pass, a production candidate,
or a profitable strategy. `NO_TRAIN_CANDIDATE` remains a valid result.

## Non-Goals

V3 does not:

- modify or reinterpret V1 or V2 code, registries, hashes, commands, or
  artifacts;
- add announcements, fund flow, new sector feeds, or any external data source;
- use setup-specific entries from `DetectedSetup.metrics` in the first cycle;
- change candidate discovery, execution profiles, costs, position sizing, or
  settlement;
- run automated parameter optimization or broad feature search;
- read validation or test outcomes during train diagnosis;
- install a schedule, send a notification, place an order, update holdings, or
  write personal or decision memory.

## Version and Isolation

V3 uses new identities rooted at:

- ranking version: `five-day-ranking-key-v3`;
- train schema: `five-day-ranking-v3-train-v1`;
- validation schema: `five-day-ranking-v3-validation-v1`;
- score formula version: `hierarchical-confidence-edge-v1`;
- feature version: `common-point-in-time-features-v1`;
- selection version: `absolute-edge-boundary-margin-v1`.

V3 lives in separate modules and a separate CLI. No V3 loader may accept a V1
or V2 artifact, and no existing artifact identity may change.

## Point-in-Time Train Flow

V3 retains the canonical 378/126/126 parent split and the two expanding train
folds:

- fold 1: 252 calibration sessions followed by 63 evaluation sessions;
- fold 2: 315 calibration sessions followed by 63 evaluation sessions.

For each fold:

1. include only observations whose signal date is in the calibration segment;
2. require the observation to be resolved before the first evaluation session;
3. build full-window and recent-window evidence;
4. define the recent window as the last 126 calibration sessions, or all
   available calibration sessions when fewer than 126 exist;
5. freeze hierarchy statistics, feature-bin boundaries, feature-bin effects,
   and policy inputs before reading fold evaluation outcomes;
6. rank fold evaluation plans from those frozen values;
7. admit selected plans through the existing capacity and no-backfill path;
8. score only selected, triggered, capacity-admitted, completed observations in
   official fold and combined metrics.

Validation and test dates are retained only as split identities. Their outcomes
must not enter any train statistic, threshold, feature boundary, or policy
choice.

## Hierarchical Evidence

Evidence is built independently for every execution profile. Outcomes from
different profiles are never pooled because their entries and stops differ.

The hierarchy is:

1. profile;
2. profile plus setup type;
3. profile plus setup type and market status;
4. profile plus setup type, market status, and sector resonance.

Each level records at least:

- resolved sample count;
- after-cost net expectancy;
- Profit Factor;
- profitable-rate Wilson interval;
- positive 63-session-window ratio;
- MAE p75;
- stop rate;
- data-end session.

### Recursive edge shrinkage

For policy shrinkage constant `k` and a child level with raw net expectancy
`e` and resolved samples `n`:

```text
w(n, k) = n / (n + k)
root_edge = w(root_n, k) * root_raw_edge
child_edge = w(child_n, k) * child_raw_edge
             + (1 - w(child_n, k)) * parent_edge
```

Missing child evidence inherits the parent value. A candidate requires at least
60 resolved full-window observations at the profile root. Otherwise it fails
the safety gate with `PROFILE_HISTORY_TOO_LOW`.

The recursive calculation is performed separately for the full and recent
windows. Let their root sample reliabilities be:

```text
r_full = n_full / (n_full + k)
r_recent = n_recent / (n_recent + k)
```

The candidate base edge is:

```text
E = (r_full * E_full + r_recent * E_recent) / (r_full + r_recent)
```

`E` remains in after-cost net-return units. It is not converted to an
in-date percentile.

## Stable-Negative Hard Gate

The V2 hard-coded sector and setup exclusions are removed. A candidate is
`STABLE_NEGATIVE` only when the deepest evidence level meeting the sample
requirements and its immediate parent both satisfy every condition below:

- at least 60 full-window resolved observations;
- at least 30 recent-window resolved observations;
- full and recent recursively shrunk net expectancy are both at most zero;
- full and recent Profit Factor are both available and at most `1.0`;
- the full-window profitable-rate Wilson upper bound is below `0.50`.

If no child level and parent both meet the sample requirements, the candidate
is uncertain rather than stably negative. It remains rankable with its signed
evidence. The profile root alone cannot trigger this hard gate because it has
no parent confirmation. This gate is evaluated only from the frozen
calibration window.

The remaining hard gates are unchanged safety requirements:

- complete point-in-time coverage;
- valid existing profile and stop resolution;
- existing liquidity eligibility;
- no active-structure conflict;
- calibration data end before signal date;
- profile-root history minimum.

Neither positive net expectancy nor Profit Factor above one is a pre-ranking
hard gate in V3.

## Common Plan Features

The first V3 experiment uses only common, point-in-time features with the same
meaning across setup types:

1. setup quality;
2. structure duration in trading sessions;
3. structure width, `(structure_high - structure_low) / structure_low`;
4. trigger gap, `(breakout_trigger - signal_close) / signal_close`;
5. effective entry-to-stop risk distance from the existing profile stop
   resolver;
6. resistance effective R, retaining a separate missing-level category;
7. log five-session average traded amount.

Market status and sector resonance already enter the evidence hierarchy and are
not counted again as independent feature adjustments. `anti_chase_passed` and
research share counts are eligibility facts, not score components.

### Calibration-only feature effects

For each continuous feature, full-window quintile boundaries are frozen before
fold evaluation. The recent window reuses those boundaries. The missing
resistance category is evaluated separately.

For a feature bin:

```text
raw_delta = bin_net_expectancy - profile_setup_parent_expectancy
shrunk_delta = n / (n + k) * raw_delta
```

The full and recent bin deltas must have the same non-zero sign. Otherwise the
feature contributes zero for that bin. A full bin requires at least 30 resolved
observations and a recent bin at least 15. Eligible full and recent deltas are
combined using the same reliability-weighted formula as the hierarchical edge.

Each feature contribution is clipped to `[-0.001, +0.001]`, equivalent to
`±0.10%` net return. The sum of all feature contributions is clipped to
`[-0.003, +0.003]`, equivalent to `±0.30%`. These limits prevent a sparse
univariate bin from overwhelming the hierarchical edge.

## Score Components

All components remain in net-return units.

### Consistency adjustment

```text
C = clip(min(E_full, E_recent), -0.001, +0.001)
```

This rewards a positive weakest window and penalizes a negative weakest window.

### Structure adjustment

`S` is the clipped sum of the seven calibration-only feature effects and lies
in `[-0.003, +0.003]`.

### Downside penalty

Let `stop_rate` and `mae_p75` be the reliability-weighted hierarchical values,
and let `risk_distance` be the effective entry-to-stop percentage. The
non-negative downside penalty is:

```text
D = clip(
      0.01 * max(stop_rate - 0.30, 0)
    + 0.10 * max(mae_p75 - 0.05, 0)
    + 0.05 * max(risk_distance - 0.05, 0),
    0,
    0.003
)
```

### Policy score

```text
score = E + consistency_weight * C
          + structure_weight * S
          - downside_weight * D
```

The score is an after-cost, risk-adjusted predicted edge. Deterministic
tie-breakers are, in order: higher base edge, higher weakest-window edge, lower
downside penalty, higher setup quality, normalized code, and profile identity.

## Eight Preregistered Policies

Four templates combine with `k in {30, 60}`:

| Template | Consistency weight | Structure weight | Downside weight |
| --- | ---: | ---: | ---: |
| `EDGE` | 0.50 | 0.50 | 0.50 |
| `CONSISTENCY` | 1.00 | 0.50 | 0.50 |
| `STRUCTURE` | 0.50 | 1.00 | 0.50 |
| `DOWNSIDE` | 0.50 | 0.50 | 1.00 |

The fixed identity order is:

1. `EDGE-K30`;
2. `EDGE-K60`;
3. `CONSISTENCY-K30`;
4. `CONSISTENCY-K60`;
5. `STRUCTURE-K30`;
6. `STRUCTURE-K60`;
7. `DOWNSIDE-K30`;
8. `DOWNSIDE-K60`.

The policy-set hash covers the ordered registry, hierarchy, formulas, feature
definitions, sample requirements, clipping values, absolute floor, boundary
margin, tie-breakers, and version strings.

## Daily Zero-to-Three Selection

After safety and stable-negative gates:

1. rank candidates by policy score;
2. collapse duplicate active structures using the existing structure identity;
3. remove candidates with score below `0.001`, or `+0.10%` predicted net edge;
4. set the provisional selection count to at most three;
5. if an unselected next candidate exists and the score difference at the
   selection boundary is below `0.001`, reduce the count by one and recheck the
   new boundary;
6. stop reducing at one; the first candidate needs the absolute floor but does
   not require a gap from the second candidate;
7. select zero when no candidate passes the absolute floor.

If there are no candidates beyond the provisional boundary, no boundary-margin
test is required. Later cancellation, non-trigger, active-structure conflict,
or capacity rejection never backfills a lower-ranked plan.

Top-1 and Top-5 remain diagnostic sensitivity variants. The formal policy uses
the zero-to-three selection above and existing capacity three.

## Policy-Family Diversity Gate

For each policy, construct one fingerprint from the ordered selected structure
keys in fold 1 and fold 2. The eight registered policies must produce at least
four distinct fingerprints.

If fewer than four fingerprints exist:

- the train review status is `POLICY_SET_DEGENERATE`;
- every policy is ineligible to win;
- validation eligibility is false;
- the artifact records the duplicate fingerprint groups.

This prevents a nominal parameter matrix from repeating the V2 behavior while
appearing to test independent hypotheses.

## Train Qualification and Winner

The formal zero-to-three policy must satisfy all requirements:

- fold 1 admitted completed samples at least 15;
- fold 2 admitted completed samples at least 15;
- fold 1 and fold 2 after-cost net expectancy both greater than zero;
- combined admitted completed samples at least 40;
- combined after-cost net expectancy at least `0.003` (`+0.30%`);
- combined Profit Factor greater than `1.10`;
- all rank bands have at least 15 triggered completed observations;
- rank monotonicity uses the existing `0.002` tolerance;
- admitted formal selections outperform rank 6-plus evidence;
- the policy-family diversity gate passes.

There is no unqualified fallback. Qualified policies are ordered by:

1. highest worst-fold net expectancy;
2. highest combined net expectancy;
3. highest combined admitted completed samples;
4. lowest combined maximum drawdown;
5. fixed policy identity order.

The first value is the unique train winner. If no policy qualifies, status is
`NO_TRAIN_CANDIDATE` and validation eligibility is false.

## Artifacts

### Train artifact

The immutable train artifact is named:

```text
ranking-v3-train-<artifact-identity>.json
```

It records:

- exact parent research identity and input fingerprint;
- split and fold boundaries, resolution cutoff, and excluded unresolved counts;
- formula, feature, policy, selection, metric, cost, sizing, and evaluator
  versions;
- all eight complete policy definitions and hashes;
- hierarchy and feature-bin sample summaries without raw observations;
- stable-negative and safety-gate rejection counts;
- Top-1, formal zero-to-three, and Top-5 metrics, portfolios, rank bands,
  funnels, and deterministic plan keys for each fold and combined train;
- policy fingerprints and duplicate groups;
- every policy qualification reason;
- the winner or terminal no-winner status;
- `validation_outcomes_read=false`, `test_outcomes_read=false`,
  `promotion_eligible=false`, and `trade_permission=NO-TRADE`.

### Validation artifact

Validation evaluates only the verified train winner and is named from the train
identity and winner policy hash. It cannot compare policies, change formulas,
or reuse a V1/V2 validation artifact. All hierarchy values, feature-bin
boundaries, feature effects, and score parameters are frozen from the 378 train
sessions recorded in the train artifact. Validation outcomes never recalibrate
or update them. Existing V2 formal validation thresholds remain unchanged.

Validation eligibility only permits a separately designed and approved test
stage. V3 has no test, freeze, forward, settlement, release, or production
command.

Writers are exclusive and byte-idempotent. Loaders recompute content hashes,
verify filenames and lineage, validate the current policy registry, reject raw
observation leakage, and fail closed on any mismatch.

## Manual CLI

The separate CLI is:

```text
scripts/analysis/analyze_five_day_ranking_v3.py
```

It exposes exactly:

- `diagnose-train --research-artifact ... --output-dir ...`;
- `validate-ranking --train-artifact ... --research-artifact ... --output-dir ...`.

Train diagnosis loads the canonical parent and writes only V3 train evidence.
Validation loads train first. A no-winner or degenerate train artifact returns
exit code 2 before loading the parent. A valid existing validation artifact is
strictly loaded and reused before the parent is read.

CLI failures print only:

```text
五日排名V3诊断失败
```

No dependency detail, path content, credential, observation, holding, or memory
value may be exposed by the CLI error boundary.

## Error Handling and Fail-Closed Reasons

At minimum, V3 must represent and test:

- `PROFILE_HISTORY_TOO_LOW`;
- `CALIBRATION_NOT_POINT_IN_TIME`;
- `STABLE_NEGATIVE`;
- `ABSOLUTE_EDGE_TOO_LOW`;
- `BOUNDARY_MARGIN_TOO_LOW`;
- `POLICY_SET_DEGENERATE`;
- fold and combined sample failures;
- non-positive fold expectancy;
- combined edge and Profit Factor failures;
- rank-band sample and monotonicity failures;
- parent lineage or input-fingerprint mismatch;
- policy registry, formula, feature, or selection version mismatch;
- existing artifact byte conflict;
- validation requested without one verified winner.

No error condition may silently fall back to V2, relax a threshold, or force a
selection.

## Testing

Implementation follows TDD and includes:

1. recursive root/child shrinkage, missing-child inheritance, and K30/K60
   boundary behavior;
2. full/recent window cutoffs and exclusion of outcomes resolving on or after
   fold evaluation start;
3. stable-negative parent/child agreement, every boundary, and uncertain-bucket
   pass-through;
4. common feature derivation from signal-time values only;
5. feature-bin freezing, sign disagreement suppression, minimum samples, single
   `±0.10%` cap, and total `±0.30%` cap;
6. consistency and downside formulas at exact Decimal boundaries;
7. exact eight-policy registry, hashes, formula identity, and tie-breakers;
8. zero-to-three selection, structure collapse, absolute floor, iterative
   boundary reduction, and no backfill;
9. fingerprint diversity pass and degenerate-family rejection;
10. admitted-only official metrics and separate rank-band diagnostics;
11. train thresholds, winner ordering, and no-winner behavior;
12. immutable writer idempotency, tamper rejection, lineage enforcement, and
    raw-observation exclusion;
13. CLI command surface, train-first validation short circuit, existing
    validation reuse, conflict preservation, and sanitized failures;
14. unchanged V1 and V2 artifact identities and complete relevant regression
    suites.

## Acceptance Run

After implementation and regression verification:

1. run only V3 `diagnose-train` against the same canonical parent used by V2;
2. strictly load and verify the generated train artifact;
3. report universe retention, hierarchy coverage, stable-negative exclusions,
   policy fingerprints, Top-1/formal/Top-5 metrics, fold metrics, rank bands,
   and all qualification reasons;
4. compare V3 descriptively with V1 and V2;
5. prove byte idempotency and absence of later-stage artifacts or staged
   research output;
6. stop without running validation.

If and only if one unique policy qualifies, request explicit user confirmation
before `validate-ranking`. A train winner is research evidence, not a stock
recommendation or permission to trade.
