# Limit-Up Gene Watch Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full-market `limit_up_gene_watch` lane that catches strong limit-up-gene consolidation setups, validates them chronologically, and remains shadow-only until a fail-closed promotion artifact approves Top5 integration.

**Architecture:** A pure candidate evaluator consumes the existing `stock_ai.limit_up_logic` result and base liquidity facts. A standalone runner scans MySQL daily bars, applies news-risk vetoes only after technical preselection, and saves an independent strategy bucket. A chronological backtest extends the existing validation artifact with drawdown and profit/loss ratio gates; Top5 loading includes the lane only when the artifact is current and promoted.

**Tech Stack:** Python 3.11, pandas, SQLAlchemy, MySQL 8, pytest, existing limit-up logic and selection validation modules.

## Global Constraints

- Strategy name is exactly `limit_up_gene_watch`.
- Candidate action is exactly `蓄势观察，等待次日确认`; the lane never emits a direct buy action.
- Eligibility requires `gene == STRONG`, a recent limit-up count of at least one, unbroken support, continuation probability at least 45, failure probability at most 40, base liquidity pass, and no material-risk veto.
- Missing sector, auction, or seal data remains missing and is not treated as a negative zero.
- The old 700-session box is not a gate for this lane.
- Point-in-time backtests may use only facts available at the signal close.
- Top5 integration fails closed unless a current promotion artifact passes all configured gates.
- No personal holdings or decisions are used as research fixtures or committed outputs.

---

### Task 1: Implement the pure limit-up-gene watch evaluator

**Files:**
- Create: `stock_ai/limit_up_gene_watch.py`
- Create: `tests/unit/test_limit_up_gene_watch.py`

**Interfaces:**
- Produces `LimitUpGeneWatchPolicy` with defaults `min_amount_wan=5000`, `min_continuation=45`, `max_failure=40`, and `required_gene="STRONG"`.
- Produces `LimitUpGeneCandidate` with code, name, score, action, tags, missing fields, and raw metrics.
- Produces `evaluate_limit_up_gene_candidate(result: LimitUpResult, *, amount_wan: float, base_filter_passed: bool, policy: LimitUpGeneWatchPolicy = DEFAULT_POLICY) -> LimitUpGeneCandidate | None`.

- [ ] **Step 1: Write failing eligibility tests**

```python
def test_strong_gene_consolidation_enters_watch_pool() -> None:
    candidate = evaluate_limit_up_gene_candidate(
        limit_result(gene="STRONG", continuation=60, failure=30, risk=False),
        amount_wan=38_000,
        base_filter_passed=True,
    )
    assert candidate is not None
    assert candidate.action == "蓄势观察，等待次日确认"


@pytest.mark.parametrize("change", [
    {"gene": "MEDIUM"},
    {"continuation": 44},
    {"failure": 41},
    {"risk": True},
])
def test_hard_gate_failure_excludes_candidate(change) -> None:
    assert evaluate_limit_up_gene_candidate(limit_result(**change), amount_wan=38_000, base_filter_passed=True) is None


def test_missing_confirmation_fields_are_disclosed_not_zeroed() -> None:
    candidate = evaluate_limit_up_gene_candidate(limit_result(missing=("auction_strength", "seal_quality")), amount_wan=38_000, base_filter_passed=True)
    assert candidate.missing_fields == ("auction_strength", "seal_quality")
```

- [ ] **Step 2: Run and verify missing module failure**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_gene_watch.py -q`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement the evaluator and deterministic score**

Calculate score as `gene + price_volume + theme_sector + fund_flow`, capped at 100. Preserve existing drivers/suppressors and add no score for missing confirmation fields.

- [ ] **Step 4: Run evaluator tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_gene_watch.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the evaluator task**

```bash
git add stock-ai/stock_ai/limit_up_gene_watch.py stock-ai/tests/unit/test_limit_up_gene_watch.py
git commit -m "feat(stock-ai): evaluate limit-up gene watch candidates"
```

### Task 2: Add the MySQL full-market selection runner

**Files:**
- Create: `scripts/selection/stock_selection_limit_up_gene.py`
- Create: `tests/unit/test_stock_selection_limit_up_gene.py`

**Interfaces:**
- Produces `run_selection(df_all: pd.DataFrame, *, names: Mapping[str, str], risks: Mapping[str, tuple[bool, tuple[str, ...]]]) -> pd.DataFrame`, where each risk tuple is `(material_risk, reasons)`.
- CLI accepts `--trade-date`, `--report-only`, and `--limit`.
- Saves rows through `save_selection_daily_results(trade_date, rows, strategy="limit_up_gene_watch")`.

- [ ] **Step 1: Write a failing point-in-time runner test**

```python
def test_runner_uses_only_bars_through_trade_date() -> None:
    panel = panel_with_future_limit_up_after("2026-08-12")
    rows = run_selection(panel[panel.trade_date <= "2026-08-12"], names=NAMES, risks={})
    assert rows.iloc[0]["数据截止"] == "2026-08-12"
    assert rows.iloc[0]["建议动作"] == "蓄势观察，等待次日确认"
    assert "2026-08-13" not in rows.iloc[0]["原始指标"]
