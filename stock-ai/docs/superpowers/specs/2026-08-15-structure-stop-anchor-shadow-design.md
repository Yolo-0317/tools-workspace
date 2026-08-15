# Structure Stop-Anchor Shadow Research Design

## Status

Approved in conversation on 2026-08-15. This document is ready for written-spec review before implementation planning.

## Purpose

Determine whether production buy-point plans are rejected because their pattern-native invalidation anchors create unnecessarily wide risk distances. Compare three fixed, point-in-time stop-anchor variants without changing production pattern detection, gates, resistance, 2R requirements, position sizing, or rule version.

This is retrospective, zero-share case research. It cannot authorize trades or promote a formal rule.

## Evidence Leading to This Study

The three gate-shadow windows produced 120 exact gate hits, but every hit also failed the production price plan: 65 for risk distance and 55 for insufficient 2R room. Because those rows contain two simultaneous failures, they cannot justify relaxing either gate or price-plan logic.

A separate, compliant single-variable calculation over formal-gate-pass price-plan near misses found:

- 28 insufficient-2R rows whose legacy effective resistance room ranged from approximately 0.02R to 0.28R;
- no candidate at an economically meaningful 0.5R-or-higher relaxed target;
- negative mean fee-adjusted net returns when targets were forced down to 0.05R through 0.20R; and
- one risk-distance row at approximately 8.60% whose fee-adjusted net return was negative.

The next isolated variable is therefore the stop anchor that determines risk distance and, through risk distance, the unchanged 2R target.

## Non-Goals

- Do not modify `models.py`, `patterns.py`, `gates.py`, `planning.py`, or production rule version `buy-point-selection-3.1.0`.
- Do not lower the 2R requirement or replace production `nearest_resistance_above`.
- Do not bypass market, base, setup, anti-chase, sector, holdings, reference, or risk gates.
- Do not combine a gate bypass with a stop-anchor change in an evaluable or freezable cohort.
- Do not tune multiple ATR multipliers after observing outcomes.
- Do not install scheduling, send notifications, write holdings or decision memory, or place orders.
- Do not treat eight observed windows as an independent holdout.

## Research Windows

Build eight consecutive research blocks from the local confirmed A-share calendar, ending with the completed 2026-08-03 through 2026-08-07 signal block and its result cutoff of 2026-08-14.

Each block contains exactly:

- five confirmed signal trading sessions; and
- the next five confirmed result trading sessions.

The runtime derives blocks from confirmed trading dates rather than assuming Monday-through-Friday calendar weeks. Every signal and outcome date must already exist in the bounded MySQL daily-bar input. Missing trading dates fail closed.

All eight blocks are retrospective and observed. Generated artifacts must set `retrospective=true`, `promotion_eligible=false`, `status=CASE_ANALYSIS_ONLY`, `trade_permission=NO-TRADE`, and `executable_shares=0` recursively.

## Cohort Isolation

### Primary evaluable cohort

A stock-date enters the primary cohort only when all of the following pass with production logic and point-in-time data:

- latest complete signal-date bar;
- complete sector, ST, market, and historical-holdings facts;
- market gate;
- base gate;
- one of the three production setup detectors;
- anti-chase gate; and
- sector gate.

The production diagnostic price plan must then report exactly one failure:

```text
RISK_DISTANCE_OUT_OF_RANGE
```

The row must not also fail 2R room, board-lot sizing, ATR availability, or any other condition. This ensures the research changes only one causal variable.

### Secondary diagnostic cohort

Rows with exactly one supported market or sector gate failure plus a risk-distance failure may be recorded for geometry attribution. They must be labeled `DIAGNOSTIC_ONLY_COMBINED_FAILURE` and are permanently excluded from metrics qualification, freezing, ranking, and forward screens.

No other multi-failure row is retained.

## Baseline

The baseline reproduces the production plan exactly:

```text
trigger = ceil_cent(structure_high + 0.01)
invalidation = floor_cent(structure_low - 0.2 * ATR14)
risk = trigger - invalidation
target = ceil_cent(trigger + 2 * risk)
```

The production risk interval remains:

