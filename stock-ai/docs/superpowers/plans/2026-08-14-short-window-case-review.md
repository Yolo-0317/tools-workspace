# Short-Window Buy-Point Case Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated, point-in-time two-week case review that explains strict candidates, one-soft-gate near misses, subsequent outcomes, and missed buyable winners without changing or promoting production rules.

**Architecture:** Add a pure `case_review` module beside the existing buy-point replay code. It will trace the existing hard-gate funnel, admit exactly one explicitly allowed soft-gate failure into a diagnostic near-miss pool, evaluate outcomes and buyable-winner recall from bounded future bars, and render immutable JSON/Markdown artifacts. A thin manual CLI will load MySQL/reference inputs and call the pure module; production selection, holdings, decision memory, and validation artifacts remain read-only.

**Tech Stack:** Python 3.11, dataclasses, Decimal, SQLAlchemy, pytest, existing `stock_ai.buy_point_selection` gates/patterns/planning/replay helpers.

## Global Constraints

- Signal window is 2026-08-03 through 2026-08-07; outcome data starts 2026-08-10.
- Signal generation may use only bars and facts available on each signal date.
- Entry may trigger only during the next two actual trading sessions; outcome horizon is at most five actual sessions after trigger.
- Success requires MFE at least 5% and MAE no more than 3%; `PENDING` is excluded from success and failure denominators.
- Only sector strength/resonance, 2R room, or risk-distance range may be the single near-miss gate.
- ST/risk veto, suspension, stale/missing price data, liquidity, existing holdings, and two failed gates are never relaxed.
- At most ten deterministic near misses are retained per signal date.
- This is `CASE_ANALYSIS_ONLY`; it cannot emit formal recommendations, live shares, position changes, or rule promotion.
- Outputs are immutable revisions named with signal window, outcome cutoff, rule version, and policy hash.

---

### Task 1: Gate Trace and One-Soft-Gate Classification

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/case_review.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/__init__.py`
- Create: `stock-ai/tests/unit/test_buy_point_case_review.py`

**Interfaces:**
- Produces: `GateTrace`, `CaseCandidate`, `NearMissDecision`, `classify_near_miss(trace, setup_quality, average_amount5_qian) -> NearMissDecision`.
- Allowed soft reasons are `SECTOR_RELATIVE_STRENGTH_WEAK`, `SECTOR_BREADTH_WEAK`, `SECTOR_NOT_RESONATING`, `SECTOR_AMOUNT_WEAK`, `INSUFFICIENT_TWO_R_SPACE`, and `RISK_DISTANCE_OUT_OF_RANGE`.

- [ ] **Step 1: Write failing tests for exactly one soft failure and hard-veto rejection**

```python
def test_exactly_one_allowed_soft_gate_enters_near_miss() -> None:
    trace = GateTrace("600001", SIGNAL, ("SECTOR_BREADTH_WEAK",), (), {})
    decision = classify_near_miss(trace, Decimal("0.8"), Decimal("200000"))
    assert decision.admitted
    assert decision.soft_reason == "SECTOR_BREADTH_WEAK"

def test_hard_or_two_soft_failures_never_enter_near_miss() -> None:
    hard = GateTrace("600001", SIGNAL, ("LIQUIDITY_TOO_LOW",), (), {})
    two = GateTrace(
        "600002", SIGNAL,
        ("SECTOR_BREADTH_WEAK", "INSUFFICIENT_TWO_R_SPACE"), (), {},
    )
    assert not classify_near_miss(hard, Decimal("1"), Decimal("200000")).admitted
    assert not classify_near_miss(two, Decimal("1"), Decimal("200000")).admitted
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_review.py -q`

Expected: collection fails because `case_review` does not exist.

- [ ] **Step 3: Implement immutable trace models and classifier**

```python
ALLOWED_SOFT_REASONS = frozenset({...})
HARD_REASONS = frozenset({...})