```

Add tests that a risk-vetoed preselection is removed and that output carries `缺失字段`.

- [ ] **Step 2: Run and verify missing runner failure**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_stock_selection_limit_up_gene.py -q`

Expected: FAIL because the runner does not exist.

- [ ] **Step 3: Implement two-stage scanning**

Stage one groups daily bars and runs existing limit-up logic with empty context. Stage two loads news coverage once, evaluates risk only for preselected codes, reruns the final context, and emits rows with `代码`, `名称`, `收盘价`, `涨幅%`, `成交额(万)`, `总分`, `建议动作`, `策略标签`, `涨停基因`, `延续概率`, `失败概率`, `缺失字段`, and `raw_json`.

- [ ] **Step 4: Run runner tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_stock_selection_limit_up_gene.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the runner task**

```bash
git add stock-ai/scripts/selection/stock_selection_limit_up_gene.py stock-ai/tests/unit/test_stock_selection_limit_up_gene.py
git commit -m "feat(stock-ai): add limit-up gene selection lane"
```

### Task 3: Integrate the lane into parallel selection as shadow output

**Files:**
- Modify: `scripts/selection/run_parallel_selection.py`
- Modify: `scripts/tools/selection_results.py`
- Modify: `scripts/selection/daily_selection_report.py`
- Create: `tests/unit/test_parallel_selection_lanes.py`
- Modify: `tests/unit/test_selection_results.py`

**Interfaces:**
- `LANE_ORDER` includes `limit_up_gene_watch`.
- `_STRATEGY_DISPLAY` maps it to `涨停基因蓄势`.
- Default Top5 strategies do not include it until promotion.
- Daily report shows a separate shadow-watch section.

- [ ] **Step 1: Write failing lane and fail-closed Top5 tests**

```python
def test_parallel_runner_contains_limit_up_gene_lane() -> None:
    assert "limit_up_gene_watch" in LANE_ORDER


def test_unpromoted_gene_lane_is_not_in_default_top5(monkeypatch) -> None:
    monkeypatch.delenv("LIMIT_UP_GENE_PROMOTION_ARTIFACT", raising=False)
    assert "limit_up_gene_watch" not in wechat_top5_strategies()
```

- [ ] **Step 2: Run and verify both tests fail before integration**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_parallel_selection_lanes.py tests/unit/test_selection_results.py -q`

Expected: FAIL because the lane/display do not exist.

- [ ] **Step 3: Add the lane runner and shadow report section**

Keep process workers default at four; five lanes may queue. Do not append the new strategy to `DEFAULT_WECHAT_TOP5_STRATEGIES` in this task.

- [ ] **Step 4: Run integration-unit tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_parallel_selection_lanes.py tests/unit/test_selection_results.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the shadow integration task**

```bash
git add stock-ai/scripts/selection/run_parallel_selection.py stock-ai/scripts/tools/selection_results.py stock-ai/scripts/selection/daily_selection_report.py stock-ai/tests/unit/test_parallel_selection_lanes.py stock-ai/tests/unit/test_selection_results.py
git commit -m "feat(stock-ai): run limit-up gene lane in shadow mode"
```

### Task 4: Extend validation metrics with drawdown and profit/loss ratio

**Files:**
- Modify: `stock_ai/selection_validation.py`
- Modify: `tests/unit/test_selection_validation.py`

**Interfaces:**
- `BacktestMetrics` gains backward-compatible defaults `max_drawdown_pct=0.0` and `profit_loss_ratio=0.0`.
- Produces `PromotionCriteria` with lane-specific thresholds.
- `evaluate_promotion(*, baseline: BacktestMetrics, candidate: BacktestMetrics, chronology_valid: bool = True, criteria: PromotionCriteria = DEFAULT_CRITERIA)` remains backward compatible.
- Gene-watch criteria: minimum 100 trades, win-rate improvement at least 5 percentage points, non-negative expectancy, Wilson lower bound at least 0.45, maximum drawdown at most 15%, and profit/loss ratio at least 1.5.

- [ ] **Step 1: Write failing promotion-gate tests**

```python
def test_gene_watch_rejects_excessive_drawdown() -> None:
    candidate = metrics(trades=120, wins=72, expectancy=0.8, max_drawdown=15.1, profit_loss_ratio=1.8)
    decision = evaluate_promotion(baseline=BASELINE, candidate=candidate, criteria=GENE_WATCH_CRITERIA)
    assert "MAX_DRAWDOWN_TOO_HIGH" in decision.reasons