```text
max(1.5%, 0.8 * ATR14 / trigger) <= risk / trigger <= 5%
```

The production resistance check remains:

```text
nearest_resistance_above(trigger, last_60_signal_time_bars) >= target
```

The baseline is attribution only and cannot freeze because it already failed production risk distance.

## Fixed Stop-Anchor Profiles

All variants preserve production trigger price, formal risk interval, 2R target formula, resistance check, risk budget, plan validity, and execution costs. The two support-anchor variants preserve the production 0.2 ATR buffer; the fixed ATR-distance comparator defines the complete invalidation distance and therefore adds no second buffer. A variant that still fails any downstream production check is rejected rather than partially admitted.

### `STRUCTURE_STOP:RECENT_SETUP_LOW`

Use a setup-aware recent low:

- `PRE_BREAKOUT`: minimum low of the final 10 signal-time sessions;
- `TREND_PULLBACK`: minimum low of the detected two-to-four-session pullback; and
- `FIRST_LAUNCH_PULLBACK`: minimum low of the one-to-two quiet sessions after the launch, excluding the launch bar.

The anchor must be finite, positive, and no higher than the signal-date low.

### `STRUCTURE_STOP:DYNAMIC_SUPPORT`

Construct support candidates using only signal-time data:

- MA10;
- MA20; and
- the `RECENT_SETUP_LOW` anchor.

Keep only finite positive candidates at or below the signal-date low. Select the highest remaining support. If none exists, reject the profile as `SUPPORT_ANCHOR_UNAVAILABLE`.

### `STRUCTURE_STOP:ATR_1_5`

Set invalidation directly from a single frozen volatility distance:

```text
invalidation = floor_cent(trigger - 1.5 * ATR14)
```

This comparator does not use a separate 0.2 ATR buffer because its invalidation is already the complete volatility stop. The multiplier is fixed before outcomes are evaluated; no alternate ATR multipliers are generated in this study.

## Point-in-Time Data Rules

- Setup, moving averages, ATR, anchors, trigger, risk, target, resistance, and ranking can use only bars whose `trade_date <= signal_date`.
- Outcome bars cannot influence profile construction, eligibility, deduplication, or ranking.
- Each plan uses the confirmed second trading session after its signal date as `valid_through_trade_date`.
- Outcome evaluation is bounded to the fifth confirmed trading session after the signal date.
- Historical holdings are read point-in-time; no current-position fallback is allowed.
- Incomplete announcement coverage remains visible in the artifact and prevents any future promotion claim, but does not fabricate missing facts.

## Outcome Evaluation

Reuse the production conservative execution simulator and default costs:

- entry begins after the signal date;
- locked limit-up entries remain unbuyable;
- slippage, commission, minimum commission, and sell tax apply;
- target/stop ambiguity remains conservatively resolved by existing execution logic; and
- every result retains trigger date, status, fee-adjusted net return, MFE, MAE, stop-first flag, and structure identity.

Research reports group results by profile and setup type. Each group includes:

- raw primary rows;
- downstream-valid candidates;
- triggered and resolved counts;
- positive-net count and rate;
- mean and median fee-adjusted net return;
- stop-first count and rate;
- mean MFE and MAE; and
- exact-date overlap with existing v5 actionable-winner rows.

Zero denominators remain null rather than receiving synthetic rates.

## Freeze Rules

A profile qualifies only after aggregating raw rows from all eight immutable research windows and meeting every condition:

- at least 10 triggered and resolved plans;
- mean fee-adjusted net return greater than zero;
- positive-net rate at least 50%; and
- stop-first rate no greater than 40%.

Freeze validation also requires:

- eight distinct approved research identities;
- identical production rule version, policy hash, evaluator version, cost version, and stop-profile matrix hash;
- recomputed raw-row metrics that exactly match every reported summary;
- no diagnostic combined-failure row in qualifying metrics; and
- recursive zero-share safety.

An empty freeze is valid. No fallback, threshold relaxation, or candidate padding is permitted.

## Forward Observation

Only frozen profiles may enter manual forward screens. Forward behavior remains:

