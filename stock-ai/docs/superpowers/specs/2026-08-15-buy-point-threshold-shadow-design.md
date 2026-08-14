# Buy-Point Threshold Shadow Research Design

## Status

Approved section by section in conversation on 2026-08-15. This feature is
research-only. It does not change formal selection, portfolio, memory, or order
behavior.

## Purpose

Test whether narrowly relaxing one numeric setup boundary at a time can produce
a small, higher-precision pool of actionable three-to-five-session buy points.
The study must measure executable plan outcomes across the entire eligible
point-in-time universe, not merely recover hindsight winners.

The v5 daily-recall evidence found only 9 exact-date captures among 16,918
actionable winner stock-date rows across three frozen weeks. All 9 captures were
`NEAR_MISS`, while `NO_BUY_POINT_SETUP` dominated the missed population. Among
11,724 no-setup winner diagnostics, the closest existing template had exactly
one failed condition for:

- 450 first-launch-pullback rows;
- 402 trend-pullback rows; and
- 65 pre-breakout rows.

This suggests testing small single-boundary relaxations before adding a fourth
setup or performing a joint threshold search.

## Objective and Success Definition

The study is precision-first. The frozen shadow basket may contain at most five
stocks per signal date and does not have to fill the basket.

Short-term success uses two layers:

1. Primary executable-plan evidence: triggered and resolved count, transaction-
   cost-adjusted mean and median net return, positive-net-return rate, stop-first
   rate, MFE, and MAE.
2. Auxiliary recall evidence: exact-date capture of daily actionable winners
   with at least 5% forward upside within the next five sessions from a normal
   entry.

An intraday high alone is not treated as a successful strategy outcome.

## Considered Approaches

### Single-boundary threshold ladders

Selected. Each profile relaxes exactly one existing numeric `SelectionPolicy`
field by 10%, 25%, or 50%. Every other setup condition and every downstream gate
remains unchanged. The approach provides direct attribution and limits universe
expansion.

### Joint threshold search

Rejected for this iteration. Simultaneously changing multiple setup boundaries
could increase recall quickly, but three short windows cannot reliably identify
interactions and would make the result difficult to explain.

### A fourth setup template

Rejected for this iteration. The current evidence does not yet establish a
stable new pre-entry structure. Designing a new template from the same hindsight
winners used to evaluate it would create severe outcome leakage.

## Frozen Profile Matrix

Each profile has a deterministic identifier containing setup type, policy
field, direction, and relaxation rate. A profile changes exactly one policy
field from `SelectionPolicy()`.

For an upper bound, the research value is:

```text
formal_value * (1 + relaxation_rate)
```

For a lower bound, the research value is:

```text
formal_value * (1 - relaxation_rate)
```

The relaxation rates are the literal decimals `0.10`, `0.25`, and `0.50`.

### Pre-breakout fields

- `platform_width_max` upward;
- `platform_near_top_max` upward;
- `platform_contraction_max` upward; and
- `platform_amount_ratio_max` upward.

### Trend-pullback fields

- `trend_return10_min` downward;
- `trend_return10_max` upward;
- `trend_drawdown_min` downward;
- `trend_drawdown_max` upward; and
- `pullback_amount_ratio_max` upward.

### First-launch-pullback fields

- `launch_gain_min` downward;
- `launch_gain_max` upward;
- `launch_amount_ratio_min` downward;
- `launch_amount_ratio_max` upward;
- `launch_close_location_min` downward;
- `consolidation_gain_abs_max` upward; and
- `consolidation_amount_ratio_max` upward.

The initial matrix therefore contains 48 profiles: 16 fields times 3 rates.

Structural or hard-coded conditions are not relaxable in v1. These include no
negative pullback, disorderly pullback bars, close below MA10 or MA20, falling
MA20, preceding three-up, preceding five-session return, invalid prices, and
insufficient history. A numeric profile cannot bypass any such failure.

## Shadow Setup Generation

The implementation creates a dedicated research module:

```text
stock_ai/buy_point_selection/threshold_shadow_research.py
```

For every profile and eligible stock-date:

1. Run the relevant production detector with the formal policy and require it to
   return no setup of that type.
2. Use `dataclasses.replace` to change exactly the profile's one allowed policy
   field.
