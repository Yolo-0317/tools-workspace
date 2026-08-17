# Five-Day Ranking V3 Aggregate Cost-Drag Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every V3 actual-holding aggregate satisfy the exact canonical identity `mean_after_cost_drag == mean_gross_return - mean_return`, including recurring-decimal inputs, then complete the one-off real train attribution.

**Architecture:** Keep row-level attribution and strict report validation unchanged. Canonicalize the aggregate inside `summarize_attributed_returns()` by deriving the cost drag from the two already-aggregated means under the existing `Decimal` context; prove the behavior at both the pure-domain and strict artifact round-trip boundaries before rerunning real data.

**Tech Stack:** Python 3.11, `Decimal`, pytest, Ruff, immutable canonical JSON, SQLAlchemy read-only MySQL loader, existing BaoStock/Eastmoney benchmark loader.

## Global Constraints

- Keep the diagnostic train-only and `NO-TRADE`.
- Do not change row-level gross return, net return, benchmark return, excess return, ranking, qualification, promotion, validation, or execution behavior.
- Do not add tolerance-based arithmetic validation or global decimal quantization.
- Do not read validation or test outcomes.
- Do not invoke freeze, forward, settlement, notification, holding, memory, order, or trading flows.
- Do not store observation rows, stock codes, positions, credentials, or raw provider responses in the attribution artifact.
- Preserve unrelated dirty-worktree changes and never stage generated attribution artifacts.

---

### Task 1: Canonicalize Aggregate Cost Drag Through TDD

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py:412-422`
- Test: `tests/unit/test_five_day_ranking_v3_attribution.py:503-517`
- Test: `tests/unit/test_five_day_ranking_v3_attribution_report.py:1-250`

**Interfaces:**
- Consumes: `summarize_attributed_returns(rows, eligible_rows, excluded_missing_coverage, gross_returns) -> AttributionMetrics`, `write_five_day_ranking_v3_attribution()`, and `load_five_day_ranking_v3_attribution()`.
- Produces: an `AttributionMetrics` whose aggregate cost drag is exactly the difference of its aggregate gross and net returns and a canonical artifact accepted by the unchanged strict validator.

- [ ] **Step 1: Add a failing pure aggregate regression**

Add this test next to `test_attribution_summary_reports_gross_return_and_after_cost_drag`:

```python
def test_attribution_summary_derives_exact_recurring_decimal_cost_drag() -> None:
    raw_returns = (
        Decimal("0.0135792468135792468135792468"),
        Decimal("-0.0246801357924680135792468013"),
        Decimal("0.0379135792468013579246801357"),
    )
    gross_returns = (
        Decimal("0.0148138147037027036025915924"),
        Decimal("-0.0234455679023445567902344557"),
        Decimal("0.0391481471369248147136924813"),
    )
    value = summarize_attributed_returns(
        tuple(_attributed(str(raw), "0", "0") for raw in raw_returns),
        eligible_rows=3,
        excluded_missing_coverage=0,
        gross_returns=gross_returns,
    )

    assert value.mean_return is not None
    assert value.mean_gross_return is not None
    assert value.mean_after_cost_drag == (
        value.mean_gross_return - value.mean_return
    )
```

- [ ] **Step 2: Add a failing strict round-trip regression**

In `test_five_day_ranking_v3_attribution_report.py`, import `replace` from `dataclasses` and import `AttributedReturn` plus `summarize_attributed_returns`. Add a helper that constructs three zero-benchmark rows from the same recurring decimals:

```python
def _recurring_cost_drag_metrics() -> AttributionMetrics:
    raw_returns = (
        Decimal("0.0135792468135792468135792468"),
        Decimal("-0.0246801357924680135792468013"),
        Decimal("0.0379135792468013579246801357"),
    )
    gross_returns = (
        Decimal("0.0148138147037027036025915924"),
        Decimal("-0.0234455679023445567902344557"),
        Decimal("0.0391481471369248147136924813"),
    )
    rows = tuple(
        AttributedReturn(
            raw_return=raw,
            matched_index_return=Decimal("0"),
            market_median_return=Decimal("0"),
            index_excess=raw,
            market_median_excess=raw,
            market_members=1000,
        )
        for raw in raw_returns
    )
    return summarize_attributed_returns(
        rows,
        eligible_rows=3,
        excluded_missing_coverage=0,
        gross_returns=gross_returns,
    )
```

Add a test that replaces every variant's actual aggregate and `TIME_EXIT_GAIN` status aggregate with that result, updates each actual funnel count to three, updates coverage to 288 attempted/completed intervals, writes the artifact, and strict-loads it:

```python
def test_recurring_decimal_cost_drag_survives_strict_round_trip(
    tmp_path: Path,
) -> None:
    base = _review()
    metrics = _recurring_cost_drag_metrics()
    empty = _empty_metrics()
    variants = tuple(
        replace(
            variant,
            actual=metrics,
            actual_by_status={
                "STOPPED": empty,
                "TIME_EXIT_GAIN": metrics,
                "TIME_EXIT_FLAT": empty,
                "TIME_EXIT_LOSS": empty,
            },
            funnel_counts={
                **variant.funnel_counts,
                "ACTUAL_ATTRIBUTION_ELIGIBLE": 3,
                "ACTUAL_ATTRIBUTION_COMPLETED": 3,
            },
        )
        for variant in base.variants
    )
    review = replace(
        base,
        coverage=replace(
            base.coverage,
            attempted_intervals=288,
            completed_intervals=288,
        ),
        variants=variants,
    )

    path = write_five_day_ranking_v3_attribution(review, tmp_path)
    artifact = load_five_day_ranking_v3_attribution(
        path,
        expected_parent_train_identity="a" * 64,
        expected_parent_research_identity="b" * 64,
    )
    actual = artifact.payload["variants"][0]["actual"]

    assert Decimal(actual["mean_after_cost_drag"]) == (
        Decimal(actual["mean_gross_return"])
        - Decimal(actual["mean_return"])
    )