- one completed, locally confirmed signal date per manual run;
- price bars bounded through the signal date;
- zero to five candidates after deterministic code/date deduplication;
- zero executable shares and no outcome fields in the screen artifact;
- a separate immutable settlement after exactly five completed sessions; and
- no formal promotion before at least 20 distinct forward signal dates and 20 resolved plans, followed by a separate approved validation design.

Forward screens and settlements remain `CASE_ANALYSIS_ONLY / NO-TRADE` even when profiles freeze.

## Architecture

Add a focused research module for pure stop-anchor calculations and reuse existing replay, execution, immutable-artifact, calendar, and MySQL seams:

```text
stock_ai/buy_point_selection/structure_stop_shadow.py
    fixed profile definitions
    setup-aware anchor calculation
    zero-share candidate construction
    profile validation and matrix hash

stock_ai/buy_point_selection/structure_stop_evaluation.py
    bounded outcome evaluation
    profile aggregation
    eight-window freeze validation

stock_ai/buy_point_selection/structure_stop_report.py
    immutable research/freeze/screen/settlement payloads
    strict stage loaders

scripts/analysis/review_buy_point_structure_stops.py
    manual research/freeze/screen/settle CLI
```

Production detector, gate, and planner modules remain unchanged. The research module may call their pure helpers but cannot be imported by a production selector.

## Immutable Artifacts

Use schema `buy-point-structure-stop-shadow-v1`. Every artifact identity includes stage, signal dates, cutoff where applicable, v5 lineage, input fingerprint, production rule and policy hashes, profile matrix hash, evaluator version, cost version, and parent/freeze lineage.

Writers use exclusive creation. An identical rerun verifies byte-for-byte content; different content at the same path raises an immutable-content error. Generated files remain under ignored `output/research/buy_point_structure_stops/` and are not committed.

## Error Handling

Fail closed on:

- an unapproved or incomplete trading-session block;
- missing historical holdings, sector, ST, or market facts;
- future bars in a signal panel;
- an unsupported or reordered profile matrix;
- a primary row with more than the single approved risk-distance failure;
- an anchor above the signal-date low or a non-finite/non-positive anchor;
- a profile candidate that fails the unchanged formal risk or 2R checks;
- nonzero executable shares;
- candidate/outcome membership mismatch;
- edited summary metrics or lineage hashes;
- a diagnostic combined-failure row entering freeze or screen; or
- an attempt to settle before exactly five completed outcome sessions.

The CLI returns exit code 2 for validation failures and performs no fallback data writes.

## Tests

Tests must prove:

- the exact three-profile matrix and canonical hash;
- setup-aware recent lows for all three production setup types;
- future bars cannot change any anchor;
- dynamic support selects only valid signal-time support at or below signal low;
- ATR 1.5 uses the exact fixed multiplier and no extra buffer;
- every shadow preserves production trigger, risk bounds, 2R formula, resistance, plan validity, and costs;
- a risk-only formal-gate-pass row can enter the primary cohort;
- a risk-plus-2R or risk-plus-gate row cannot enter primary metrics;
- diagnostic combined-failure rows never freeze or screen;
- all candidates and outcomes remain zero-share;
- eight research windows are exact and distinct;
- reported metrics are recomputed from raw rows before freezing;
- qualification boundaries are inclusive or exclusive exactly as specified;
- empty freeze and empty screen artifacts are valid;
- screen artifacts contain no outcomes or future dates;
- settlement preserves exact parent membership and never rewrites the screen; and
- production planner, pattern, gate, and broader buy-point regression tests remain unchanged.

## Acceptance Criteria

The study is complete when it:

- generates eight immutable retrospective research revisions from bounded read-only inputs;
- isolates risk-only production near misses from combined-failure diagnostics;
- compares exactly the three frozen stop-anchor profiles with full five-session outcomes;
- either freezes only profiles meeting every stated threshold or produces an explicit empty freeze;
- provides manual zero-share screen and settlement commands for any non-empty freeze;
- passes the relevant buy-point regression suite; and
- leaves production rules, portfolio state, memory, notifications, schedules, and orders unchanged.
