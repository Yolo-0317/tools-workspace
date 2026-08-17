# Five-Day Ranking V3 Same-Day Attribution Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve completed same-day entry/exit trades in V3 train attribution by assigning zero close-to-close benchmark returns while retaining all hard coverage checks.

**Architecture:** Keep the existing attribution pipeline and artifact schema unchanged. Amend only the interval ordering boundary in the pure attribution domain, prove both public interval and real builder behavior through TDD, then resume the already-approved one-off real train attribution run.

**Tech Stack:** Python 3.11, `Decimal`, pytest, Ruff, immutable JSON artifacts, SQLAlchemy read-only MySQL loader, existing BaoStock/Eastmoney benchmark loader.

## Global Constraints

- Keep the diagnostic train-only and `NO-TRADE`.
- Do not change V1, V2, V3 ranking, qualification, promotion, or validation behavior.
- Do not read validation or test outcomes.
- Do not invoke freeze, forward, settlement, notification, holding, memory, order, or trading flows.
- Do not store observation rows, stock codes, positions, credentials, or raw provider responses in the attribution artifact.
- A same-day interval still requires the matched-index close and at least 1,000 valid same-universe closes for that date.
- Accept `start == end`; reject `start > end` and any endpoint outside the bounded train calendar.
- Preserve unrelated dirty-worktree changes and never stage generated real attribution artifacts.

---

### Task 1: Correct the Same-Day Interval Boundary Through TDD

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py:668-740`
- Modify: `tests/unit/test_five_day_ranking_v3_attribution.py:178-275`
- Modify: `tests/unit/test_five_day_ranking_v3_attribution.py:350-430`

**Interfaces:**
- Consumes: `MarketClosePanel`, `attribute_interval()`, `build_five_day_ranking_v3_attribution_review()`, and the existing completed-training fixture.
- Produces: same-day dual-benchmark returns of exactly `Decimal("0")`; actual trade `net_return`, gross return, and cost drag remain unchanged; reversed intervals still raise `ValueError`.

- [ ] **Step 1: Add a failing public interval test**

Add this hand-derived case next to the existing interval attribution tests:

```python
def test_interval_attribution_accepts_same_day_with_zero_benchmarks() -> None:
    panel = _market_panel()
    value = attribute_interval("600001", START, START, panel)

    assert value.raw_return == Decimal("0")
    assert value.matched_index_return == Decimal("0")
    assert value.market_median_return == Decimal("0")
    assert value.index_excess == Decimal("0")
    assert value.market_median_excess == Decimal("0")
    assert value.market_members == 1000
```

This test catches either boundary guard continuing to reject equality or benchmark arithmetic fabricating a non-zero same-day return.

- [ ] **Step 2: Add a failing actual-holding builder regression**

Add a test-only helper that replaces the completed evaluation's exit date and resolution date with its existing entry date, rebuilds the research and strict V3 train artifact, and supplies closes only for the signal and same-day entry/exit endpoints:

```python
def test_attribution_builder_keeps_same_day_actual_trade() -> None:
    _, research, evaluation = _completed_training_fixture()
    entry_date = evaluation.trade.entry_date
    assert entry_date is not None
    assert evaluation.trade.exit is not None
    same_day = replace(
        evaluation,
        resolution_date=entry_date,
        trade=replace(
            evaluation.trade,
            exit=replace(
                evaluation.trade.exit,
                planned_exit_date=entry_date,
                actual_exit_date=entry_date,
            ),
        ),
    )
    same_day_research = replace(
        research,
        observations=tuple(
            same_day if value is evaluation else value
            for value in research.observations
        ),
    )
    artifact = _artifact_from_research(same_day_research)
    signal_date = same_day.plan.candidate.signal_date
    panel = _bounded_market_panel(
        artifact.split.train,
        (signal_date, entry_date),
        target_closes={
            signal_date: Decimal("10"),
            entry_date: Decimal("10.5"),
        },
    )

    review = build_five_day_ranking_v3_attribution_review(
        artifact,
        same_day_research,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=panel,
    )

    actual = review.variants[0].actual
    assert actual.completed_rows == 1
    assert actual.mean_return == Decimal("0.04")
    assert actual.mean_matched_index_return == Decimal("0")
    assert actual.mean_market_median_return == Decimal("0")
    assert actual.mean_index_excess == Decimal("0.04")
    assert actual.mean_market_median_excess == Decimal("0.04")
    assert review.status == "COMPLETE"
