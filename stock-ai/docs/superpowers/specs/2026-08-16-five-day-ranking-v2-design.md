# Five-Day Ranking V2 Conservative Edge Design

## Goal

Design a second, isolated ranking research chain that can identify zero to
three credible five-day buy points per signal day. V2 must first demonstrate
positive after-cost expectancy in both chronological train folds and a
meaningful relationship between rank and future return. It must not change
candidate discovery, entry, stop, cost, holding period, daily capacity, or any
production selector.

The current `five-day-ranking-key-v1` remains immutable evidence. V2 uses new
policy, artifact, and CLI identities and cannot overwrite or silently promote
V1 results.

## Evidence Behind the Design

The corrected V1 train artifact
`ranking-train-d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3.json`
shows:

- combined global Top-3 expectancy of approximately `-0.51%` per admitted
  trade and Profit Factor `0.75`;
- negative global Top-3 expectancy in both 63-session evaluation folds;
- no stable return monotonicity between Rank 1, Rank 2-3, and Rank 4-5;
- only 50 admitted completed trades from 315 global Top-3 selections;
- persistent train-only loss attribution in stopped trades, non-resonating
  sectors, and `FIRST_LAUNCH_PULLBACK` candidates.

The immediate problem is therefore ranking quality and abstention, not a lack
of candidate volume. V2 must repair those two concerns without broad search or
simultaneous changes to execution rules.

## Confirmed Decisions

- Primary objective: positive after-cost Top-3 expectancy in both train folds,
  with basic return monotonicity by rank.
- Scope: change ranking and pre-ranking elimination only.
- Search budget: exactly twelve preregistered candidate policies.
- Selection cardinality: zero to three structures per day; never fill a quota
  with a lower-quality candidate.
- Hard exclusions: only a small, fixed set of train-supported and signal-time
  observable conditions.
- Validation: at most one immutable validation trial for the unique train
  winner, after a separate explicit user confirmation.
- Validation failure cannot be used to retune and reread the same segment.

## Non-Goals

V2 does not:

- change setup detection, candidate discovery, entries, stops, costs,
  five-session holding semantics, Top-3 capacity, or `TWO_R`;
- add current-stock recommendations, order placement, holdings writes,
  schedules, notifications, or advisor-memory writes;
- use Eastmoney stock diagnosis or the deprecated Eastmoney eight-dimension
  framework;
- introduce machine learning or unconstrained parameter search;
- run validation, freeze, test, forward screening, or settlement as part of
  implementation acceptance;
- consume the test segment at any stage in this design.

## Architecture

V2 is a separate research path with five bounded layers.

Keep those responsibilities in three new components:

- `five_day_ranking_v2.py`: pure policy registry, feature projection,
  eligibility, percentile scoring, structure collapse, ranking, fold
  evaluation, monotonicity assessment, and unique-winner selection;
- `five_day_ranking_v2_report.py`: canonical payloads, lineage hashes,
  exclusive writers, strict loaders, and validation-trial identity;
- `analyze_five_day_ranking_v2.py`: the two-command manual CLI and no other
  runtime surface.

The pure ranking component consumes existing `FiveDaySignalPlan`,
`FiveDayCalibration`, and `FiveDayObservation` values. The report component
consumes only completed V2 review values. The CLI composes existing immutable
parent loaders with the two V2 components; neither library component performs
database, network, notification, holdings, memory, or order I/O.

### 1. Point-in-Time Feature Projection

For each signal-date plan, project only fields known at the signal time:

- calibration sample count and after-cost net expectancy;
- calibration profitable-rate Wilson lower bound;
- calibration positive-window ratio, MAE p75, and stop rate;
- market status, sector resonance, and resistance basis;
- setup quality and the existing liquidity eligibility result;
- setup type, profile identity, structure identity, and deterministic plan key.

No observation outcome from the candidate being scored may enter its score or
eligibility decision.

### 2. Conservative Edge and Eligibility

For calibration sample count `n` and shrinkage constant `k`, calculate:

```text
shrinkage_weight = n / (n + k)
shrunk_edge = shrinkage_weight * calibration.net_expectancy
```

`k` is fixed per policy and can only be `30` or `60`.

Every policy applies the same base eligibility gates:

- the existing calibration resolver returns at least its current minimum
  sample count;
- calibration data ends before the signal date;
- `shrunk_edge > 0`;
- calibration Profit Factor is available and greater than `1.0`;
- the existing liquidity, point-in-time coverage, and structure eligibility
  checks pass.

Failure of any gate removes the plan before ranking. An empty day is a valid
abstention result.

### 3. Optional Stable-Negative Exclusions

Each policy has one of two fixed gate modes:

- `BASE`: apply only the common eligibility gates;
- `STABLE_NEGATIVE`: also reject a plan when either:
  - `sector_resonating is False`; or
  - `setup_type == FIRST_LAUNCH_PULLBACK`.