```

- [ ] **Step 3: Run both named tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py::test_attribution_summary_derives_exact_recurring_decimal_cost_drag \
  tests/unit/test_five_day_ranking_v3_attribution_report.py::test_recurring_decimal_cost_drag_survives_strict_round_trip -q
```

Expected: the pure assertion fails because the two values differ in the final Decimal digit, and the report test fails because the unchanged strict validator rejects the same mismatch.

- [ ] **Step 4: Implement the minimal canonical aggregate calculation**

Replace only the independent per-row drag average inside `summarize_attributed_returns()`:

```python
if gross_returns is not None:
    gross_values = tuple(gross_returns)
    mean_gross_return = _mean(gross_values)
    mean_after_cost_drag = mean_gross_return - mean_return
```

Do not modify `_metric_values()` or any report validation rule.

- [ ] **Step 5: Run the named tests and attribution suites**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py::test_attribution_summary_derives_exact_recurring_decimal_cost_drag \
  tests/unit/test_five_day_ranking_v3_attribution_report.py::test_recurring_decimal_cost_drag_survives_strict_round_trip -q
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py \
  tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py -q
```

Expected: zero failures; the strict validator remains unchanged.

- [ ] **Step 6: Run static checks and commit only the root-cause fix**

```bash
ruff check \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
.venv/bin/python -m compileall -q \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
git diff --check -- \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
git add \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
git diff --cached --check
git commit -m "fix(stock-ai): canonicalize aggregate cost drag"
```

---

### Task 2: Complete the Real Train Attribution and Stop

**Files:**
- Read: `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
- Read: `output/research/buy_point_five_day_returns/ranking-train-d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3.json`
- Read: `output/research/buy_point_five_day_returns/ranking-v2-train-99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22.json`
- Read: `output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json`
- Generate but never stage: `output/research/buy_point_five_day_returns/ranking-v3-train-attribution-<identity>.json`

**Interfaces:**
- Consumes: the fixed pure aggregate calculation, immutable canonical parent artifacts, configured read-only `MYSQL_URL`, and existing benchmark providers.
- Produces: one strict aggregate-only train attribution artifact, an idempotency proof, unchanged parent identities, and a descriptive `NO-TRADE` summary.

- [ ] **Step 1: Run the complete relevant regression suite**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_profiles.py \
  tests/unit/test_five_day_return_execution.py \
  tests/unit/test_five_day_return_validation.py \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py \
  tests/unit/test_five_day_ranking_research.py \
  tests/unit/test_five_day_ranking_report.py \
  tests/unit/test_five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2_report.py \
  tests/unit/test_five_day_ranking_v3_evidence.py \
  tests/unit/test_five_day_ranking_v3_features.py \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3_report.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py \
  tests/unit/test_analyze_five_day_ranking_cli.py \
  tests/unit/test_analyze_five_day_ranking_v2_cli.py \
  tests/unit/test_analyze_five_day_ranking_v3_cli.py \
  tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py \
  tests/unit/test_research_five_day_return_shadow_cli.py -q
```

Expected: zero failures before real data access.

- [ ] **Step 2: Run the manual attribution command once**

```bash
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking_v3_attribution.py \
  diagnose-train-attribution \
  --train-artifact output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

Expected: exactly one attribution path. A sanitized technical failure triggers a new evidence-gathering cycle without printing credentials or a raw provider exception. `MARKET_DATA_INCOMPLETE` is a valid artifact result and must not be repaired with later-period data.

- [ ] **Step 3: Strict-load and summarize aggregate evidence only**

Call `load_five_day_ranking_v3_attribution()` with the expected V3 train and parent research identities. Report status, coverage, actual-holding and fixed-five dual-benchmark aggregates, Rank-1 paired diagnostics, gross-versus-net drag, and frozen safety flags. Do not print stock codes, nested source rows, credentials, or forbidden artifact keys.

- [ ] **Step 4: Prove deterministic idempotency**

Calculate the generated file's SHA-256 hash, rerun the identical CLI command, and require the same file path and identical hash.

- [ ] **Step 5: Prove immutable parents and operational isolation**

Strict-load the parent research artifact and all train generations again. Require these identities:

```text
Research 2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59
V1 d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3
V2 99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22
V3 6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb
```

Require no generated validation, test, freeze, forward, settlement, notification, holding, memory, order, or trading file. Require the Git staging area to be empty.

- [ ] **Step 6: Report and stop without committing generated data**

State that the artifact is train-only and `NO-TRADE`. Do not alter V3 from this attribution case and do not begin the public-strategy challenger suite inside this plan.
