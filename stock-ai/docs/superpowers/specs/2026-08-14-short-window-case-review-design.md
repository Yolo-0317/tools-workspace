# Short-Window Buy-Point Case Review Design

## Status

Approved in conversation on 2026-08-14, pending written-spec review before implementation.

## Purpose

Use a short, point-in-time strategy execution and outcome review as a case study to expose concrete problems in buy-point selection. The first case replays the five trading days of 2026-08-03 through 2026-08-07 and evaluates subsequent outcomes beginning 2026-08-10.

This case is diagnostic evidence only. It does not replace the 630-day historical calibration, frozen test, or forward promotion gate, and it cannot modify production thresholds by itself.

## Questions the Case Must Answer

1. Which stocks entered the strict shadow list on each signal date?
2. Which stocks failed exactly one soft gate and were credible near misses?
3. Which buyable stocks subsequently rose, and were they captured by either list?
4. For missed winners, which gate rejected them using only information available on the signal date?
5. Do repeated misses point to an overly strict gate, an uncovered setup, or an inherently unbuyable move?

## Window and Chronology

- Signal window: 2026-08-03 through 2026-08-07.
- Outcome window begins on 2026-08-10.
- Each signal date is replayed only with bars, market state, sector membership, risk facts, holdings, and decision state available at that time.
- A plan may trigger only during the next two actual trading sessions.
- After a trigger, the plan is observed for at most five actual trading sessions.
- A plan whose five-session horizon is not yet available remains `PENDING`; it is not counted as success or failure.
- The report may be generated as a partial snapshot through the latest complete daily bar and regenerated later as a new case revision. Earlier snapshots remain unchanged.

## Candidate Layers

### Strict shadow

A stock passes the existing 3.1.0 technical, market, sector, tradability, risk-distance, and price-plan gates but lacks formal eligibility because historical calibration, forward promotion, account evidence, or complete announcement coverage is unavailable. It has zero executable shares and cannot create a live plan.

### One-soft-gate near miss

A stock fails exactly one approved soft gate and passes every hard gate. The allowed soft-gate families are:

- sector strength or resonance;
- 2R room;
- risk-distance range.

The following are never relaxed for a near miss:

- ST, suspension, or a known hard announcement veto;
- missing or stale price data;
- minimum liquidity and basic tradability;
- existing holding exclusion;
- more than one failed gate.

At most ten near misses are retained per signal date. Ranking is deterministic: fewer and smaller boundary deviations first, then setup quality, liquidity, and stock code.

## Outcome Definition

A case plan is successful when all of the following hold:

- the frozen entry condition is realistically triggered within the next two trading sessions;
- within five trading sessions after the trigger, maximum favorable excursion is at least 5%;
- maximum adverse excursion over the same horizon is no more than 3%.

The ledger also records trigger date, entry price, close-to-exit return, fee-adjusted return, MFE, MAE, non-trigger, stop-first, and unresolved outcomes. Daily bars cannot reveal intraday ordering when target and stop are both touched, so the existing conservative stop-first convention remains unchanged.

## Buyable Winner and Recall Definition

A buyable winner is a Shanghai or Shenzhen main-board stock that:

- reaches at least 5% maximum gain from the signal week's final close to an outcome-week high;
- satisfies the existing minimum-liquidity requirement;
- offers at least one normal entry session that is not a one-price limit-up and does not open more than 3% above the relevant prior close;
- is not subject to an available hard risk veto at the relevant point in time;
- was not already held at the relevant signal date.

The case reports separate recall for strict-shadow candidates, near misses, and their union. It also lists every missed buyable winner with its first point-in-time rejection gate. This is attribution, not permission to relax that gate.

## Metrics

- triggered-plan success rate, excluding `PENDING`;
- buyable-winner recall for strict shadow, near miss, and their union;
- non-trigger rate, stop-first rate, average and median fee-adjusted return;
- MFE and MAE distributions;
- daily candidate count and zero-candidate days;
- rejection counts and missed-winner attribution by gate;
- count of incomplete signal dates and unresolved plans.

Small-sample percentages are descriptive only. The report must show raw numerators and denominators and must not label a threshold as improved or promoted.

## Data and Integrity Rules

- MySQL daily bars and existing point-in-time reference tables are the primary inputs.
- No locally derived candidate list, holding, account fact, or personal decision memory is sent to an external data provider.
- Missing announcement coverage does not prevent case diagnostics, but the report is fixed to `RISK_COVERAGE_INCOMPLETE / NO-TRADE` and cannot emit formal recommendations.
- A missing market snapshot, daily bar, or sector membership marks the affected signal date `INCOMPLETE`; it must not be represented as a legitimate zero-candidate day.
- Outcome-week data is unavailable to signal generation and gate attribution.
- Existing production profiles, validation artifacts, holdings, plan events, and decision memories are read-only for this case.

## Components and Outputs

The implementation is an isolated analysis path that reuses existing pure pattern, gate, plan, and replay functions:

1. A point-in-time signal replay produces strict-shadow candidates and per-code gate traces.
2. A near-miss classifier admits only one approved soft-gate failure.
3. The existing trigger and five-session outcome simulator resolves each retained plan.
4. A full-market winner analyzer identifies buyable winners and joins their historical gate traces.
5. A renderer writes one JSON artifact and one Markdown case report under `stock-ai/output/`; both remain ignored by Git.

The case identity includes the signal window, outcome cutoff, rule version, and policy hash. Output filenames include the outcome cutoff. Regeneration with a later cutoff creates a new immutable revision rather than overwriting the earlier partial snapshot. No scheduler, notification, automatic order, production API, or new live-selection mode is added.

## Interpretation and Decision Memory

The report header and conclusion must state: `CASE_ANALYSIS_ONLY`. Findings may create a follow-up hypothesis only when they identify a concrete failure mode. A production rule change requires corroboration from additional independent cases and the existing historical and forward validation process.

The durable project decision is the scope constraint itself: short-window execution and review are used to discover problems, not to prove profitability, calibrate probabilities, or authorize trading.

## Failure Handling

- Empty strict and near-miss lists are valid only when every signal date is complete; otherwise the report is incomplete.
- Any detected future-data leakage aborts artifact creation.
- Malformed or inconsistent outcome rows abort the affected revision.
- External-source failure is represented explicitly and cannot be converted into complete coverage.
- A partial current-week report keeps unresolved plans as `PENDING` and displays the latest complete market date.

## Test Requirements

- signal replay cannot access bars or facts after its signal timestamp;
- next-two-session trigger and next-five-session outcome boundaries use actual trading dates;
- the 5% MFE and 3% MAE thresholds are tested at, below, and above the boundary;
- `PENDING` is excluded from success and failure denominators;
- exactly one allowed soft-gate failure can enter near miss;
- hard veto, liquidity failure, existing holding, or two failed gates cannot enter near miss;
- buyable-winner detection excludes one-price limit-ups and excessive gap opens;
- missed-winner attribution uses the signal-date gate trace;
- identical inputs produce identical case identity and output ordering;
- a later cutoff creates a new revision and does not overwrite an earlier one;
- no formal plan, position change, profile update, or automatic order is produced.

## Acceptance Criteria

The first case is complete when it produces an auditable partial or final report for the stated signal week, identifies strict-shadow and near-miss candidates per day, resolves every currently observable outcome without leakage, lists buyable winners and their capture status, attributes each miss to a point-in-time gate, and clearly separates findings from any future rule-change decision.
