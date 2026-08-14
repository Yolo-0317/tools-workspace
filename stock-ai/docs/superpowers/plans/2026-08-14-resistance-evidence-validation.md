# Resistance Evidence Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct point-in-time holdings reconstruction, split observed-level and no-level resistance passes in immutable v4 case reports, and run two frozen July validation windows.

**Architecture:** The existing case loader will reconstruct every requested signal date from the latest authoritative EOD snapshot plus later per-code position events. A pure resistance-evidence classifier will derive one of four bases without changing profile math, and the report will add setup-aware evidence cohorts under a new immutable v4 schema. Validation continues through the read-only manual case command and writes only ignored research artifacts.

**Tech Stack:** Python 3.11, SQLAlchemy Core, frozen dataclasses, `Decimal`, pytest, MySQL read-only runtime, deterministic JSON/Markdown reporting.

## Global Constraints

- Production `planning.py`, `nearest_resistance_above`, `build_price_plan`, rule version `buy-point-selection-3.1.0`, and every formal threshold remain unchanged.
- MySQL access is read-only; do not insert or update snapshots, events, holdings, memory, profiles, or orders.
- A prior EOD snapshot is required for complete holdings reconstruction; events alone never establish completeness.
- Future snapshots and events cannot affect earlier signal dates.
- Existing v1, v2, and v3 artifacts remain immutable.
- Every resistance opportunity remains zero-share and `CASE_ANALYSIS_ONLY / NO-TRADE`.
- Parameters remain frozen across both July validation windows and the August reconciliation run.
- Generated case artifacts stay ignored by Git.

---

### Task 1: Reconstruct missing-day holdings from the latest EOD snapshot

**Files:**
- Modify: `stock-ai/scripts/analysis/review_buy_point_case.py`
- Modify: `stock-ai/tests/unit/test_review_buy_point_case_cli.py`

**Interfaces:**
- Consumes: `_load_holdings_by_date(engine, signal_dates)` and the existing `portfolio_account_daily`, `portfolio_positions_daily`, and `portfolio_position_events` tables.
- Produces: the same `(holdings_by_date, complete_by_date)` return type with corrected point-in-time semantics.

- [ ] **Step 1: Change the existing missing-day test to require snapshot carry-forward**

Use a literal SQLite fixture with an August 3 EOD snapshot containing `600001`, no August 4 snapshot, and an August 4 event setting `600002` to 200 shares. Assert August 4 contains both unchanged `600001` and changed `600002`, while both dates are complete.

```python
assert holdings[first] == frozenset({"600001"})
assert holdings[second] == frozenset({"600001", "600002"})
assert complete == {first: True, second: True}
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_review_buy_point_case_cli.py::test_historical_holdings_use_daily_snapshot_then_append_only_events
```

Expected: failure because the current missing-day branch discards the prior snapshot and returns only `600002`.

- [ ] **Step 3: Query an anchor snapshot and reconstruct each requested date**

In `_load_holdings_by_date`:

1. Query `MAX(snapshot_date)` for EOD snapshots no later than the first requested date.
2. Load all EOD account and position rows from that anchor, or the first requested date when no anchor exists, through the final requested date.
3. Load ordered position events only inside the required reconstruction interval.
4. For each signal date, choose the latest snapshot date no later than it.
5. Copy that snapshot's per-code share state, then apply events whose timestamp is at or after the next-day boundary of the snapshot and before the next-day boundary of the signal date.
6. Return positive-share codes and `complete=True`; when no earlier snapshot exists, return an empty set and `complete=False`.

- [ ] **Step 4: Verify GREEN and add literal event-boundary tests**

Add tests proving:

- a later zero-share event removes a carried code;
- sequential buy and sell events use timestamp order;
- an exact-date snapshot is authoritative and does not double-apply same-day events;
- a requested date before the first snapshot remains incomplete; and
- a future event does not leak backward.

Run the complete CLI test module and confirm every test passes.