def test_gene_watch_rejects_weak_profit_loss_ratio() -> None:
    candidate = metrics(trades=120, wins=72, expectancy=0.8, max_drawdown=10, profit_loss_ratio=1.49)
    decision = evaluate_promotion(baseline=BASELINE, candidate=candidate, criteria=GENE_WATCH_CRITERIA)
    assert "PROFIT_LOSS_RATIO_TOO_LOW" in decision.reasons
```

- [ ] **Step 2: Run and verify new metric arguments fail**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_selection_validation.py -q`

Expected: FAIL because the metrics/criteria are not supported.

- [ ] **Step 3: Implement backward-compatible criteria**

Preserve current strict-selection behavior by setting its default criteria to the existing gates. Serialize and validate the two new metrics in artifacts; legacy artifacts without them fail closed for the gene lane but continue to fall back safely for old policies.

- [ ] **Step 4: Run validation tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_selection_validation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit validation extensions**

```bash
git add stock-ai/stock_ai/selection_validation.py stock-ai/tests/unit/test_selection_validation.py
git commit -m "feat(stock-ai): add risk gates to selection promotion"
```

### Task 5: Build chronological backtest and promotion artifact

**Files:**
- Create: `scripts/analysis/backtest_limit_up_gene_watch.py`
- Create: `tests/unit/test_backtest_limit_up_gene_watch.py`
- Create at runtime only: `output/validation/limit_up_gene_watch.json`

**Interfaces:**
- CLI flags: `--start`, `--end`, `--hold-days 5`, `--commission-rate 0.0008`, `--slippage-rate 0.001`, and `--artifact`.
- Baseline is the same-date current `combined` candidate stream; candidate is `limit_up_gene_watch`.
- Entry is T+1 open; exit is T+5 close; suspended/missing bars skip the trade and are counted.

- [ ] **Step 1: Write failing no-future-data and cost tests**

```python
def test_signal_evaluation_receives_only_rows_through_signal_date() -> None:
    seen = []
    run_backtest(PANEL, evaluator=lambda bars: seen.append(bars.trade_date.max()) or ())
    assert all(value <= signal_date for value, signal_date in paired_dates(seen))


def test_round_trip_costs_reduce_return() -> None:
    gross = trade_return(10.0, 11.0, commission_rate=0, slippage_rate=0)
    net = trade_return(10.0, 11.0, commission_rate=0.0008, slippage_rate=0.001)
    assert net < gross
```

- [ ] **Step 2: Run and verify missing backtest module failure**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_backtest_limit_up_gene_watch.py -q`

Expected: FAIL on missing module.

- [ ] **Step 3: Implement chronological replay and artifact output**

Use chronological train/validation/test splits from `selection_validation`. Calculate trade count, wins, expectancy, Wilson lower bound, max drawdown, profit/loss ratio, and identity counts. Do not commit the generated artifact until the team deliberately chooses a stable promoted artifact policy; runtime output remains gitignored.

- [ ] **Step 4: Run backtest unit tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_backtest_limit_up_gene_watch.py -q`

Expected: PASS.

- [ ] **Step 5: Run the historical backtest**

Run: `cd stock-ai && .venv/bin/python -m scripts.analysis.backtest_limit_up_gene_watch --start 2023-01-03 --end 2026-08-12 --hold-days 5 --artifact output/validation/limit_up_gene_watch.json`

Expected: artifact records full data bounds, split bounds, costs, metrics, and a promotion decision. If it fails any gate, keep shadow mode and report the reasons; do not tune on the test split.

- [ ] **Step 6: Commit the backtest code and tests**