Unknown sector resonance is not treated as false. No additional loss bucket
may be discovered and added during the twelve-policy trial.

### 4. Deterministic Composite Ranking

After gating, compute seven component percentiles within each signal date.
For a beneficial raw value `x` among `m` plan variants:

```text
percentile(x) =
    0.5,                                            when m == 1
    (count(worse) + 0.5 * count(equal_except_self)) / (m - 1), otherwise
```

For MAE and stop rate, lower raw values are better. Equal raw values receive
the same percentile. The seven components are:

1. higher `shrunk_edge`;
2. higher Wilson lower bound;
3. higher positive-window ratio;
4. lower MAE p75;
5. lower stop rate;
6. higher observable context score;
7. higher setup quality.

The context raw score is the mean of three fixed sub-scores:

- market: `1` for `ALLOW`, otherwise `0`;
- sector: `1` for resonating, `0.5` for unknown, `0` for false;
- resistance: `1` for a level at or above 2R, `0.5` for no reliable level,
  and `0` for a level below 2R.

The weighted component sum produces a score from zero to one hundred. Score
all eligible plan variants first, then retain only the highest-scoring profile
variant for each existing active-structure key. Rank the surviving structures
by:

1. composite score descending;
2. shrunk edge descending;
3. setup quality descending;
4. normalized stock code ascending;
5. profile identifier ascending.

Select at most three structures. A later cancellation or failure to trigger
does not backfill a lower-ranked structure. Average trading amount remains an
eligibility input but is not a V2 return-score component.

## The Twelve Preregistered Policies

V2 has three weight templates:

| Template | Edge | Wilson | Positive windows | Low MAE | Low stop rate | Context | Setup quality |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `EDGE` | 35 | 20 | 15 | 10 | 10 | 5 | 5 |
| `BALANCED` | 25 | 20 | 15 | 15 | 15 | 5 | 5 |
| `DOWNSIDE` | 20 | 20 | 10 | 20 | 20 | 5 | 5 |

Each template combines with `k in {30, 60}` and gate mode in
`{BASE, STABLE_NEGATIVE}`. The fixed identity order is:

1. `EDGE-K30-BASE`
2. `EDGE-K30-STABLE_NEGATIVE`
3. `EDGE-K60-BASE`
4. `EDGE-K60-STABLE_NEGATIVE`
5. `BALANCED-K30-BASE`
6. `BALANCED-K30-STABLE_NEGATIVE`
7. `BALANCED-K60-BASE`
8. `BALANCED-K60-STABLE_NEGATIVE`
9. `DOWNSIDE-K30-BASE`
10. `DOWNSIDE-K30-STABLE_NEGATIVE`
11. `DOWNSIDE-K60-BASE`
12. `DOWNSIDE-K60-STABLE_NEGATIVE`

The policy-set hash covers this ordered list, every weight, formula, gate,
tie-breaker, and version. Changing any of them creates a different experiment
and cannot reuse V2 validation identity.

## Train Evaluation

Use the existing immutable parent, exact 378-session train segment, and two
expanding folds:

- Fold 1: sessions 1-252 calibrate; sessions 253-315 evaluate.
- Fold 2: sessions 1-315 calibrate; sessions 316-378 evaluate.

Calibration observations must resolve before the evaluation fold begins.
Candidate outcomes from validation or test cannot enter any train metric.

Every policy is evaluated using the shared no-backfill selection and capacity
admission path. Official metrics use only selected, triggered, capacity-
admitted trades with a completed entry and exit. Cancelled, not-triggered,
missing, pending, incomplete, overflow, and capacity-rejected rows remain in
the funnel only.

Top 3 is the only selectable policy. Top 1 and Top 5 are descriptive
sensitivity diagnostics and cannot win the search.

### Minimum Train Evidence

A candidate requires:

- at least 15 admitted completed trades in each fold;
- at least 40 admitted completed trades across both folds;
- complete selection and observation coverage in both folds.

### Rank Monotonicity

Rank monotonicity is a separate train-only diagnostic. It uses scored plans
with a triggered and completed observation, including plans below Top 3, so it
can evaluate ranks that would not be admitted. Those rows cannot enter the
official portfolio-return metrics.

Pool both evaluation folds and form `RANK_1`, `RANK_2_3`, `RANK_4_5`, and
`RANK_6_PLUS`. Each band must have at least 15 triggered completed samples.
With tolerance `0.002` in decimal return units, require:

```text
expectancy(RANK_1) + 0.002 >= expectancy(RANK_2_3)
expectancy(RANK_2_3) + 0.002 >= expectancy(RANK_4_5)
official_admitted_top3_expectancy > expectancy(RANK_6_PLUS)
```

Failure or insufficient band evidence rejects the candidate.

### Train Qualification and Unique Winner