- [ ] **Step 5: Commit the holdings correction**

```bash
git add scripts/analysis/review_buy_point_case.py \
  tests/unit/test_review_buy_point_case_cli.py
git commit -m "fix(stock-ai): reconstruct missing-day holdings"
```

---

### Task 2: Derive explicit resistance evidence bases

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/resistance_research.py`
- Modify: `stock-ai/tests/unit/test_buy_point_resistance_research.py`

**Interfaces:**
- Consumes: `ResistanceVariantProfile` and the containing profile's `complete` value.
- Produces: `resistance_evidence_basis(complete: bool, variant: ResistanceVariantProfile) -> str` plus public constants `LEVEL_AT_OR_ABOVE_2R`, `NO_LEVEL`, `LEVEL_BELOW_2R`, and `INCOMPLETE`.

- [ ] **Step 1: Write the failing four-way evidence classification test**

Create four literal variants and assert:

```python
assert resistance_evidence_basis(True, level_pass) == "LEVEL_AT_OR_ABOVE_2R"
assert resistance_evidence_basis(True, no_level) == "NO_LEVEL"
assert resistance_evidence_basis(True, below_level) == "LEVEL_BELOW_2R"
assert resistance_evidence_basis(False, no_level) == "INCOMPLETE"
```

The test must also assert that only `LEVEL_AT_OR_ABOVE_2R` and `NO_LEVEL` correspond to existing `passes_two_r=True` values.

- [ ] **Step 2: Run the focused test and verify RED**

Expected: import failure because the classifier and constants do not exist.

- [ ] **Step 3: Implement the minimal pure classifier**

Use this precedence:

```python
if not complete:
    return INCOMPLETE
if variant.level is None:
    return NO_LEVEL
if variant.passes_two_r:
    return LEVEL_AT_OR_ABOVE_2R
return LEVEL_BELOW_2R
```

Do not change resistance levels, clustering, tolerance, pass flags, or production planning.

- [ ] **Step 4: Run resistance and planning tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_resistance_research.py \
  tests/unit/test_buy_point_planning.py
```

Expected: all tests pass and `planning.py` remains unchanged.

- [ ] **Step 5: Commit evidence classification**

```bash
git add stock_ai/buy_point_selection/resistance_research.py \
  tests/unit/test_buy_point_resistance_research.py
git commit -m "feat(stock-ai): classify resistance pass evidence"
```

---

### Task 3: Render immutable v4 evidence cohorts

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_report.py`
- Modify: `stock-ai/tests/unit/test_buy_point_case_report.py`

**Interfaces:**
- Consumes: `CaseReview.resistance_profiles`, `resistance_evidence_basis`, existing exact representative outcome joins, and existing v3 payload fields.
- Produces: schema `buy-point-case-review-v4`, serialized `evidence_basis`, `resistance_evidence_comparison`, completeness metrics, and an evidence-split Markdown section.

- [ ] **Step 1: Write the failing v4 identity and serialization test**

Assert that the schema is v4, its identity differs from v3, every existing v3 top-level key remains present, and serialized variants contain literal evidence values:

```python
assert payload["schema"] == "buy-point-case-review-v4"
assert payload["resistance_profiles"][0]["variants"][0]["evidence_basis"] == "LEVEL_BELOW_2R"
assert payload["resistance_profiles"][0]["variants"][2]["evidence_basis"] == "NO_LEVEL"
```

- [ ] **Step 2: Run the focused report test and verify RED**

Expected: failure because the current schema is v3 and variants do not serialize evidence basis.

- [ ] **Step 3: Advance the immutable schema and serialize evidence**

Set `CASE_REPORT_SCHEMA` to `buy-point-case-review-v4`. Preserve all v3 keys and add `evidence_basis` to each variant payload using the containing profile's completeness flag.

- [ ] **Step 4: Write the failing evidence-cohort outcome test**

Create one setup with two passing profiles: one level at 2.2R with a triggered success and one no-level pass with an expired outcome. Assert separate rows keyed by `(setup_type, variant, evidence_basis)`:

```python
assert level_row["cohort_opportunities"] == 1
assert level_row["triggered"] == 1
assert level_row["successes"] == 1
assert level_row["mean_net_return"] == "0.06"
assert no_level_row["cohort_opportunities"] == 1
assert no_level_row["triggered"] == 0
assert no_level_row["successes"] == 0
assert no_level_row["mean_net_return"] is None
```

- [ ] **Step 5: Implement exact evidence comparisons**

For every setup type and variant, build rows only for passing bases `LEVEL_AT_OR_ABOVE_2R` and `NO_LEVEL`. Reuse the exact representative key `(code, signal_date, tier, structure_id)`. Count complete profiles before cohort filtering; exclude missing outcomes from resolved denominators; average only non-null values; sort by setup type, variant order, then evidence basis.

- [ ] **Step 6: Render Markdown and verify safety language**

Add compact level-pass and no-level-pass rows under `显著阻力证据拆分`. Include the literal statement `未发现阻力不等于已证明上涨空间` and preserve `CASE_ANALYSIS_ONLY / NO-TRADE`.

- [ ] **Step 7: Run all report, runtime, case, and resistance tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_resistance_research.py \
  tests/unit/test_buy_point_case_report.py \
  tests/unit/test_buy_point_case_review.py \
  tests/unit/test_review_buy_point_case_cli.py
```