```

- [ ] **Step 3: Add a failing reversed-interval test**

```python
def test_interval_attribution_rejects_reversed_dates() -> None:
    panel = _market_panel()

    with pytest.raises(ValueError, match="interval endpoints must be train dates"):
        attribute_interval("600001", END, START, panel)
```

This prevents the equality fix from accepting genuine reverse chronology.

- [ ] **Step 4: Run the three named tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py::test_interval_attribution_accepts_same_day_with_zero_benchmarks \
  tests/unit/test_five_day_ranking_v3_attribution.py::test_attribution_builder_keeps_same_day_actual_trade \
  tests/unit/test_five_day_ranking_v3_attribution.py::test_interval_attribution_rejects_reversed_dates -q
```

Expected: the first two tests fail with `interval endpoints must be train dates in order`; the reversed test passes and protects the existing strict branch.

- [ ] **Step 5: Implement the minimal boundary correction**

In `_benchmark_interval()` and `attribute_interval()`, change only the ordering condition:

```python
if start not in train_dates or end not in train_dates or start > end:
    raise ValueError("interval endpoints must be train dates in order")
```

Do not special-case returns to zero. Existing `simple_return(close, close)` and same-date cross-sectional calculation must naturally produce exact zeros while still validating the index close and 1,000-member market coverage.

- [ ] **Step 6: Run the named tests and the attribution suites**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py \
  tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py -q
```

Expected: zero failures, including the same-day builder regression and all incomplete-coverage behavior.

- [ ] **Step 7: Run static checks and commit only the fix**

```bash
ruff check \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
.venv/bin/python -m compileall -q \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git diff --check -- \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git add \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git diff --cached --check
git commit -m "fix(stock-ai): allow same-day market attribution"
```

---

### Task 2: Resume the One-Off Real Train Attribution and Stop

**Files:**
- Read: `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
- Read: `output/research/buy_point_five_day_returns/ranking-train-d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3.json`
- Read: `output/research/buy_point_five_day_returns/ranking-v2-train-99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22.json`
- Read: `output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json`
- Generate but never stage: `output/research/buy_point_five_day_returns/ranking-v3-train-attribution-<identity>.json`

**Interfaces:**
- Consumes: the corrected pure attribution boundary, immutable parent artifacts, configured read-only `MYSQL_URL`, and existing benchmark providers.
- Produces: one strict aggregate-only train attribution artifact, an idempotency proof, unchanged V1/V2/V3 identities, and a descriptive `NO-TRADE` report.

- [ ] **Step 1: Rerun the complete Task 7 suite**

Run the exact 20-file, 472-test command from Task 7 in `2026-08-17-v3-market-strategy-attribution.md`. Expected: zero failures before any real data access.

- [ ] **Step 2: Run the manual attribution command once**

```bash
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking_v3_attribution.py \
  diagnose-train-attribution \
  --train-artifact output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

Expected: exactly one attribution path. A sanitized technical failure triggers evidence-gathering without printing its raw message. `MARKET_DATA_INCOMPLETE` is a valid artifact result and must not be repaired by reading later data.

- [ ] **Step 3: Strict-load and summarize only aggregate evidence**

Use `load_five_day_ranking_v3_attribution()` with both expected parent identities. Report coverage counts, actual/fixed-five dual-benchmark results, Rank-1 diagnostics, gross-versus-net drag, status, and frozen safety flags. Do not print nested source rows or any forbidden artifact key.

- [ ] **Step 4: Prove idempotency**

Hash the generated file with SHA-256, rerun the identical command, and require the same path and identical file hash.

- [ ] **Step 5: Prove parent and operational state are unchanged**

Strict-load V1, V2, V3, and research again. Require:

```text
V1 d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3
V2 99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22
V3 6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb
```

Require no generated validation, test, freeze, forward, settlement, notification, holding, memory, order, or trading file; require the Git staging area to remain empty.

- [ ] **Step 6: Report and stop without a generated-artifact commit**

State that the result is train-only and `NO-TRADE`. Do not modify V3 from this one attribution case and do not begin the public-strategy challenger suite inside this task.
