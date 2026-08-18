# V3 Ranking Component Attribution Design

**Date:** 2026-08-18
**Status:** Approved conversational design, pending written-spec review
**Scope:** Train-only diagnosis; no ranking change, strategy promotion, trading,
holding, notification, or investment-memory side effect

## Problem

The canonical V3 market-and-strategy attribution artifact completed all 87,168
required intervals, but its rank diagnosis does not yet identify which score
component causes weak ordering.

The first aggregate reading also exposed two interpretation problems:

1. The reported 39 `RANKER_INVERTED` variants are not 39 independent rankers.
   The same policy-and-fold diagnosis is repeated under `FORMAL`, `TOP_1`, and
   `TOP_5`. After removing that presentation duplication, there are 24 unique
   policy-and-fold diagnoses: all eight policies are inverted in fold 1, all
   eight are labelled healthy in fold 2, and the combined results contain five
   inverted and three mixed policies.
2. Fold 2's healthy label is mean-sensitive. Rank 1 beats Rank 2-3 by about
   0.22% on the mean raw paired difference, but the median paired difference is
   about -0.82%, the daily win ratio is 43.75%, and the mean cross-sectional
   Spearman correlation remains negative. A small number of large winners can
   therefore make the current mean-based verdict look healthier than the
   typical date.

The evidence is consistent with temporal instability, an unhelpful score
component, or both. It does not justify reversing the whole score, changing
weights, or weakening the existing V3 qualification gates.

## Objective

Build one immutable, aggregate-only, train-only component-attribution artifact
that answers:

- whether base edge, consistency, feature structure, or downside penalty is
  associated with later five-session returns;
- whether removing consistency, feature structure, or downside penalty
  improves same-date ranking robustly in both train folds;
- whether an apparent improvement is stable across folds or is a regime
  reversal;
- which single component, if any, is sufficiently suspect to justify a
  separate follow-on V3 redesign.

The artifact is diagnostic evidence only. It cannot select a production
strategy, modify V3, read validation or test outcomes, or emit a buy decision.

## Non-Goals

This work must not:

- change the V3 score, policies, weights, hard gates, entries, stops, costs,
  capacity, or winner rules;
- search new weights, thresholds, feature subsets, or arbitrary component
  combinations;
- remove or invert base edge in this experiment;
- run V3 validation, one-shot test, forward screening, settlement, or trading;
- use holdings, orders, advisor memory, decision memory, notifications, or the
  forbidden Eastmoney AI eight-dimensional framework;
- persist stock codes, plan keys, dates, observation rows, positions, or
  credentials;
- declare a component causal merely because it is correlated with returns.

## Selected Architecture

Use a standalone component-attribution pipeline rather than changing the V3
artifact or adding fields to the existing market-attribution artifact. The
pipeline contains:

1. a pure domain module that reconstructs signed score components, reranks a
   fixed candidate pool, calculates same-date component correlations and
   baseline-versus-ablation metrics, and assigns descriptive labels;
2. a strict report module that writes and loads one canonical aggregate-only
   artifact;
3. a manual CLI that verifies the complete parent chain, loads bounded
   train-only market data, builds the diagnosis, writes one artifact, and
   stops.

An ad-hoc script is rejected because its results would not be identity-bound or
strictly reproducible. Extending V3 directly is rejected because it would
change an already frozen experiment before the diagnosis identifies a root
cause.

## Inputs and Lineage

The CLI accepts exactly:

- the canonical V3 train artifact;
- its canonical parent five-day research artifact;
- the canonical completed V3 market-and-strategy attribution artifact;
- one output directory;
- configured read-only access to the bounded market data already required by
  the existing attribution pipeline.

Before market access, it must verify:

- every artifact identity and filename;
- the Research-to-V3 parent identity and input fingerprint;
- the V3-to-market-attribution parent identities and market-data fingerprint;
- current V3 policy registry and score-formula versions;
- `validation_outcomes_read=false`, `test_outcomes_read=false`,
  `promotion_eligible=false`, and `trade_permission=NO-TRADE` throughout the
  parent chain;
- `status=COMPLETE` and full interval coverage in the parent attribution;
- only the two V3 train evaluation folds can contribute outcomes.

A lineage failure stops before MySQL or benchmark access.

