# Daily Recall Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact signal-date five-session winner recall, market-freeze research rows, and deterministic no-setup diagnostics to immutable v5 case reviews.

**Architecture:** A new pure `recall_research.py` module owns hindsight winner, attribution, and setup-diagnostic models without importing the report or runtime. The existing read-only case runtime assembles daily cohorts from bounded inputs and stores them in defaulted `CaseReview` fields. The report advances to v5, preserves every v4 key, and adds raw and aggregate daily-recall evidence.

**Tech Stack:** Python 3.11, frozen dataclasses, `Decimal`, SQLAlchemy-backed read-only case inputs, pytest, deterministic JSON/Markdown reporting.

## Global Constraints

- Production setup detectors and their return values remain unchanged.
- Production market, sector, anti-chase, base, planning, sizing, and validation gates remain unchanged.
- Rule version stays `buy-point-selection-3.1.0`.
- No holding, decision memory, promotion profile, notification, or order mutation is allowed.
- MySQL remains read-only and generated reports remain ignored by Git.
- All new outputs remain `CASE_ANALYSIS_ONLY / NO-TRADE` with zero executable shares.
- Winner construction uses exactly five trading sessions and exact `(signal_date, code)` attribution.
- Existing v1 through v4 artifacts remain immutable.

---

### Task 1: Find daily actionable winners without future leakage

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/recall_research.py`
- Create: `stock-ai/tests/unit/test_buy_point_recall_research.py`

**Interfaces:**
- Consumes: one signal date, exactly five outcome dates, `bars_by_code`, point-in-time risk flags, point-in-time holding codes, and `SelectionPolicy`.
- Produces: `DailyRecallWinner`, `DailyRecallCohort`, `next_five_trading_dates(...)`, and `find_daily_actionable_winners(...)`.

- [ ] **Step 1: Write the failing normal-entry winner test**

Create 60 signal-time bars ending at 10.00 and five outcome bars. The first normal outcome opens at 10.00 and a later high reaches 10.60. Assert the wished-for API returns one literal winner:

```python
winner = cohort.winners[0]
assert winner.code == "600001"
assert winner.signal_date == date(2026, 8, 3)
assert winner.horizon_end_date == date(2026, 8, 10)
assert winner.entry_date == date(2026, 8, 4)
assert winner.entry_price == Decimal("10.00")
assert winner.forward_maximum_gain == Decimal("0.06")
assert winner.maximum_gain_date == date(2026, 8, 6)
assert winner.executable_shares == 0
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_recall_research.py::test_normal_entry_before_five_percent_gain_is_actionable
```

Expected: collection fails because `recall_research` does not exist.

- [ ] **Step 3: Add immutable winner and cohort models**

Implement:

```python
@dataclass(frozen=True)
class DailyRecallWinner:
    code: str
    signal_date: date
    horizon_end_date: date
    entry_date: date
    entry_price: Decimal
    forward_maximum_gain: Decimal
    maximum_gain_date: date
    captured_tiers: tuple[str, ...] = ()
    first_rejection: str | None = None
    executable_shares: int = 0


@dataclass(frozen=True)
class DailyRecallCohort:
    signal_date: date
    outcome_dates: tuple[date, ...]
    complete: bool
    winners: tuple[DailyRecallWinner, ...]
```

`next_five_trading_dates(signal_date, trading_dates, cutoff)` returns the first five unique sorted dates strictly after the signal date and no later than cutoff.

- [ ] **Step 4: Implement minimal actionable-winner construction**

Fail closed unless `outcome_dates` contains exactly five dates. Reuse the current hindsight eligibility boundary: main-board code, not held, no signal-date VETO, valid signal-date history with at least five bars, and five-day average amount at or above `policy.min_average_amount5_qian`.

For each normal entry day, calculate the maximum later high including that day from its opening price. Select the earliest entry whose forward maximum gain is at least 5%; on equal maximum highs, select the earliest date.

- [ ] **Step 5: Verify GREEN and add boundary tests one at a time**

Each test must be written and observed failing before the corresponding code branch:

- a locked one-price limit-up entry is skipped;
- an opening gap strictly greater than 3% is skipped;
- a gain that occurs before the first qualifying entry does not create a winner;
- a sixth-session high cannot affect the five-session result;
- four outcome dates produce `complete=False` and no winners;
- held, VETO, illiquid, and non-main-board codes remain excluded; and
- invalid or non-finite entry prices are excluded.

- [ ] **Step 6: Run the complete recall-research test module**

Expected: all winner-construction tests pass with no warnings.

- [ ] **Step 7: Commit daily winner construction**

```bash
git add stock_ai/buy_point_selection/recall_research.py \
  tests/unit/test_buy_point_recall_research.py
