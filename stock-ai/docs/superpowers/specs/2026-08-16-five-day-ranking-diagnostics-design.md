# Five-Day Ranking Diagnostics and Metric Consistency Design

## Goal

Correct the five-day research evaluation so every return and risk metric
describes the trades the strategy would actually select and admit, then add a
train-only diagnostic workflow that determines whether ranking, entry, stops,
or market and sector filters explain the current failure to qualify.

This work repairs the evaluation ruler before changing the strategy. It does
not add ranking factors, relax promotion thresholds, recommend current stocks,
run `freeze` or `test`, or enable trading.

## Observed Problem

The complete research artifact
`research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
contains 57,848 observations, covers 2,449 stocks and 373 signal dates, reports
`point_in_time_complete=true`, and leaves `test_outcomes_read=false`.

The production ranking path already performs calibration eligibility checks,
deduplicates active structures, limits each signal date to the top three
plans, and admits no more than three concurrently active research positions.
However, `_segment_metrics_from_observations(...)` currently calculates net
expectancy, Profit Factor, profitable-rate Wilson bounds, stop rate, and
positive-window ratio from every resolved observation for a profile. Only
maximum drawdown and concentration use the ranked and capacity-admitted
portfolio.

The resulting validation report mixes all-candidate statistics with actual
Top-3 portfolio statistics. It therefore cannot answer whether the stocks the
strategy would really select have positive five-day returns.

## Selected Approach

Use a layered, auditable research workflow:

1. create one shared selection result for ranking, Top-N truncation, entry
   triggering, and portfolio-capacity admission;
2. calculate every promotion metric from the admitted trades in that result;
3. run Top-1, Top-3, Top-5, rank-band, and loss-attribution diagnostics only on
   chronological train folds;
4. preregister the existing ranking key with daily Top 3 as the only validation
   policy;
5. allow one immutable validation artifact for that preregistered policy;
6. preserve every prior artifact as retrospective evidence and record every
   new trial without overwrite.

### Rejected alternatives

- **Metric correction only:** small but leaves no evidence about whether
  ranking, entry, stops, or filters cause losses.
- **Rewrite ranking immediately:** adds factors before diagnosing the current
  ranking and increases backtest-overfitting risk.
- **Choose Top N from validation:** converts validation into an optimization
  set and invalidates its confirmatory role.

## Architecture

### Raw observation layer

Existing candidate discovery, the four fixed entry/stop profiles, execution
simulation, costs, five-day outcomes, and raw observations remain unchanged.
The new workflow references an immutable base research artifact by identity
and input fingerprint rather than copying or modifying it.

### Shared selection layer

The validation module gains one shared portfolio-selection operation that
accepts plans, observations, frozen calibrations, a daily limit, active
structure identities, and a capacity limit. It returns a typed selection
result containing:

- eligible and rejected plan counts by reason;
- daily deterministic rank and rank position;
- duplicate-structure and daily-limit rejections;
- selected plans that never triggered or were cancelled;
- selected plans with completed entries and exits;
- capacity-admitted observations;
- capacity rejections;
- unresolved or missing-observation evidence.

The operation keeps current ranking semantics. It does not backfill a lower
ranked candidate when an earlier selected plan later fails to trigger, because
that future information was unavailable at selection time.

`build_five_day_portfolio_metrics(...)`, segment evaluation, train diagnostics,
and validation diagnostics all consume this same result. No consumer may
reimplement ranking or admission locally.

### Metric-consistency layer

All strategy-performance metrics use only capacity-admitted observations with
an actual entry and completed exit:

- triggered/resolved sample count;
- average net return;
- gross profit, gross loss, and Profit Factor;
- profitable rate and Wilson interval;
- stop rate;
- 63-session positive-window ratio;
- maximum drawdown;
- stock and sector trade concentration;
- stock and sector profit concentration;
- top-five profit share.

Discovery, eligibility, ranking, trigger, cancellation, unresolved, and
capacity counts remain funnel diagnostics. They are never added to the return
denominator. Promotion sample thresholds also count admitted trades, not all
resolved candidates.

Per-profile validation selects a daily Top 3 inside that profile to determine
whether the profile qualifies. The combined validation portfolio then ranks
across only the qualifying profiles, deduplicates structures globally, applies
the same daily Top 3 and capacity-three rules, and evaluates concentration.

### Diagnostic research layer

A focused diagnostic module produces two views from train only:

1. **Per-profile:** each of the four profiles under daily Top 1, Top 3, and
   Top 5.
2. **Global:** all profiles compete under the current ranking key, with global
   structure deduplication, under daily Top 1, Top 3, and Top 5.

It also emits:

- selection-funnel counts and rates;
- rank bands 1, 2-3, 4-5, and 6-plus;
- setup type;
- market `ALLOW` or `LIMITED` state;
- sector resonance;
- resistance evidence;
- setup-quality bands;
- calibration-expectancy bands;
- entry and stop profile;
- `STOPPED`, `TIME_EXIT_LOSS`, `TIME_EXIT_GAIN`, cancellation, and
  not-triggered attribution;
- gross-to-net cost drag.

Top-N and bucket outputs are descriptive research evidence. They cannot
qualify a profile or alter the preregistered validation policy in this version.

## Chronological Train Research

The existing split remains exactly 378 train, 126 validation, and 126 test
signal sessions. The test segment remains unread.

The 378 train sessions use an expanding walk-forward design:

- sessions 1-252 form the first calibration window;
- sessions 253-315 form diagnostic fold 1;
- sessions 316-378 form diagnostic fold 2;
- fold 2 calibration may include fold-1 observations only when their outcomes
  resolved before the first signal date of fold 2.

For each fold, calibrations are frozen before the fold starts. A calibration
must have `data_end` earlier than every signal it ranks. Observations whose
resolution date is not earlier than the fold boundary cannot enter that fold's
calibration. This prevents overlapping five-day outcomes from leaking across
the boundary.

The two 63-session folds are reported separately and combined. A result that
works in only one fold is marked unstable. No train diagnostic result gains
promotion authority.

## Validation Preregistration

The only validation policy in this design is:

```text
ranking key: current deterministic calibration/market/sector/resistance/
             quality/liquidity key