## Frozen Score Decomposition

For each existing scored plan, reconstruct the signed components under its
registered policy:

```text
E = hierarchical evidence edge
C* = consistency_weight * consistency
S* = structure_weight * feature_adjustment
D* = -downside_weight * downside

baseline_score = E + C* + S* + D*
```

The reconstruction must equal the persisted V3 score exactly under the frozen
decimal arithmetic. Any mismatch produces `SCORE_RECONSTRUCTION_FAILED` and no
component verdict.

The component-correlation section reports the same-date cross-sectional
Spearman relationship of `E`, `C*`, `S*`, and `D*` with:

- fixed-five raw return;
- matched-index excess return;
- same-universe market-median excess return.

At least five finite candidate outcomes are required on a date. Persist only
date counts and aggregate mean/median correlations.

## Preregistered Experiments

Run exactly four score formulas for every policy and fold:

```text
BASELINE = E + C* + S* + D*
WITHOUT_CONSISTENCY = E + S* + D*
WITHOUT_STRUCTURE = E + C* + D*
WITHOUT_DOWNSIDE = E + C* + S*
```

No other subset or weight is permitted. Base edge remains in every formula and
is treated as the required reference signal, not as an ablation candidate.

Each experiment uses the exact same scored plans, signal dates, fixed-five
endpoints, benchmark values, and coverage exclusions. Selection mode is not an
experiment dimension because the underlying ranking is identical under
`FORMAL`, `TOP_1`, and `TOP_5`. Results are unique by policy and fold.

## Deterministic Reranking and Comparability

`BASELINE` must reproduce the persisted V3 ordinal ranks exactly. A mismatch
produces `BASELINE_REPRODUCTION_FAILED`.

For an ablation, sort first by its experimental score and then only by the
canonical plan identity. Do not reuse any V3 economic tie-breaker, because
base-edge, weakest-window, downside, or setup-quality tie-breaks could leak an
ablated component back into the order. Plan identities remain in memory and
are forbidden in the output; persist only aggregate tie counts.

If an exact-score tie crosses the Rank 1 or Rank 2-3 evaluation boundary, that
policy-and-fold experiment is `BOUNDARY_TIE_INCONCLUSIVE`; it must not receive
a helpful or harmful label. This prevents an arbitrary identity order from
being interpreted as economic evidence.

Before comparing an ablation with baseline, require exact equality of:

- candidate count;
- eligible fixed-five outcome count;
- excluded coverage count;
- paired date set in memory;
- benchmark fingerprint.

Persist only the counts and fingerprints. Any mismatch produces
`COMPARABILITY_FAILED`.

## Same-Date Rank Metrics

For each policy, fold, and experiment, compute:

- paired dates where Rank 1 and at least one Rank 2-3 outcome both exist;
- Rank 1 minus median Rank 2-3 raw, index-excess, and market-excess differences;
- mean and exact median of each paired difference;
- Rank 1 daily win ratio and its Wilson interval;
- eligible and completed correlation dates;
- mean and exact median daily Spearman correlation for raw and both excess
  targets.

The Wilson endpoint identities remain exact: zero wins have lower bound zero,
and all wins have upper bound one.

Fold 1 and fold 2 are the decision units. A combined-train section may be
reported for description, but it cannot override disagreement between folds.

## Component Effect Deltas

For each ablation, calculate `ablation - baseline` on the same policy and fold
for every rank metric. Positive deltas mean removing the component improved the
metric.

The core robust direction vector is:

- median raw Rank-1 paired difference;
- Rank-1 daily win ratio;
- mean raw cross-sectional Spearman correlation.

The two benchmark safeguards are:

- mean matched-index-excess paired difference;
- mean market-median-excess paired difference.

Report all delta magnitudes without rounding them into a binary result. There
is no optimized materiality threshold in this train-only diagnostic.

## Descriptive Labels

Each fold requires at least 30 paired dates and at least 30 completed
correlation dates. Otherwise its comparison is `INCONCLUSIVE`.

For a component ablation:

- `CONSISTENTLY_HARMFUL`: in both folds, all three core deltas are strictly
  positive and both benchmark-safeguard deltas are non-negative;
- `CONSISTENTLY_HELPFUL`: in both folds, all three core deltas are strictly
  negative and both benchmark-safeguard deltas are non-positive;