git commit -m "feat(stock-ai): build exact daily recall winners"
```

---

### Task 2: Attribute winners by exact signal date and diagnose market freezes

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/recall_research.py`
- Modify: `stock-ai/tests/unit/test_buy_point_recall_research.py`

**Interfaces:**
- Consumes: `DailyRecallWinner`, `CaseSignalReplay`, signal-time bars, holdings, risk flags, and `SelectionPolicy`.
- Produces: `attribute_daily_recall_winners(...)`, `MarketFreezeDiagnostic`, and `diagnose_market_freeze_winners(...)`.

- [ ] **Step 1: Write the failing exact-date attribution test**

Construct a winner for August 4, a candidate for the same code on August 3, and distinct traces on both dates. Assert the August 3 candidate and trace cannot capture or explain the August 4 winner:

```python
assert attributed.captured_tiers == ()
assert attributed.first_rejection == "NO_BUY_POINT_SETUP"
```

- [ ] **Step 2: Run the test and verify RED**

Expected: import failure because `attribute_daily_recall_winners` does not exist.

- [ ] **Step 3: Implement exact-date attribution**

Index candidates by `(candidate.signal_date, normalize_code6(candidate.code))` and read only `replay.traces[(winner.signal_date, winner.code)]`. Sort tiers and return replaced immutable winner rows.

- [ ] **Step 4: Write the failing zero-share market-freeze diagnostic test**

Use a winner whose exact trace first rejection is `INDEX_AND_BREADTH_WEAK` and whose signal-time bars match an existing setup fixture. Assert:

```python
assert row.market_reason == "INDEX_AND_BREADTH_WEAK"
assert row.base_passed
assert row.setup_types == ("PRE_BREAKOUT",)
assert row.executable_shares == 0
```

Also assert the replay's strict and near-miss candidates remain unchanged.

- [ ] **Step 5: Implement the market-freeze diagnostic model and builder**

```python
@dataclass(frozen=True)
class MarketFreezeDiagnostic:
    code: str
    signal_date: date
    market_reason: str
    base_passed: bool
    base_reasons: tuple[str, ...]
    setup_types: tuple[str, ...]
    setup_qualities: tuple[Decimal, ...]
    executable_shares: int = 0
```

Admit only missed winners with exact first rejection in `{INDEX_AND_BREADTH_WEAK, AMOUNT_AND_BREADTH_WEAK}`. Bound bars on or before the signal date, run existing `base_gate` and `detect_setups` for diagnosis, and never build a candidate or plan.

- [ ] **Step 6: Run the recall and case-review tests**

Expected: attribution and market-freeze tests pass; existing candidate counts remain unchanged.

- [ ] **Step 7: Commit exact attribution and market diagnostics**

```bash
git add stock_ai/buy_point_selection/recall_research.py \
  tests/unit/test_buy_point_recall_research.py
git commit -m "feat(stock-ai): diagnose exact-date market misses"
```

---

### Task 3: Diagnose the nearest failed setup template

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/recall_research.py`
- Modify: `stock-ai/tests/unit/test_buy_point_recall_research.py`
- Read-only reference: `stock-ai/stock_ai/buy_point_selection/patterns.py`

**Interfaces:**
- Consumes: signal-time bars and current `SelectionPolicy` values.
- Produces: `SetupTemplateDiagnostic` and `diagnose_no_setup(code, signal_date, bars, policy) -> tuple[SetupTemplateDiagnostic, ...]`.

- [ ] **Step 1: Write failing production-positive parity tests**

For the literal platform, trend-pullback, and first-launch fixtures already used by production detector tests, assert the matching template diagnostic has no failures and identical principal metrics. Example:

```python
diagnostic = _by_template(diagnose_no_setup("600001", SIGNAL, bars), "PRE_BREAKOUT")
assert diagnostic.failures == ()
assert diagnostic.metrics["distance_to_platform_top"] == Decimal("0.010556...")
```

Use hand-derived literal values from the fixture rather than calling the detector for expected results.

- [ ] **Step 2: Run parity tests and verify RED**

Expected: import failure because the diagnostic API is absent.

- [ ] **Step 3: Implement the immutable diagnostic model and numeric deviation helper**

```python
@dataclass(frozen=True)
class SetupTemplateDiagnostic:
    code: str
    signal_date: date
    template: str
    window_sessions: int | None
    failures: tuple[str, ...]
    boundary_deviation: Decimal
    metrics: Mapping[str, Decimal]
    executable_shares: int = 0