3. Run only the relevant detector with the relaxed policy.
4. Require the v5 diagnostic mirror to show that the formal result failed only
   the condition corresponding to the profile field.
5. Require the actual normalized boundary deviation to be no greater than the
   profile rate.
6. Wrap the detected structure in `ThresholdShadowSetup`; do not expose it as a
   formal setup or candidate.

The wrapper records the profile identifier, formal value, shadow value,
relaxation rate, actual deviation, detected structure and metrics. It has no
trade permission.

Production `patterns.py` and default `SelectionPolicy` remain unchanged. A
formal detector result always supersedes and excludes the corresponding shadow
result so the study measures genuinely incremental candidates.

## Full-Universe Candidate Pipeline

Shadow generation runs on every point-in-time eligible stock-date in the frozen
windows, not only v5 winner rows. Outcome data is unavailable during signal
generation.

Point-in-time eligibility requires an eligible Shanghai or Shenzhen main-board
code, complete signal-time history, valid positive prices, the formal liquidity
floor, no signal-date `VETO`, and absence from that date's reconstructed
holdings. Missing facts are not inferred.

After shadow setup generation, the candidate must pass the existing unchanged:

- base and liquidity gate;
- point-in-time risk exclusions;
- market regime gate;
- sector strength and breadth gates;
- anti-chase gates; and
- price-plan and 2R-space requirements.

The existing price planner may consume the wrapped detected structure internally,
but the returned object is wrapped as `ThresholdShadowCandidate` with
`executable_shares=0`, `CASE_ANALYSIS_ONLY`, and `NO-TRADE`. It cannot enter the
formal candidate list, sizing, notification, decision memory, or order paths.

## Deduplication and Daily Ranking

The research report retains raw profile hits for audit. The daily selectable
shadow basket is deduplicated by `(signal_date, code)`.

When one stock-date passes multiple profiles, choose deterministically by:

1. lower relaxation rate;
2. lower actual normalized deviation;
3. higher relaxed-detector setup quality; and
4. lexical profile identifier.

After profile freezing, rank deduplicated daily candidates by:

1. frozen profile rank;
2. lower relaxation rate;
3. lower actual deviation;
4. higher setup quality;
5. larger 2R-space buffer; and
6. normalized stock code.

Retain at most five candidates per signal date. Do not fill missing slots with
an ineligible profile or candidate.

## Outcome Evaluation

Each candidate uses the same existing plan trigger, validity, stop, 2R target,
transaction-cost, and intraday ambiguity handling as the formal 3.1.0 case
baseline. Its evaluation horizon ends after the fifth trading session following
the signal date.

Primary metrics use triggered rows with a resolved net return:

- mean and median net return;
- positive-net-return rate, defined literally as `net_return > 0`;
- stop-first rate;
- mean MFE and MAE; and
- counts for raw hits, deduplicated candidates, selected candidates, triggers,
  resolutions, expirations, and ambiguous intraday ordering.

Auxiliary recall joins the existing v5 actionable winners by exact
`(signal_date, code)`. Stock-date rows are explicitly described as overlapping
and non-independent.

The formal comparison cohort uses the same signal dates, inputs, outcome cutoff,
fees, and evaluator. Only the formal strict tier participates in the trade-like
baseline; near-miss research rows are reported separately.

## Development, Freeze, and Test Split

The workflow has three explicit stages and no scheduled execution:

1. `research`: run the July 20–24 and July 27–31 signal windows, with outcomes
   through July 31 and August 7 respectively.
2. `freeze`: aggregate only those two windows, screen profiles, rank qualifying
   profiles, and write an immutable profile artifact.
3. `test`: consume the frozen artifact once for the August 3–7 signal window,
   with outcomes through August 14.

A profile qualifies for freezing only when its combined research rows contain at
least 10 triggered outcomes with resolved net returns and satisfy all of:

- mean net return greater than zero;
- positive-net-return rate at least 50%; and
- stop-first rate no greater than 40%.

Qualifying profiles receive a frozen rank by:

1. higher mean net return;
2. higher positive-net-return rate;
3. lower stop-first rate;
4. lower relaxation rate; and
5. lexical profile identifier.

If no profile qualifies, freeze an explicit empty profile set. The test stage
must then produce an empty shadow basket rather than lowering the thresholds.