def classify_near_miss(trace, setup_quality, average_amount5_qian):
    unique = tuple(dict.fromkeys(trace.failed_reasons))
    admitted = len(unique) == 1 and unique[0] in ALLOWED_SOFT_REASONS
    return NearMissDecision(admitted, unique[0] if admitted else None, ...)
```

The returned ranking key is deterministic: normalized boundary deviation ascending, setup quality descending, five-day amount descending, code ascending.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_review.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add stock-ai/stock_ai/buy_point_selection/case_review.py stock-ai/stock_ai/buy_point_selection/__init__.py stock-ai/tests/unit/test_buy_point_case_review.py
git commit -m "feat(stock-ai): classify buy-point near misses"
```

### Task 2: Point-in-Time Signal Replay With First-Rejection Attribution

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_review.py`
- Modify: `stock-ai/tests/unit/test_buy_point_case_review.py`

**Interfaces:**
- Consumes: existing `base_gate`, `detect_setups`, `anti_chase_gate`, `sector_gate`, `build_price_plan`.
- Produces: `replay_case_signals(...) -> CaseSignalReplay`, containing per-date completeness, every code's ordered `GateTrace`, strict-shadow plans, and capped near misses.

- [ ] **Step 1: Write a failing chronology and attribution test**

```python
def test_signal_replay_never_reads_future_bars_and_records_first_rejection() -> None:
    bars = {"600001": history_through_signal + (future_spike_bar,)}
    replay = replay_case_signals(
        signal_dates=(SIGNAL,), trading_dates=TRADING_DATES,
        bars_by_code=bars, memberships=MEMBERSHIPS,
        risk_flags=(), coverage_by_date=COMPLETE_COVERAGE,
        market_snapshots=ALLOW_MARKET,
    )
    trace = replay.traces[(SIGNAL, "600001")]
    assert trace.analysis_bar_date == SIGNAL
    assert future_spike_bar.trade_date not in trace.consumed_bar_dates
    assert trace.first_rejection == "NO_BUY_POINT_SETUP"
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_review.py::test_signal_replay_never_reads_future_bars_and_records_first_rejection -q`

Expected: FAIL because `replay_case_signals` is undefined.

- [ ] **Step 3: Implement the ordered trace pipeline**

For each signal date, slice each code at `analysis_date` before invoking any gate. Record exactly these ordered stages: completeness, latest bar, base, setup, anti-chase, sector, price plan. Preserve all reasons from the failing stage, but expose the deterministic first reason for missed-winner attribution. Build a diagnostic plan for a single allowed soft failure by bypassing only that stage; never bypass a hard reason.

- [ ] **Step 4: Add and pass tests for incomplete dates, cap/order, and no live side effects**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_review.py -q`

Expected: PASS, including assertions that incomplete dates are not counted as legitimate zero-candidate days and every candidate has zero executable shares.

- [ ] **Step 5: Commit**

```bash
git add stock-ai/stock_ai/buy_point_selection/case_review.py stock-ai/tests/unit/test_buy_point_case_review.py
git commit -m "feat(stock-ai): trace point-in-time case signals"
```

### Task 3: Five-Session Outcomes and Buyable-Winner Recall

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_review.py`
- Modify: `stock-ai/tests/unit/test_buy_point_case_review.py`

**Interfaces:**
- Produces: `evaluate_case_plan(plan, bars, trading_dates, cutoff) -> CaseOutcome`, `find_buyable_winners(...) -> tuple[BuyableWinner, ...]`, and `build_case_review(...) -> CaseReview`.

- [ ] **Step 1: Write failing boundary tests**

```python
@pytest.mark.parametrize(
    ("mfe", "mae", "success"),
    [("0.0499", "-0.01", False), ("0.05", "-0.03", True), ("0.06", "-0.0301", False)],
)
def test_case_success_boundaries(mfe, mae, success):
    outcome = outcome_fixture(mfe=mfe, mae=mae)
    assert classify_case_success(outcome) is success