```

Use zero deviation inside a valid bound. Outside a maximum, use `(value - maximum) / abs(maximum)`; outside a minimum, use `(minimum - value) / abs(minimum)`. Boolean failures add one. Invalid metrics use `Decimal("Infinity")` and an explicit history or invalid-input failure.

- [ ] **Step 4: Mirror the pre-breakout diagnostic gates**

Record exact production metrics and these failure names:

```text
PLATFORM_HISTORY_SHORT
PLATFORM_WIDTH_WIDE
PLATFORM_NOT_NEAR_TOP
PLATFORM_RANGE_NOT_CONTRACTED
PLATFORM_AMOUNT_NOT_CONTRACTED
PLATFORM_MA20_NOT_RISING
```

The production-positive fixture must have no failures.

- [ ] **Step 5: Mirror trend windows and choose the closest deterministically**

Evaluate 2, 3, and 4 sessions with failure names corresponding to the production conditions. Choose by `(len(failures), boundary_deviation, session_count)`. Add a literal test where the 3-session window has one failure and the others have two, and assert `window_sessions == 3`.

- [ ] **Step 6: Mirror launch windows and choose the closest deterministically**

Evaluate quiet windows 1 and 2 with exact production conditions, including the preceding-three-up exclusion. Choose by `(len(failures), boundary_deviation, quiet_sessions)`. Assert the production-positive launch fixture selects two sessions with no failures.

- [ ] **Step 7: Prove future bars cannot change diagnostics**

Append a large future bar after the requested signal date and assert the full diagnostic tuple is unchanged.

- [ ] **Step 8: Run pattern and diagnostic tests together**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_recall_research.py \
  tests/unit/test_buy_point_patterns.py
```

Expected: both production detector and research diagnostic tests pass.

- [ ] **Step 9: Commit setup diagnostics**

```bash
git add stock_ai/buy_point_selection/recall_research.py \
  tests/unit/test_buy_point_recall_research.py
git commit -m "feat(stock-ai): diagnose missing buy-point shapes"
```

---

### Task 4: Attach daily recall evidence to the read-only runtime

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_review.py`
- Modify: `stock-ai/scripts/analysis/review_buy_point_case.py`
- Modify: `stock-ai/tests/unit/test_review_buy_point_case_cli.py`

**Interfaces:**
- Consumes: daily recall and diagnostic APIs from `recall_research.py` plus `CaseReviewInputs`.
- Produces: `_build_daily_recall(...)` and defaulted `CaseReview` fields for cohorts, market diagnostics, and no-setup diagnostics.

- [ ] **Step 1: Write the failing bounded runtime test**

Inject two signal dates, ten later trading dates, one winner per signal date, a Monday-only candidate, and exact traces. Assert the runtime stores two complete cohorts and does not use the Monday candidate to capture Tuesday.

- [ ] **Step 2: Run the focused test and verify RED**

Expected: failure because `_build_daily_recall` and `CaseReview` storage are absent.

- [ ] **Step 3: Add type-only defaulted storage**

Avoid circular imports with `TYPE_CHECKING` and add final default fields:

```python
daily_recall_cohorts: tuple["DailyRecallCohort", ...] = ()
market_freeze_diagnostics: tuple["MarketFreezeDiagnostic", ...] = ()
no_setup_diagnostics: tuple["SetupTemplateDiagnostic", ...] = ()
```

- [ ] **Step 4: Implement `_build_daily_recall`**

For every signal date, resolve exactly five later trading dates through the effective cutoff. A cohort is incomplete when the horizon is short, holdings are incomplete, the signal date appears in replay incompleteness, or required point-in-time coverage is absent. For complete dates, build winners, attribute exact candidates and traces, then build diagnostics only for missed winners.

Return all three tuples sorted by signal date, code, and template without mutating replay candidates.

- [ ] **Step 5: Integrate after existing episode and resistance assembly**

Pass the returned tuples to `CaseReview`. Preserve the existing legacy final-date `winners` field for v4 compatibility; v5 decisions use only daily recall fields.

- [ ] **Step 6: Run runtime, recall, and case tests**

Expected: all injected fixtures and backward-compatible `CaseReview` constructions pass.

- [ ] **Step 7: Commit runtime integration**

```bash
git add stock_ai/buy_point_selection/case_review.py \
  scripts/analysis/review_buy_point_case.py \
  tests/unit/test_review_buy_point_case_cli.py