The August window is a one-time holdout for the frozen hash. A second run with
the same inputs verifies the immutable output. It cannot overwrite or tune the
profile. A different profile hash creates a different research lineage and may
not claim to be the same frozen test.

Passing the short holdout only means the profile deserves a broader historical
study. It never promotes a production rule.

## Artifacts and Identity

Do not modify existing v5 case files. Create a separate immutable schema:

```text
buy-point-threshold-shadow-v1
```

Artifacts live under an ignored research output directory and link to the three
v5 case identities. The identity includes:

- schema;
- stage;
- signal dates and outcome cutoff;
- formal rule version and policy hash;
- profile-matrix hash or frozen-profile hash;
- point-in-time input coverage hashes; and
- fee/evaluator version.

The JSON report contains raw profile hits, deduplicated candidates, selected
daily baskets, outcomes, profile-level metrics, formal baseline metrics,
exact-date incremental recall, all rejection counts, frozen profile ranks, and
input completeness. Markdown presents the aggregate comparison and safety
boundary without listing thousands of raw rows.

Every raw and aggregate research record is deterministic. Existing artifacts
are opened exclusively and only accepted when their contents match exactly.

## Failure Handling

- A profile that changes zero or more than one policy field is rejected.
- An unsupported or structural field is rejected.
- Non-finite policy values, prices, quality, deviation, or plan levels fail
  closed with an explicit reason.
- Incomplete signal-date bars, holdings, market state, or required
  non-announcement point-in-time reference data excludes that date from profile
  screening and reports it.
- Incomplete announcement risk coverage permits case evidence but sets promotion
  eligibility to false.
- Fewer than five outcome sessions excludes that date from outcome metrics.
- Missing v5 lineage, a mismatched profile hash, or test-before-freeze is a hard
  error.
- An existing artifact with different contents is never overwritten.
- MySQL access is read-only. The LAN host is a runtime environment override and
  is not committed.

## Safety Boundaries

- Rule version remains `buy-point-selection-3.1.0`.
- Default `SelectionPolicy`, production detectors, gates, planner, sizing, and
  validation remain unchanged.
- No holding, decision memory, portfolio snapshot, notification, or order write
  is allowed.
- No profile can produce executable shares.
- The report is always `CASE_ANALYSIS_ONLY / NO-TRADE`.
- Generated research data remains ignored by Git.
- Announcement coverage must be complete before any later promotion study could
  be considered.

## Tests

Tests must prove:

- each profile changes exactly its named field and literal rate;
- upper and lower bounds relax in the correct direction;
- the default policy produces the same results as production detectors;
- a profile admits only a setup whose formal diagnostic has exactly the matching
  numeric failure;
- structural failures cannot be bypassed;
- formal setups are excluded from incremental shadow counts;
- future bars and outcomes cannot affect setup generation, profile identity, or
  daily ranking;
- all unchanged market, sector, anti-chase, risk, plan, and 2R gates still fail
  closed;
- multi-profile stock-date hits deduplicate deterministically;
- profile and daily rankings have total deterministic tie breakers;
- the daily basket never exceeds five and never fills from failed profiles;
- training metrics use only the two research windows;
- test cannot run before an immutable freeze;
- empty qualifying results freeze and test as an empty set;
- a frozen hash cannot be tested twice with different contents;
- primary metrics reconcile with raw triggered outcomes;
- exact-date auxiliary recall reconciles with v5 winner rows;
- every setup, candidate, plan, and report row has zero executable shares and
  non-trading labels; and
- production patterns, planning, validation, holdings, and memory regression
  tests remain unchanged and pass.

## Acceptance Criteria

Implementation is complete when:

- all 48 profiles can be generated and audited without changing production
  policy;
- every profile is evaluated on the full eligible point-in-time universe;
- the two research windows produce deterministic profile metrics and either a
  valid immutable freeze or an explicit empty freeze;
- the August holdout consumes the frozen hash exactly once;
- formal and shadow primary outcomes plus auxiliary recall reconcile with raw
  rows;
- daily selected shadows remain between zero and five;
- all artifacts remain zero-share and non-trading;
- risk incompleteness blocks promotion;
- the relevant full regression passes; and
- no formal selection, holding, memory, notification, or order behavior changes.