A policy is train-qualified only when all conditions hold:

1. Fold-1 official Top-3 expectancy is greater than zero.
2. Fold-2 official Top-3 expectancy is greater than zero.
3. Combined official Top-3 expectancy is at least `0.003`.
4. Combined official Top-3 Profit Factor is greater than `1.10`.
5. Minimum train evidence is satisfied.
6. Rank monotonicity is satisfied.

If multiple candidates qualify, choose one lexicographically by:

1. larger worst-fold expectancy;
2. larger combined expectancy;
3. larger combined admitted completed sample count;
4. smaller combined maximum drawdown;
5. earlier fixed policy identity.

If none qualify, record `NO_TRAIN_CANDIDATE`. Do not change thresholds or
candidate definitions and do not create validation eligibility.

## Immutable V2 Evidence

Use new schema, report, metric, policy-set, and ranking versions rooted at
`five-day-ranking-key-v2`. V1 artifacts and commands remain unchanged.

The train artifact records:

- exact parent research identity, input fingerprint, split, and lineage;
- all twelve policy definitions and the policy-set hash;
- fold calibration/evaluation boundaries and resolution cutoffs;
- Top-1/3/5 metrics, portfolios, rank bands, funnels, and deterministic plan
  keys for every policy and fold;
- every qualification failure reason;
- the unique train winner or `NO_TRAIN_CANDIDATE`;
- `validation_outcomes_read=false`, `test_outcomes_read=false`,
  `promotion_eligible=false`, and `trade_permission=NO-TRADE`.

Raw observations stay in the immutable parent. Writers are exclusive and
byte-idempotent; loaders recompute content and lineage hashes and fail closed
on any mismatch.

## One-Shot Validation

V2 uses a separate manual CLI with exactly two stages: `diagnose-train` and
`validate-ranking`. It does not extend or reinterpret the V1 CLI.

`validate-ranking` is callable only when the verified train artifact contains
one unique winner. Before reading the parent research artifact, derive the
validation filename from the train identity and winning-policy hash. A valid
existing artifact is returned without rereading validation outcomes; a
conflicting artifact is rejected without overwrite.

Validation evaluates only the frozen winner. It cannot compare the other
eleven candidates or change any weight, shrinkage value, gate, Top-N value, or
capacity. Existing formal thresholds remain unchanged:

- validation admitted completed trades at least 30;
- train plus validation samples at least 70;
- after-cost expectancy greater than zero;
- Profit Factor greater than `1.10`;
- profitable-rate Wilson lower bound at least `0.45`;
- stop rate at most `0.40`;
- positive-window ratio at least `0.60`;
- maximum drawdown at most `0.10`;
- maximum stock trade share at most `0.10`;
- maximum stock profit share at most `0.15`;
- maximum sector trade share at most `0.35`;
- maximum sector profit share at most `0.40`;
- Top-5 profit share at most `0.35`.

A validation pass grants eligibility for a separately approved test-stage
design only. It does not freeze, release, recommend, or trade the strategy.
Validation failure ends this V2 trial; it cannot justify tuning and rereading
the same validation segment.

## Failure Handling and Safety

Fail closed when:

- parent identity, input fingerprint, split, policy-set hash, or version does
  not match;
- point-in-time coverage is incomplete or a calibration resolves too late;
- validation or test outcomes are marked read at an earlier stage;
- any official return metric contains a non-selected, non-triggered,
  capacity-rejected, missing, pending, or incomplete trade;
- a policy definition differs from the fixed twelve-policy registry;
- an existing immutable identity has different bytes;
- a loader or CLI error could expose observations, database URLs, credentials,
  holdings, or personal memory.

No eligible candidates on a date is a valid empty selection, not a runtime
error.

## Testing and Acceptance

Implementation follows TDD and covers:

- shrinkage formula and zero/boundary behavior;
- beneficial and inverse percentile calculation, equality, and one-row days;
- context-score mapping and deterministic ties;
- base eligibility and both gate modes;
- profile-variant collapse by active structure;
- zero-to-three selection and no backfill;
- exact twelve-policy registry, identity order, and hash stability;
- fold cutoffs and exclusion of outcomes resolving at or after evaluation
  start;
- admitted-only official metrics and separate rank-band diagnostics;
- minimum samples, tolerance-based monotonicity, train gates, and winner
  ordering;
- `NO_TRAIN_CANDIDATE` with no validation eligibility;
- exclusive, byte-stable writers and tamper-rejecting loaders;
- validation pre-read reuse and single-winner enforcement;
- sanitized CLI errors and absence of database/network/write side effects;
- unchanged V1 ranking artifacts, costs, entries, stops, profiles, and existing
  five-day regression suites.

Implementation acceptance may run only V2 `diagnose-train` against the exact
immutable parent. It must stop for user review before V2 validation.