git commit -m "feat(stock-ai): attach daily recall diagnostics"
```

---

### Task 5: Render immutable v5 daily recall reports

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_report.py`
- Modify: `stock-ai/tests/unit/test_buy_point_case_report.py`

**Interfaces:**
- Consumes: `CaseReview.daily_recall_cohorts`, market-freeze diagnostics, and no-setup diagnostics.
- Produces: schema `buy-point-case-review-v5`, raw rows, reconciled daily and aggregate metrics, diagnostic counts, and Markdown sections.

- [ ] **Step 1: Write the failing v5 identity and preservation test**

Assert schema v5 differs from v4 and all v4 keys remain. Serialize a literal winner and assert every price, date, tier, rejection, and zero-share field.

- [ ] **Step 2: Run the focused test and verify RED**

Expected: schema remains v4 and daily fields are missing.

- [ ] **Step 3: Serialize deterministic daily recall and diagnostics**

Add:

```text
daily_recall_winners
daily_recall_metrics
market_freeze_diagnostics
no_setup_diagnostics
setup_diagnostic_counts
```

Sort raw rows by signal date, code, then template. Serialize `Decimal` as strings and preserve zero-share safety fields.

- [ ] **Step 4: Write failing reconciliation tests**

Create two daily cohorts with literal winner rows and assert aggregate winner pairs, unique codes, captured pairs, tier counts, rejection counts, complete dates, and incomplete dates equal hand-derived values. Assert raw daily counts sum exactly to the aggregate pair counts.

- [ ] **Step 5: Implement metrics and diagnostic counters**

Count stock-date pairs, not independent samples. Count unique codes separately. Group setup diagnostic failures by template and literal failure reason; group market diagnostics by reason, base pass, and setup presence.

- [ ] **Step 6: Render Markdown safety sections**

Add `逐日五日召回` and `无买点形态诊断`. State that stock-date rows overlap and are not independent, and that market-freeze/setup diagnostics cannot authorize trades.

- [ ] **Step 7: Run report and all new-feature tests**

Expected: v5, runtime, recall, pattern, and prior v4 assertions all pass.

- [ ] **Step 8: Commit v5 reporting**

```bash
git add stock_ai/buy_point_selection/case_report.py \
  tests/unit/test_buy_point_case_report.py
git commit -m "feat(stock-ai): report exact daily recall evidence"
```

---

### Task 6: Verify isolation and run the three frozen LAN cases

**Files:**
- Verify only: `stock-ai/stock_ai/buy_point_selection/patterns.py`
- Verify only: `stock-ai/stock_ai/buy_point_selection/planning.py`
- Runtime output, ignored: `stock-ai/output/research/buy_point_cases/`

**Interfaces:**
- Consumes: completed v5 implementation and MySQL at `192.168.1.13:3306` through an in-memory URL override.
- Produces: fresh regression evidence, three immutable v5 revisions, and setup-failure distributions without formal rule changes.

- [ ] **Step 1: Run the broader buy-point regression suite**

Run the existing 11-module suite plus `test_buy_point_recall_research.py`. Expected: all tests pass without warnings.

- [ ] **Step 2: Verify production isolation**

Run pattern and planning tests independently, compile touched modules, run `git diff --check`, and confirm both `git diff -- patterns.py` and `git diff -- planning.py` are empty.

- [ ] **Step 3: Generate frozen v5 revisions**

Use one unchanged code version for:

```text
2026-07-20..2026-07-24 -> cutoff 2026-07-31
2026-07-27..2026-07-31 -> cutoff 2026-08-07
2026-08-03..2026-08-07 -> cutoff 2026-08-14
```

- [ ] **Step 4: Audit exact-date reconciliation and safety**

For each artifact verify five complete daily cohorts, exact daily sums, raw winner count, unique code count, captured pair count, market and no-setup diagnostic counts, zero executable shares, v5 schema, `CASE_ANALYSIS_ONLY`, and `NO-TRADE`.

- [ ] **Step 5: Report dominant missing-shape evidence**

Aggregate template failure counts across all three frozen windows without changing parameters. Report which exact constraints dominate for pre-breakout, trend-pullback, and first-launch-pullback, split from market-freeze rows. Do not add a setup or propose formal threshold promotion in code.

- [ ] **Step 6: Final tracked-file audit**

Confirm generated reports are ignored, scoped implementation files are clean after commits, and no production detector, planner, holdings, memory, or order path changed. If LAN integration reveals a defect, first add a failing test, apply the smallest fix, and rerun the full suite.