- `REGIME_UNSTABLE`: one fold has an all-positive core direction while the
  other has an all-negative core direction, or one fold meets the harmful
  direction and the other meets the helpful direction;
- `INCONCLUSIVE`: samples are insufficient, a boundary tie exists, metrics
  conflict, or none of the rules above is met.

Equality is neutral, not evidence of improvement. These labels identify a
candidate for a later redesign; they do not authorize a score change.

## Artifact Contract

The canonical filename is:

```text
ranking-v3-component-attribution-<artifact_identity>.json
```

The artifact contains only:

- schema and component-attribution version;
- Research, V3, and market-attribution parent identities and fingerprints;
- frozen policy registry hash and score-formula identity;
- train split identity and aggregate market coverage;
- unique policy-and-fold experiment metrics;
- component correlations, ablation deltas, tie counts, and descriptive labels;
- a descriptive combined-train section;
- explicit safety flags.

It must contain:

```text
train_only=true
validation_outcomes_read=false
test_outcomes_read=false
promotion_eligible=false
trade_permission=NO-TRADE
```

Stock codes, plan keys, dates, observation rows, positions, and credentials are
forbidden recursively. JSON is canonical, compact, content-addressed, written
exclusively or verified byte-identical, and strictly loaded by filename,
identity, schema, exact keys, parent chain, registries, arithmetic identities,
and safety flags.

## Failure States

The pipeline fails closed with one sanitized aggregate status:

- `LINEAGE_INVALID` before market access;
- `SCORE_RECONSTRUCTION_FAILED` when persisted scores cannot be reproduced;
- `BASELINE_REPRODUCTION_FAILED` when original ranks cannot be reproduced;
- `MARKET_DATA_INCOMPLETE` when the existing dual-benchmark contract fails;
- `COMPARABILITY_FAILED` when an ablation changes the evaluation population;
- `COMPLETE` when every required aggregate is valid.

`BOUNDARY_TIE_INCONCLUSIVE` is an experiment result, not an artifact failure,
because other policies and folds can remain comparable. No failure may be
converted to zero or silently excluded.

## Testing

### Pure domain tests

- reconstruct each registered policy score exactly;
- prove the four and only four experiment formulas;
- prove a removed component cannot leak through ablation tie-breaks;
- prove deterministic ordering and boundary-tie detection;
- prove same-date pairing, median, win ratio, Wilson, and Spearman arithmetic;
- prove the four component labels, equality neutrality, and minimum samples.

### Full-builder tests

- prove selection-mode duplication is removed;
- prove every experiment shares the same candidate and outcome population;
- reject score, rank, policy registry, split, fingerprint, or coverage drift;
- ensure combined results cannot override cross-fold conflict;
- ensure no validation or test outcome is accessed.

### Report tests

- canonical byte identity and idempotent writes;
- strict parent-chain and arithmetic validation;
- rejection of old schemas, renamed files, tampering, extra keys, NaN,
  Infinity, and non-canonical decimals;
- recursive rejection of codes, dates, plan keys, rows, holdings, orders, and
  credentials.

### CLI tests

- lineage validation occurs before database or benchmark access;
- market reads remain bounded to train dates;
- errors are sanitized and produce no partial artifact;
- the command cannot import or invoke validation, test, forward, settlement,
  advisor, notification, memory, holding, or order flows.

## Real-Data Acceptance

After unit and integration tests pass, run the manual CLI once against the
current frozen parent identities. Acceptance requires:

- strict load of Research, V3, parent attribution, and component attribution;
- complete bounded market coverage;
- exact baseline rank reproduction for all 16 unique policy-and-fold units;
- comparable populations for all 48 fold-level ablations;
- a second identical run with the same path and file SHA-256;
- aggregate-only reporting with no security identifiers or daily rows;
- no generated file staged in Git.

The real run may validly conclude that all components are inconclusive or
regime-unstable. It must not be tuned until one component looks harmful.

## Follow-On Boundary

If one component is `CONSISTENTLY_HARMFUL`, a new design may replace or remove
that component and rerun train diagnosis under a new ranking version. If none
is consistently harmful, the next design should compare genuinely different
public-strategy challengers rather than continue adjusting V3 weights. Neither
follow-on is part of this design.