- [ ] **Step 8: Commit v4 reporting**

```bash
git add stock_ai/buy_point_selection/case_report.py \
  tests/unit/test_buy_point_case_report.py
git commit -m "feat(stock-ai): report resistance evidence cohorts"
```

---

### Task 4: Verify isolation and run frozen LAN validation

**Files:**
- Verify only: `stock-ai/stock_ai/buy_point_selection/planning.py`
- Runtime output, ignored: `stock-ai/output/research/buy_point_cases/`

**Interfaces:**
- Consumes: completed v4 code and MySQL at `192.168.1.13:3306` through an in-memory URL host override.
- Produces: fresh regression evidence plus three immutable v4 JSON/Markdown revisions.

- [ ] **Step 1: Run the broader buy-point regression suite**

Run the same 11-module suite used for v3, now including the new v4 tests. Expected: every test passes without warnings.

- [ ] **Step 2: Verify production isolation**

Run `tests/unit/test_buy_point_planning.py` independently, compile all touched Python modules, run `git diff --check`, and confirm `git diff -- stock_ai/buy_point_selection/planning.py` is empty.

- [ ] **Step 3: Verify August 5 holdings through the real read-only loader**

Load August 3–7 through `load_mysql_case_inputs` with an in-memory host override. Assert all five `holdings_complete_by_date` values are true and August 5 carries the eight positive-share codes visible on August 4 and August 6. Do not print credentials.

- [ ] **Step 4: Generate three frozen v4 case revisions**

Run the manual case command for:

```text
2026-07-20..2026-07-24 -> cutoff 2026-07-31
2026-07-27..2026-07-31 -> cutoff 2026-08-07
2026-08-03..2026-08-07 -> cutoff 2026-08-14
```

Use the same code and thresholds for all three runs. Expected: exit zero, v4 schema, `CASE_ANALYSIS_ONLY`, and `NO-TRADE`.

- [ ] **Step 5: Audit frozen results**

For each artifact, report raw candidates, deduplicated opportunities, profile completeness, level-pass and no-level-pass cohorts by setup, triggered/resolved/success/stop counts, mean net return, incomplete dates, and missed-winner recall availability. Confirm every profiled opportunity has zero executable shares and every profile has exactly three variants.

- [ ] **Step 6: Final tracked-file audit**

Confirm only scoped source, test, spec, and plan commits were created; generated artifacts are untracked-ignore output and `planning.py` is unchanged. If integration reveals a defect, reproduce it with a failing test before applying the smallest correction and rerun the full suite.
