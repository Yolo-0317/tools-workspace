# Daily Recall Diagnostics Design

## Status

Approved in conversation on 2026-08-14. This feature is research-only and does not change formal selection or execution behavior.

## Purpose

Replace the current week-level winner attribution with an exact signal-date, five-trading-session recall audit, then diagnose why actionable short-term winners were excluded. The result must distinguish market-regime vetoes from missing buy-point shapes before any new setup or threshold is proposed.

The three frozen v4 windows showed very low exact-date capture when each signal date was matched to its own future five sessions:

- July 20–24: 4,465 stock-date winner opportunities, 2 captured;
- July 27–31: 4,674 stock-date winner opportunities, 2 captured; and
- August 3–7: 4,030 stock-date winner opportunities, 4 captured.

The dominant first rejections were `INDEX_AND_BREADTH_WEAK` and `NO_BUY_POINT_SETUP`. The current report cannot reliably interpret those counts because it builds winners only for the final signal date, allows a candidate from any date in the weekly window to count as captured, and reports only the final date's rejection trace.

## Existing Metric Problem

The current `find_buyable_winners` audit uses the final signal date of a multi-day case, then looks across the outcome week for a 5% high relative to that final signal close. `attribute_buyable_winners` considers a winner captured when the same code appeared in any candidate tier anywhere in the signal window. This mixes different decision dates.

The broad 5% winner denominator itself is not primarily caused by entries after the rise. A read-only check showed that 88%–96% of current winners still had at least 5% forward upside from the first normal entry day's opening price. The principal defect is date attribution, followed by insufficient diagnostic detail.

## Considered Approaches

### Exact daily recall plus research diagnostics

Selected. Build an independent winner cohort for every signal date, use only its next five trading sessions, require a normal entry before the measured gain, and join candidates and rejection traces by both code and signal date. Market-vetoed winners and no-setup winners receive zero-share diagnostic rows.

This corrects measurement before altering strategy behavior and creates evidence for a later setup-design decision.

### Add a fourth setup immediately

Rejected for this iteration. The current winner rows do not yet say whether missing stocks were breakouts, trend continuations, launch pullbacks, or simply market-beta moves. Designing a setup from outcome winners now would overfit the same three weeks.

### Relax market and shape gates directly

Rejected. More than 4,000 stock-date opportunities can appear in one week under the broad hindsight benchmark. Direct relaxation would expand the trade universe without proving entry quality or risk control.

## Exact Daily Actionable Winner

A daily actionable winner is evaluated independently for each signal date.

### Point-in-time eligibility

At the signal date, the code must:

- be an eligible Shanghai or Shenzhen main-board code;
- not be held in the point-in-time portfolio;
- have no point-in-time `VETO` risk flag;
- have a valid signal-date bar and at least five historical bars; and
- meet the existing five-day average-amount floor.

These filters reproduce the current hindsight-universe safety boundary. They do not require a detected setup, sector pass, market pass, or valid 2R plan because those are the exclusions being audited.

### Outcome horizon

Use exactly the next five available trading sessions after the signal date. If the case outcome cutoff contains fewer than five sessions, mark that daily cohort incomplete and exclude it from recall denominators. Future sessions outside the five-day horizon cannot participate.

### Normal entry before gain

For each outcome session in order, a potential entry is normal when:

- the bar is not a one-price locked limit-up day with `pct_chg >= 9.5`; and
- its opening gap from the previous session close is no greater than 3%.

For every normal entry date, compute the maximum high from that date through the fifth outcome session divided by that entry day's opening price minus one. The code is a daily actionable winner when at least one normal entry has forward maximum gain of at least 5%. Select the earliest qualifying entry. This guarantees the measured gain occurs on or after the stated buyable entry.

The immutable winner row records signal date, horizon end date, entry date, entry opening price, forward maximum gain, maximum-gain date, exact-date captured tiers, and exact-date first rejection.

## Exact-Date Attribution

A winner is captured only when a strict or near-miss candidate has the same normalized code and the same signal date. A candidate from Monday cannot capture a Friday winner row.

The first rejection comes only from `replay.traces[(signal_date, code)]`. Missing traces remain explicit and are never replaced by another date's trace.

Daily and aggregate metrics report:

- complete signal dates;
- actionable winner stock-date pairs;
- unique winner codes;
- exact-date captured winner pairs;
- capture counts by candidate tier;
- missed counts by exact first rejection;
- outcome entry and gain distributions; and
- raw winner rows for audit.

Percentages are descriptive only. Stock-date pairs are not presented as independent statistical samples.

## Market-Freeze Research Rows

When the exact first rejection is a market status reason such as `INDEX_AND_BREADTH_WEAK`, the report creates a zero-share market-freeze diagnostic row for the winner. It runs signal-time base and setup detection only for diagnosis and records:

- whether the base gate would otherwise pass;
- any existing detected setup types;
- setup quality and signal-time metrics when present; and
- the market rejection reason.

It does not build a formal price plan, bypass the market gate, create a candidate, or grant trade permission. This answers whether the market gate hid otherwise valid setups without weakening the gate.

## No-Setup Diagnostics

For an exact-date winner whose first rejection is `NO_BUY_POINT_SETUP`, create a deterministic diagnostic for each existing setup template.

### Pre-breakout template

Evaluate the existing 30-session platform inputs and record failures for:

- platform width;
- distance to platform high;
- range contraction;
- amount contraction; and
- MA20 five-session slope.