def test_pending_outcome_is_excluded_from_resolved_denominator() -> None:
    metrics = summarize_outcomes((pending_outcome(), successful_outcome()))
    assert metrics.resolved == 1
    assert metrics.successes == 1
```

- [ ] **Step 2: Run boundary tests and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_review.py -q`

Expected: FAIL because outcome classification is missing.

- [ ] **Step 3: Implement actual-session trigger/outcome slicing**

Use the existing `simulate_plan` behavior for execution ordering and costs. Resolve the two entry sessions and five post-trigger sessions from `trading_dates`, never calendar weekdays. Mark insufficient horizon `PENDING`. Store trigger date/price, close return, fee-adjusted return, MFE, MAE, stop-first, and ambiguity.

- [ ] **Step 4: Write failing buyable-winner tests**

```python
def test_buyable_winner_excludes_one_price_limit_up_and_gap_over_three_percent() -> None:
    winners = find_buyable_winners(...)
    assert {item.code for item in winners} == {"600003"}
```

The fixture includes one normal winner, one one-price limit-up, one 3.01% gap open, one hard-veto code, one illiquid code, and one existing holding.

- [ ] **Step 5: Implement winner detection and signal-date trace join**

Use signal-week final close as the denominator, outcome-week highs for the 5% test, board-aware one-price limit-up detection, and point-in-time holdings/risk facts. Join every missed winner to the first reason from the relevant historical `GateTrace`.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_review.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add stock-ai/stock_ai/buy_point_selection/case_review.py stock-ai/tests/unit/test_buy_point_case_review.py
git commit -m "feat(stock-ai): evaluate short-window case outcomes"
```

### Task 4: Immutable JSON and Markdown Report

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/case_report.py`
- Create: `stock-ai/tests/unit/test_buy_point_case_report.py`

**Interfaces:**
- Consumes: `CaseReview`.
- Produces: `case_identity(review) -> str`, `case_payload(review) -> dict[str, object]`, `render_case_markdown(review) -> str`, and `write_case_revision(review, output_dir) -> tuple[Path, Path]`.

- [ ] **Step 1: Write failing determinism and immutability tests**

```python
def test_case_identity_and_order_are_deterministic(tmp_path) -> None:
    first = case_payload(review_fixture(candidates=(B, A)))
    second = case_payload(review_fixture(candidates=(A, B)))
    assert first == second
    assert first["status"] == "CASE_ANALYSIS_ONLY"

def test_later_cutoff_writes_a_new_revision(tmp_path) -> None:
    early = write_case_revision(review_fixture(cutoff=EARLY), tmp_path)
    late = write_case_revision(review_fixture(cutoff=LATE), tmp_path)
    assert early != late
    assert all(path.exists() for path in (*early, *late))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_report.py -q`

Expected: collection fails because `case_report` does not exist.

- [ ] **Step 3: Implement canonical payload, report, and exclusive-create writes**

Sort dates, codes, reasons, and outcomes explicitly. Hash canonical JSON containing signal dates, cutoff, rule version, and policy hash. Write with exclusive-create mode; if identical files already exist, verify bytes and return them, otherwise refuse overwrite. Markdown must show raw numerators/denominators and state that results cannot promote a rule.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_report.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add stock-ai/stock_ai/buy_point_selection/case_report.py stock-ai/tests/unit/test_buy_point_case_report.py
git commit -m "feat(stock-ai): render immutable case review reports"
```

### Task 5: Manual MySQL Case-Review CLI

**Files:**
- Create: `stock-ai/scripts/analysis/review_buy_point_case.py`
- Create: `stock-ai/tests/unit/test_review_buy_point_case_cli.py`

**Interfaces:**
- Produces CLI: `python -m scripts.analysis.review_buy_point_case --signal-start YYYY-MM-DD --signal-end YYYY-MM-DD --outcome-cutoff YYYY-MM-DD --output-dir output/research/buy_point_cases`.

- [ ] **Step 1: Write failing CLI parsing and fail-closed tests**

```python
def test_cli_rejects_outcome_cutoff_before_signal_end() -> None:
    assert main(["--signal-start", "2026-08-03", "--signal-end", "2026-08-07", "--outcome-cutoff", "2026-08-06"]) == 2