daily limit: 3
active capacity: 3
profile matrix: existing four fixed profiles
metric version: selected-portfolio-v2
```

Top 1 and Top 5 are not eligible for validation selection. Factor buckets do
not change the ranking key. A train diagnostic artifact embeds this policy and
its hash before any corrected validation metrics are produced.

Validation retains the existing strict gates:

- at least 30 admitted validation trades per profile;
- at least 70 admitted train-evaluation plus validation trades;
- positive net expectancy;
- Profit Factor greater than 1.10;
- profitable-rate 95% Wilson lower bound at least 45%;
- stop rate no greater than 40%;
- at least 60% positive 63-session windows;
- maximum drawdown no greater than 10%;
- existing combined stock, sector, and top-five concentration limits.

The corrected result may remain unqualified. No threshold is relaxed and no
candidate is padded to force promotion.

## Manual Stages

A new analysis-only CLI is isolated from the existing five-stage research CLI.
It exposes exactly two manual stages.

### `diagnose-train`

Consumes a complete base research artifact, verifies its identity and
`test_outcomes_read=false`, projects train observations, runs the two expanding
folds, and writes an immutable train diagnostic artifact. It does not calculate
validation returns.

### `validate-ranking`

Consumes one train diagnostic artifact and its referenced base research
artifact. It verifies the preregistered policy and writes one immutable
corrected validation artifact. It does not call `freeze`, read test outcomes,
or alter the train artifact.

Implementation acceptance runs `diagnose-train` first and stops for user
review. `validate-ranking` requires a later explicit confirmation.

## Artifacts and Trial Ledger

Artifacts use a new schema family and deterministic identities:

```text
ranking-train-<identity>.json
ranking-validation-<identity>.json
```

Identity inputs include:

- base research artifact identity and input fingerprint;
- split dates and fold boundaries;
- profile-matrix, ranking-policy, and selection-policy hashes;
- daily and capacity limits;
- cost, sizing, execution, metric, and report versions;
- exact diagnostic variants;
- preregistered validation-policy hash.

Each artifact contains aggregate metrics, funnel counts, selected plan
identities, admitted trade identities, rejection reasons, and its parent
identity. Raw observations remain in the base research artifact to avoid a
second multi-million-line copy.

Artifacts are write-once. An identical rerun verifies and reuses existing
bytes without recalculating validation. A different payload under an existing
identity is an error. The immutable artifact directory is the complete trial
ledger; no mutable summary file or new MySQL table is introduced.

## Versioning and Compatibility

The evaluator and metric identity advance to `selected-portfolio-v2` because
the semantic population of every segment metric changes. Existing research
artifacts remain readable for retrospective comparison but are not eligible as
corrected evidence.

Future `freeze` input must explicitly require the corrected evaluator identity
and a matching immutable validation artifact. This implementation does not run
or create a freeze artifact.

## Error Handling

- Future-dated calibration: fail the trial and write no complete artifact.
- Missing selected-plan observation: mark the selection incomplete and prohibit
  validation qualification.
- Pending or unresolved selected trade at cutoff: count it explicitly and
  prohibit qualification until the bounded outcome is available.
- Cancelled or not-triggered selected plan: preserve funnel evidence but exclude
  it from trade-return metrics.
- Capacity rejection: preserve the selected-plan identity and rejection reason
  but exclude it from portfolio returns.
- Insufficient calibration or admitted samples: fail closed with explicit
  reason codes.
- Empty train result: valid diagnostic artifact, but no validation permission.
- Existing validation artifact: verify and reuse it before loading validation
  observations; never overwrite or rerun with changed parameters.
- Identity, parent, version, split, or policy mismatch: exit with a concise
  error and no child artifact.

## Testing

Tests are written before production changes and prove:

- adding arbitrarily bad daily-limit overflow observations cannot change the
  real Top-3 return metrics;
- changing an admitted trade changes expectancy, Profit Factor, Wilson bounds,
  stop rate, rolling-window results, and drawdown consistently;
- ranking, deterministic ties, active-structure deduplication, no-backfill
  semantics, and daily Top 1/3/5 truncation;
- capacity-three admission and capacity rejection evidence;
- cancelled, not-triggered, unresolved, and missing observations remain outside
  return metrics and inside funnel counts;
- metric sample gates use admitted trades;
- fold-1 and fold-2 calibrations use only earlier resolved outcomes;
- train diagnostics emit no validation or test return metrics;
- Top 1, Top 5, or changed ranking parameters cannot enter the preregistered
  validation stage;
- validation artifacts are write-once and idempotent;
- old evaluator evidence cannot enter corrected freeze eligibility;
- existing five-day CLI safety surfaces remain unchanged;
- the complete relevant five-day and buy-point regressions pass.

## Runtime Acceptance

After implementation verification:

1. Use the complete `2b52de79...` research artifact as the immutable parent.
2. Run only `diagnose-train`.
3. Report fold-level and combined Top 1/3/5 results, rank-band monotonicity,
   selection funnels, and loss attribution.
4. Compare corrected Top-3 train metrics with the old all-resolved-candidate
   baseline and explain the difference.
5. Confirm no validation, freeze, test, forward, holdings, order, schedule,
   notification, advisor-memory, or decision-memory artifact was created.
6. Stop for user review before `validate-ranking`.

## Out of Scope

- Changing the current ranking key, profile matrix, entry rules, stop rules,
  costs, thresholds, or candidate discovery.
- Selecting a different Top N from validation results.
- Reading or consuming the 126-session test segment.
- Running `freeze`, forward screening, settlement, or formal selector release.
- Recommending or trading current stocks.
- Writing MySQL, holdings, orders, personal decision memory, schedules, or
  notifications.
- Using the deprecated Eastmoney eight-dimension or any Eastmoney stock
  diagnosis framework.