### Trend-pullback template

Evaluate each existing 2-, 3-, and 4-session pullback window. For every window, record failures for:

- absence of a negative pullback session;
- oversized or positive pullback bars;
- 10-session trend return;
- drawdown from the trend peak;
- pullback amount contraction; and
- close position relative to MA10 and MA20.

Select the closest window deterministically by `(failed_condition_count, normalized_boundary_deviation, session_count)` and retain its literal metrics and failures.

### First-launch-pullback template

Evaluate both existing 1- and 2-session quiet windows. Record failures for:

- launch gain;
- launch amount ratio;
- launch close location;
- excessive preceding five-session return;
- preceding three-up exclusion;
- quiet-session price range; and
- quiet-session amount contraction.

Select the closest window by `(failed_condition_count, normalized_boundary_deviation, quiet_session_count)`.

Diagnostics reuse the exact current policy values but cannot return a `DetectedSetup` or alter detector output. They are an explanatory mirror with tests that assert every production-positive fixture has zero diagnostic failures.

## Architecture

Create a focused research module:

```text
stock_ai/buy_point_selection/recall_research.py
```

It owns immutable daily winner and setup-diagnostic models plus pure functions for:

- finding daily actionable winners;
- exact-date candidate attribution;
- market-freeze diagnostic rows; and
- closest-template no-setup diagnostics.

The case runtime constructs daily cohorts after replay using bars, point-in-time risk flags, point-in-time holdings, and the existing five-session trading calendar. `CaseReview` receives defaulted daily-recall fields so current fixtures remain compatible.

The report schema advances from `buy-point-case-review-v4` to `buy-point-case-review-v5`. It preserves all v4 fields and adds:

- `daily_recall_winners`;
- `daily_recall_metrics`;
- `market_freeze_diagnostics`;
- `no_setup_diagnostics`; and
- aggregate diagnostic counts by signal date, setup template, and failed condition.

The Markdown report adds `逐日五日召回` and `无买点形态诊断` sections. Existing v1 through v4 artifacts remain immutable.

## Data Flow

1. Load the existing bounded case inputs without additional data sources.
2. Replay existing signal-date gates and candidates unchanged.
3. For each signal date, resolve exactly five later trading sessions.
4. Find actionable winners using only that signal date's history and five-session outcome bars.
5. Attribute candidates and rejection traces by exact `(signal_date, code)`.
6. Diagnose market-vetoed and no-setup missed winners from signal-time bars only.
7. Render immutable v5 daily and aggregate evidence.

No outcome information enters setup diagnostics, ranking, or signal-time failure selection. Outcome bars only label the independently constructed hindsight winner cohort.

## Failure Handling

- Fewer than five outcome sessions makes the daily cohort incomplete.
- Missing signal-date bars, incomplete holdings, incomplete market/reference inputs, or absent traces remain explicit.
- Non-positive or non-finite prices exclude the affected winner row.
- Diagnostic metrics that cannot be calculated remain null with an explicit insufficient-history reason.
- Missing sector membership does not get inferred.
- Market-freeze diagnostics never create a formal or near-miss candidate.
- Every diagnostic row has zero executable shares and `NO-TRADE` permission.

## Frozen Validation

Regenerate the same three windows under one unchanged v5 implementation:

- July 20–24 with outcomes through July 31;
- July 27–31 with outcomes through August 7; and
- August 3–7 with outcomes through August 14.

For each window, compare the old final-date count with the new exact daily stock-date count, verify exact-date capture, and report market-freeze setup presence plus no-setup failure distributions. Do not select a fourth setup or tune a threshold during this iteration.

## Safety

- Production setup detectors and their return values remain unchanged.
- Production market, sector, anti-chase, base, planning, sizing, and validation gates remain unchanged.
- Rule version stays `buy-point-selection-3.1.0`.
- No holding, decision memory, promotion profile, notification, or order mutation is allowed.
- MySQL remains read-only and generated reports remain ignored by Git.
- All new outputs remain `CASE_ANALYSIS_ONLY / NO-TRADE`.

## Tests

Tests must prove:

- each signal date uses its own next five trading sessions;
- a gain before the first qualifying entry does not create a winner;
- a normal entry followed by 5% upside does create a winner;
- locked limit-up and greater-than-3% gap entries are rejected;
- exact-date attribution cannot use a candidate from another signal date;
- exact-date rejection cannot use another date's trace;
- incomplete five-session horizons fail closed;
- future bars outside the horizon cannot change a winner or diagnosis;
- market-freeze diagnostics remain zero-share and never create candidates;
- production-positive fixtures have zero corresponding setup-diagnostic failures;
- closest-window selection is deterministic for trend and launch diagnostics;
- outcome bars cannot affect setup diagnostics;
- v5 identity differs from v4 and all v4 payload fields remain present;
- daily and aggregate numerators reconcile exactly; and
- production planning, setup detection, validation, holdings, and memory behavior remain unchanged.

## Acceptance Criteria

The feature is complete when:

- all three frozen windows contain complete exact daily five-session recall cohorts;
- every capture and rejection is joined by exact signal date and code;
- market-freeze and no-setup losses have auditable signal-time diagnostics;
- the report identifies the dominant missing shape constraints without changing them;
- all research rows remain zero-share and non-trading;
- the broader buy-point regression passes; and
- no production selection or portfolio state changes.