def test_cli_defaults_to_case_analysis_only_and_never_writes_production_state(tmp_path) -> None:
    result = main(valid_args(tmp_path), runtime_factory=lambda _: fake_runtime())
    assert result == 0
    assert fake_runtime().writes == []
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_review_buy_point_case_cli.py -q`

Expected: collection fails because the CLI module does not exist.

- [ ] **Step 3: Implement read-only loader and CLI**

Load bounded daily bars, trading dates, sector memberships, risk flags, and coverage from existing repositories. Reuse historical market snapshot construction. Refuse missing market/daily/sector data; represent missing announcement coverage as `RISK_COVERAGE_INCOMPLETE / NO-TRADE`. Do not import production write repositories.

- [ ] **Step 4: Run CLI tests and relevant regression tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_review_buy_point_case_cli.py tests/unit/test_buy_point_case_review.py tests/unit/test_buy_point_case_report.py tests/unit/test_buy_point_historical_replay.py tests/unit/test_buy_point_historical_replay_runtime.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add stock-ai/scripts/analysis/review_buy_point_case.py stock-ai/tests/unit/test_review_buy_point_case_cli.py
git commit -m "feat(stock-ai): add manual buy-point case review"
```

### Task 6: Run the Approved August Case and Verify Scope

**Files:**
- Runtime only: `stock-ai/output/research/buy_point_cases/*.json`
- Runtime only: `stock-ai/output/research/buy_point_cases/*.md`

**Interfaces:**
- Consumes the completed CLI and existing MySQL/reference data.
- Produces the first auditable `CASE_ANALYSIS_ONLY` revision.

- [ ] **Step 1: Run the full relevant unit suite**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_buy_point_case_review.py tests/unit/test_buy_point_case_report.py tests/unit/test_review_buy_point_case_cli.py tests/unit/test_buy_point_historical_replay.py tests/unit/test_buy_point_historical_replay_runtime.py tests/unit/test_buy_point_gates.py tests/unit/test_buy_point_patterns.py -q`

Expected: PASS with no warnings or errors.

- [ ] **Step 2: Generate the approved case revision**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m scripts.analysis.review_buy_point_case --signal-start 2026-08-03 --signal-end 2026-08-07 --outcome-cutoff 2026-08-14 --output-dir output/research/buy_point_cases`

Expected: exit 0 and paths to one JSON plus one Markdown revision.

- [ ] **Step 3: Inspect the artifacts**

Verify the report states `CASE_ANALYSIS_ONLY`, lists completeness for all five signal dates, includes strict/near-miss/missed-winner sections, keeps pending rows unresolved, and contains no executable share count or production mutation.

- [ ] **Step 4: Run repository status and secret checks**

Run: `git status --short`

Run: `git diff --check`

Run: `rg -n "mysql\+|password|token|持仓" stock-ai/stock_ai/buy_point_selection/case_review.py stock-ai/stock_ai/buy_point_selection/case_report.py stock-ai/scripts/analysis/review_buy_point_case.py`

Expected: output artifacts remain ignored, diffs contain no secrets or personal state, and unrelated dirty files remain untouched.

- [ ] **Step 5: Final implementation commit**

```bash
git add stock-ai/stock_ai/buy_point_selection stock-ai/scripts/analysis/review_buy_point_case.py stock-ai/tests/unit/test_buy_point_case_review.py stock-ai/tests/unit/test_buy_point_case_report.py stock-ai/tests/unit/test_review_buy_point_case_cli.py stock-ai/docs/superpowers/plans/2026-08-14-short-window-case-review.md
git commit -m "feat(stock-ai): complete short-window buy-point case review"
```