```bash
git add stock-ai/scripts/analysis/backtest_limit_up_gene_watch.py stock-ai/tests/unit/test_backtest_limit_up_gene_watch.py
git commit -m "feat(stock-ai): backtest limit-up gene watch lane"
```

### Task 6: Add fail-closed promotion loading and Top5 gating

**Files:**
- Modify: `stock_ai/selection_validation.py`
- Modify: `scripts/tools/selection_results.py`
- Modify: `tests/unit/test_selection_validation.py`
- Modify: `tests/unit/test_selection_results.py`

**Interfaces:**
- Produces `load_gene_watch_promotion(path, *, expected_data_end: date) -> bool`.
- `wechat_top5_strategies()` appends `limit_up_gene_watch` only when the configured artifact is promoted and its data end equals the latest completed selection date.

- [ ] **Step 1: Write failing stale/missing/promoted artifact tests**

```python
def test_missing_gene_artifact_fails_closed(tmp_path) -> None:
    assert load_gene_watch_promotion(tmp_path / "missing.json", expected_data_end=END) is False


def test_stale_gene_artifact_fails_closed(tmp_path) -> None:
    path = write_gene_artifact(tmp_path, promoted=True, data_end="2026-08-11")
    assert load_gene_watch_promotion(path, expected_data_end=date(2026, 8, 12)) is False


def test_current_promoted_artifact_enables_top5(tmp_path, monkeypatch) -> None:
    path = write_gene_artifact(tmp_path, promoted=True, data_end="2026-08-12")
    monkeypatch.setenv("LIMIT_UP_GENE_PROMOTION_ARTIFACT", str(path))
    assert "limit_up_gene_watch" in wechat_top5_strategies()
```

- [ ] **Step 2: Run and verify missing loader/gating failures**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_selection_validation.py tests/unit/test_selection_results.py -q`

Expected: FAIL on missing loader or disabled integration.

- [ ] **Step 3: Implement current-artifact validation**

Validate schema version, rule version, timestamps, complete chronological bounds, cost fields, all promotion metrics, and empty reasons. Any parsing or freshness error returns `False` without raising into daily selection.

- [ ] **Step 4: Run promotion tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_selection_validation.py tests/unit/test_selection_results.py -q`

Expected: PASS.

- [ ] **Step 5: Commit promotion gating**

```bash
git add stock-ai/stock_ai/selection_validation.py stock-ai/scripts/tools/selection_results.py stock-ai/tests/unit/test_selection_validation.py stock-ai/tests/unit/test_selection_results.py
git commit -m "feat(stock-ai): gate gene watch promotion fail closed"
```

### Task 7: Verify shadow production run and document promotion status

**Files:**
- Modify: `docs/CAPABILITIES.md`
- Modify: `docs/SCHEDULING.md`

**Interfaces:**
- Documents strategy bucket, missing-field semantics, backtest command, artifact freshness, and shadow/promoted status.

- [ ] **Step 1: Run the complete focused suite**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_features.py tests/unit/test_limit_up_scoring.py tests/unit/test_limit_up_replay.py tests/unit/test_limit_up_gene_watch.py tests/unit/test_stock_selection_limit_up_gene.py tests/unit/test_parallel_selection_lanes.py tests/unit/test_backtest_limit_up_gene_watch.py tests/unit/test_selection_validation.py tests/unit/test_selection_results.py -q`

Expected: all tests PASS.

- [ ] **Step 2: Run the new lane for the latest complete trade date**

Run: `cd stock-ai && .venv/bin/python -m scripts.selection.stock_selection_limit_up_gene --trade-date 2026-08-12`

Expected: rows save under `strategy=limit_up_gene_watch`; the known regression fixture shape appears in the independent watch output, while Top5 remains unchanged unless a valid promotion artifact exists.

- [ ] **Step 3: Verify database isolation**

Run a read-only query counting rows by strategy for the latest date.

Expected: `limit_up_gene_watch` is separate; existing `combined`, `ma5`, `five_factor`, and `bottom_breakout` row counts are unchanged.

- [ ] **Step 4: Document actual promotion status**

If the artifact failed any gate, document `shadow` and the exact machine reasons. If it passed, document the artifact path, data end, and promotion timestamp without including individual trades or personal holdings.

- [ ] **Step 5: Review the diff and commit docs**

Run: `git diff --check && git status --short`

```bash
git add stock-ai/docs/CAPABILITIES.md stock-ai/docs/SCHEDULING.md
git commit -m "docs(stock-ai): document limit-up gene watch lane"
```
