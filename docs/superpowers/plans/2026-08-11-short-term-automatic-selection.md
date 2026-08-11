# Short-Term Automatic Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manually triggered A-share short-term selection pipeline that scores breakout and strong-trend pullback setups, freezes auditable next-session plans, and returns a chat-ready Top 5 report.

**Architecture:** `stock-ai` remains the discovery and mechanical-scoring owner; `a-share-short-term-trading` owns versioned candidates, plan construction, market/portfolio gates, persistence, and next-session diagnosis. A thin CLI composes both projects, runs the existing four lanes, validates the completed-bar date, refreshes evidence only for finalists, then saves and renders an idempotent result.

**Tech Stack:** Python 3.11, pandas, Pydantic v2, SQLAlchemy 2, PyMySQL, pytest, MySQL 8, existing OpenCLI capture adapters.

## Global Constraints

- Trigger only from manual chat/CLI; do not add cron, scheduled refresh, dashboard, push, or auto-order behavior.
- Select only Shanghai/Shenzhen main-board A shares; exclude ST/delisting, Beijing, STAR, ChiNext, listings younger than 60 trading days, suspended/illiquid names, moves above 7%, and current holdings.
- Support `BREAKOUT` and `PULLBACK`; rank separately, merge at most 3+2, fill unused quota from the other type, and cap one industry at two names.
- Use only completed daily bars: previous completed session pre-market/intraday, same-day completed bars post-market, and latest completed session on holidays.
- Missing MySQL, calendar, or completed daily bars fails closed; missing chip/account/holding evidence may produce observation output but never an approved executable plan.
- `LIMITED` halves ticket and loss budgets and returns at most two executable names; `FREEZE` creates no new-risk authorization and forces maximum shares to zero.
- Existing v1.1 contracts and records remain readable; migrations are additive and idempotent.
- Do not commit `.env`, credentials, broker holdings, generated personal data, or unrelated dirty-worktree files.
- Implement every behavior test-first and commit only the files named by that task.

---

## File Structure

### New files

- `stock-ai/stock_ai/short_term_selection.py`: pure bar normalization, hard gates, shape classification, scoring, de-duplication, and 3+2 allocation.
- `stock-ai/tests/unit/test_short_term_selection.py`: selector unit and no-lookahead tests.
- `a-share-short-term-trading/short_term_trading/selection_service.py`: candidate-to-plan orchestration, deterministic IDs, failure isolation, and report rendering.
- `a-share-short-term-trading/tests/test_selection_service.py`: orchestration and renderer tests using in-memory fakes.
- `a-share-short-term-trading/scripts/select_short_term_candidates.py`: manual composition CLI.
- `a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py`: CLI data-date and failure-close tests.
- `a-share-short-term-trading/sql/005_short_term_automatic_selection.sql`: additive v1.2 candidate/plan fields and idempotency indexes.

### Modified files

- `stock-ai/stock_ai/market_codes.py`: exact Shanghai/Shenzhen main-board predicate.
- `stock-ai/stock_ai/short_term_trade.py`: compatibility DataFrame wrapper over the new pure selector.
- `stock-ai/scripts/tools/selection_results.py`: recognize and merge `bottom_breakout` as an explicit source.
- `stock-ai/scripts/selection/short_term_trade_candidates.py`: delegate to the new manual CLI instead of maintaining a second rule set.
- `stock-ai/scripts/analysis/backtest_short_term_trade.py`: run both setup types with the production selector and emit separate metrics.
- `stock-ai/tests/unit/test_market_codes.py`: main-board boundary tests.
- `stock-ai/tests/unit/test_short_term_trade.py`: compatibility-wrapper assertions for both shapes.
- `a-share-short-term-trading/short_term_trading/contracts/market.py`: add backward-compatible `CandidateV2`.
- `a-share-short-term-trading/short_term_trading/contracts/decisions.py`: add `TradePlanV2` and stronger price invariants.
- `a-share-short-term-trading/short_term_trading/contracts/__init__.py`: export v2 contracts.
- `a-share-short-term-trading/short_term_trading/diagnosis.py`: shape-aware plan prices and nullable unapproved sizing.
- `a-share-short-term-trading/short_term_trading/repositories/planning.py`: v2 upsert and latest-valid-plan queries.
- `a-share-short-term-trading/short_term_trading/diagnosis_runtime.py`: load the latest persisted plan when no plan is supplied.
- `a-share-short-term-trading/scripts/diagnose_stock.py`: inject `PlanningRepository`; keep `--plan-json` as an explicit override.
- `a-share-short-term-trading/tests/test_contract_market.py`: v2 candidate validation.
- `a-share-short-term-trading/tests/test_contract_decisions.py`: v2 plan validation.
- `a-share-short-term-trading/tests/test_diagnosis.py`: breakout/pullback price and sizing tests.
- `a-share-short-term-trading/tests/test_repositories.py`: SQL shape and latest-plan unit tests.
- `a-share-short-term-trading/tests/test_diagnose_stock_cli.py`: persisted-plan fallback tests.
- `a-share-short-term-trading/tests/test_migration_files.py`: migration and credential-safety assertions.
- `a-share-short-term-trading/tests/integration/test_mysql_migrations.py`: v1.2 column/index verification.
- `a-share-short-term-trading/tests/integration/test_mysql_repositories.py`: v2 idempotent round trip.
- `a-share-short-term-trading/README.md`: manual trigger, output semantics, and safe-failure documentation.

---

### Task 1: Main-Board Predicate and Pure Dual-Shape Selector

**Files:**
- Create: `stock-ai/stock_ai/short_term_selection.py`
- Modify: `stock-ai/stock_ai/market_codes.py`
- Test: `stock-ai/tests/unit/test_market_codes.py`
- Test: `stock-ai/tests/unit/test_short_term_selection.py`

**Interfaces:**
- Consumes: merged selection rows with `代码`, `名称`, `所属行业`, `策略来源`, and 60–120 completed `stock_daily` rows per code.
- Produces: `SelectionBar`, `CandidateSignal`, `RejectedSignal`, `SelectionResult`, the public selector documented below, and `is_sh_sz_main_board_code(code: str) -> bool`.

- [ ] **Step 1: Write failing main-board and selector tests**

```python
def test_main_board_code_boundaries() -> None:
    assert is_sh_sz_main_board_code("600000")
    assert is_sh_sz_main_board_code("605999")
    assert is_sh_sz_main_board_code("000001")
    assert is_sh_sz_main_board_code("003999")
    for code in ("300001", "301001", "688001", "689001", "830001", "920001", "200001", "900901"):
        assert not is_sh_sz_main_board_code(code)


def test_selector_detects_breakout_without_using_analysis_day_in_prior_high() -> None:
    result = select_short_term_candidates(
        analysis_date=date(2026, 8, 10),
        rows=[selection_row("600001", sources=("combined", "bottom_breakout"))],
        bars_by_code={"600001": breakout_bars(last_close=12.10, prior_high=12.00)},
        holding_codes=set(),
        st_codes=set(),
    )
    assert [(item.code, item.candidate_type) for item in result.candidates] == [("600001", "BREAKOUT")]
    assert result.candidates[0].setup_score >= 70


def test_selector_detects_a_shrinking_volume_pullback() -> None:
    result = select_short_term_candidates(
        analysis_date=date(2026, 8, 10),
        rows=[selection_row("000001", sources=("ma5", "five_factor"))],
        bars_by_code={"000001": pullback_bars()},
        holding_codes=set(),
        st_codes=set(),
    )
    assert result.candidates[0].candidate_type == "PULLBACK"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_market_codes.py stock-ai/tests/unit/test_short_term_selection.py
```

Expected: FAIL because `is_sh_sz_main_board_code` and `short_term_selection` do not exist.

- [ ] **Step 3: Implement exact normalized inputs and hard gates**

```python
CandidateType = Literal["BREAKOUT", "PULLBACK"]

@dataclass(frozen=True)
class SelectionBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    pct_chg: float
    amount_qian: float

@dataclass(frozen=True)
class CandidateSignal:
    code: str
    name: str
    sector: str
    candidate_type: CandidateType
    setup_score: float
    liquidity_score: float
    trend_score: float
    catalyst_score: float
    source_strategies: tuple[str, ...]
    reasons: tuple[str, ...]
    metrics: dict[str, float]

@dataclass(frozen=True)
class RejectedSignal:
    code: str
    reason: str

@dataclass(frozen=True)
class SelectionResult:
    analysis_date: date
    candidates: tuple[CandidateSignal, ...]
    rejected: tuple[RejectedSignal, ...]

def select_short_term_candidates(
    *,
    analysis_date: date,
    rows: Sequence[Mapping[str, object]],
    bars_by_code: Mapping[str, Sequence[Mapping[str, object] | SelectionBar]],
    holding_codes: set[str],
    st_codes: set[str],
    limit: int = 5,
    max_per_sector: int = 2,
) -> SelectionResult:
    normalized = _normalize_inputs(analysis_date, rows, bars_by_code)
    evaluated = _evaluate_all(normalized, holding_codes, st_codes)
    return _build_result(analysis_date, evaluated, limit, max_per_sector)
```

Implement the three private functions shown above in the same module: `_normalize_inputs` converts mappings into ordered `SelectionBar` tuples and rejects duplicate dates; `_evaluate_all` returns either one or two scored shapes plus structured rejection reasons for each code; `_build_result` de-duplicates and calls the allocator introduced in Task 2. Implement `is_sh_sz_main_board_code` with exact prefixes `600/601/603/605` and `000/001/002/003`. Normalize MySQL `amount` as Tushare thousands of yuan; the 1亿元 five-day threshold is `100_000` thousand yuan. Reject fewer than 60 bars, last bar date mismatch, incomplete OHLC/amount, holdings, names containing `ST`, `*ST`, or `退`, explicit ST codes, non-main-board codes, suspended bars (`amount_qian <= 0`), five-day average below `100_000`, and analysis-day gains above 7%.

- [ ] **Step 4: Implement shape conditions and deterministic scoring**

Use prior windows that exclude the analysis bar for `prior_high20` and average amount. Award breakout points as: trend 20 alignment + 10 rising MA20 + 10 close 2–12% above MA20; quality 15 valid new high + up to 10 close-location + 5 gap at most 3%; liquidity 10 five-day average at least 2亿元 (otherwise 5) + 10 for amount ratio 1.2–2.0 (5 for 2.0–3.0); consensus 5 for two sources and 10 for at least three. Award pullback points as: trend 20 alignment + 10 rising MA20 + 10 for 10-day return 5–25%; quality 10 close inside the MA5/MA10 support band + 10 upper-half/recovery close + 10 for 2–6% drawdown (5 for 6–10%); liquidity 10 five-day average at least 2亿元 (otherwise 5) + 10 for amount ratio at most 0.9 (5 for 0.9–1.2); the same consensus points. Reject a pullback when either of the last two closes is below its MA10 while that day's amount exceeds the preceding five-day average. Keep only scores at least 70. Store a deterministic technical `risk_reward_hint = (prior_high20 - close) / (close - technical_support)` when the denominator is positive, otherwise zero; this is only a tie-breaker and never replaces the final chip-aware plan ratio.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_market_codes.py stock-ai/tests/unit/test_short_term_selection.py
git add stock-ai/stock_ai/market_codes.py stock-ai/stock_ai/short_term_selection.py stock-ai/tests/unit/test_market_codes.py stock-ai/tests/unit/test_short_term_selection.py
git commit -m "feat(stock-ai): add dual-shape short-term selector"
```

Expected: focused tests PASS.

---

### Task 2: De-duplication, 3+2 Allocation, and Compatibility Wrapper

**Files:**
- Modify: `stock-ai/stock_ai/short_term_selection.py`
- Modify: `stock-ai/stock_ai/short_term_trade.py`
- Modify: `stock-ai/scripts/tools/selection_results.py`
- Test: `stock-ai/tests/unit/test_short_term_selection.py`
- Test: `stock-ai/tests/unit/test_short_term_trade.py`

**Interfaces:**
- Consumes: `CandidateSignal` values from Task 1.
- Produces: `allocate_candidates(candidates, limit=5, breakout_quota=3, pullback_quota=2, max_per_sector=2) -> tuple[CandidateSignal, ...]` and a backward-compatible bars-aware `build_trade_candidates` DataFrame API.

- [ ] **Step 1: Write failing allocation and wrapper tests**

```python
def test_allocator_keeps_three_breakouts_two_pullbacks_and_two_per_sector() -> None:
    selected = allocate_candidates(candidate_fixtures(), limit=5)
    assert sum(item.candidate_type == "BREAKOUT" for item in selected) <= 3
    assert sum(item.candidate_type == "PULLBACK" for item in selected) <= 2
    assert Counter(item.sector for item in selected).most_common(1)[0][1] <= 2


def test_allocator_fills_an_unused_pullback_slot_with_breakout() -> None:
    selected = allocate_candidates(four_breakouts_and_one_pullback(), limit=5)
    assert len(selected) == 5


def test_dataframe_wrapper_can_return_both_candidate_types() -> None:
    output = build_trade_candidates(rows, bars_by_code=bars, holding_codes=set())
    assert set(output["候选类型"]) == {"突破启动", "强趋势回踩"}
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_short_term_selection.py stock-ai/tests/unit/test_short_term_trade.py
```

Expected: FAIL because allocation and the bars-aware wrapper are absent.

- [ ] **Step 3: Implement allocation and source merging**

Sort each type by `(-setup_score, -risk_reward_hint, -average_amount_qian, code)`, enforce per-sector count before appending, take the initial 3+2 quotas, then fill remaining slots from all unselected candidates with the same ordering and sector cap. If one code has both shapes, retain the higher score; on equal score retain the higher `risk_reward_hint` stored in metrics.

Add `bottom_breakout: "底部突破"` to `_STRATEGY_DISPLAY`. The automatic pipeline must explicitly call:

```python
merge_selection_strategies_df(
    trade_date=analysis_date,
    strategies=("combined", "ma5", "five_factor", "bottom_breakout"),
)
```

- [ ] **Step 4: Replace the old breakthrough-only wrapper**

Keep the public function name, translate `CandidateSignal` fields into existing Chinese report columns, and remove the unconditional `candidate_type != "突破启动"` drop. Require `bars_by_code`; do not silently fall back to label-only classification.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_short_term_selection.py stock-ai/tests/unit/test_short_term_trade.py stock-ai/tests/unit/test_run_parallel_selection.py
git add stock-ai/stock_ai/short_term_selection.py stock-ai/stock_ai/short_term_trade.py stock-ai/scripts/tools/selection_results.py stock-ai/tests/unit/test_short_term_selection.py stock-ai/tests/unit/test_short_term_trade.py
git commit -m "feat(stock-ai): allocate mixed short-term candidates"
```

Expected: focused tests PASS and no legacy wrapper regression.

---

### Task 3: CandidateV2, TradePlanV2, and Additive MySQL Migration

**Files:**
- Modify: `a-share-short-term-trading/short_term_trading/contracts/market.py`
- Modify: `a-share-short-term-trading/short_term_trading/contracts/decisions.py`
- Modify: `a-share-short-term-trading/short_term_trading/contracts/__init__.py`
- Create: `a-share-short-term-trading/sql/005_short_term_automatic_selection.sql`
- Modify: `a-share-short-term-trading/tests/test_contract_market.py`
- Modify: `a-share-short-term-trading/tests/test_contract_decisions.py`
- Modify: `a-share-short-term-trading/tests/test_migration_files.py`

**Interfaces:**
- Consumes: normalized signals from Task 2.
- Produces: `CandidateV2`, `TradePlanV2`, and schema version `1.2` storage columns.

- [ ] **Step 1: Write failing v2 contract tests**

```python
def test_candidate_v2_accepts_pullback_and_keeps_v1_strict() -> None:
    candidate = CandidateV2(candidate_type="PULLBACK", setup_score=Decimal("82.5"), **v2_candidate_fields())
    assert candidate.schema_version == "1.2"
    with pytest.raises(ValidationError):
        CandidateV1(candidate_type="PULLBACK", **v1_candidate_fields())


def test_trade_plan_v2_rejects_invalid_price_order() -> None:
    with pytest.raises(ValidationError, match="price order"):
        TradePlanV2(
            trigger_price=Decimal("10.00"), entry_ceiling=Decimal("10.20"),
            invalidation_price=Decimal("10.10"), first_reduce_price=Decimal("11.00"),
            **v2_plan_fields(),
        )
```

- [ ] **Step 2: Write failing migration assertions and run RED**

```python
def test_short_term_selection_migration_is_additive_and_idempotent() -> None:
    sql = (SQL_DIR / "005_short_term_automatic_selection.sql").read_text().lower()
    for column in ("analysis_date", "setup_score", "rule_version", "source_strategies_json", "executable_status"):
        assert column in sql
    assert "information_schema.columns" in sql
    assert "values ('1.2'" in sql
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_contract_market.py a-share-short-term-trading/tests/test_contract_decisions.py a-share-short-term-trading/tests/test_migration_files.py
```

Expected: FAIL because v2 contracts and migration 005 do not exist.

- [ ] **Step 3: Implement immutable v2 contracts**

```python
class CandidateV2(ContractModel):
    schema_version: Literal["1.2"] = "1.2"
    candidate_id: str
    analysis_date: date
    trading_date: date
    code: str
    name: str
    candidate_type: Literal["BREAKOUT", "PULLBACK"]
    setup_score: Decimal = Field(ge=0, le=100)
    liquidity_score: Decimal = Field(ge=0, le=1)
    trend_score: Decimal = Field(ge=0, le=1)
    catalyst_score: Decimal = Field(ge=0, le=1)
    sector: str
    rule_version: str
    source_strategies: tuple[str, ...] = Field(min_length=1)
    executable_status: Literal["OBSERVE", "EXECUTABLE", "REJECTED"]
    rejected_reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...] = Field(min_length=1)

class TradePlanV2(ContractModel):
    schema_version: Literal["1.2"] = "1.2"
    plan_id: str
    candidate_id: str
    analysis_date: date
    trading_date: date
    code: str
    status: SignalStatus
    trigger_price: Decimal
    entry_ceiling: Decimal
    invalidation_price: Decimal
    first_reduce_price: Decimal
    risk_distance: Decimal
    risk_reward_ratio: Decimal
    atr: Decimal
    chip_trade_date: date
    maximum_shares: int | None
    market_status: MarketStatus
    portfolio_status: Literal["APPROVED", "NOT_APPROVED"]
    valid_until: AwareDatetime
    rule_version: str
    evidence_refs: tuple[str, ...] = Field(min_length=1)
```

Validate UUID IDs, code, UTC timestamps, `invalidation < trigger <= ceiling < first_reduce`, `risk_reward_ratio >= 1.5` for `WAIT_ENTRY`, `maximum_shares == 0` under `FREEZE`, and `maximum_shares is None` whenever portfolio status is not approved except `FREEZE`.

- [ ] **Step 4: Add migration 005 without deleting old data**

Use the existing information-schema guarded pattern for every column and index. Add candidate columns `analysis_date`, `setup_score`, `rule_version`, `source_strategies_json`, and `executable_status`; add plan columns `analysis_date`, `risk_reward_ratio`, `atr`, `chip_trade_date`, `maximum_shares`, `market_status`, and `portfolio_status`. Add nullable columns first and backfill v1.1 rows conservatively. Guardedly drop `uk_candidate_code_date_type`, because it conflicts with rule-version idempotency, then create `uk_candidate_analysis_code_type_rule (analysis_date, code, candidate_type, rule_version)`. Reuse `uk_plan_candidate_rule`, and insert schema-version row `1.2`. The migration changes indexes but deletes no business rows.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_contract_market.py a-share-short-term-trading/tests/test_contract_decisions.py a-share-short-term-trading/tests/test_migration_files.py
git add a-share-short-term-trading/short_term_trading/contracts a-share-short-term-trading/sql/005_short_term_automatic_selection.sql a-share-short-term-trading/tests/test_contract_market.py a-share-short-term-trading/tests/test_contract_decisions.py a-share-short-term-trading/tests/test_migration_files.py
git commit -m "feat(stt): add automatic-selection v2 contracts"
```

Expected: focused tests PASS; dry-run lists migration 005 last.

---

### Task 4: Idempotent Candidate/Plan Persistence and Latest-Plan Lookup

**Files:**
- Modify: `a-share-short-term-trading/short_term_trading/repositories/planning.py`
- Modify: `a-share-short-term-trading/tests/test_repositories.py`
- Modify: `a-share-short-term-trading/tests/integration/test_mysql_repositories.py`
- Modify: `a-share-short-term-trading/tests/integration/test_mysql_migrations.py`

**Interfaces:**
- Consumes: `CandidateV2` and `TradePlanV2` from Task 3.
- Produces: `upsert_candidate(candidate: CandidateV2)`, `upsert_plan(plan: TradePlanV2)`, `get_candidate_v2(candidate_id)`, `get_plan_v2(plan_id)`, and `get_latest_valid_plan(code, at) -> TradePlanV2 | None`.

- [ ] **Step 1: Write failing repository tests**

```python
def test_candidate_v2_upsert_replaces_only_same_deterministic_record() -> None:
    repo.upsert_candidate(candidate_v2(setup_score="80"))
    repo.upsert_candidate(candidate_v2(setup_score="84"))
    assert repo.get_candidate_v2(CANDIDATE_ID).setup_score == Decimal("84")


def test_latest_valid_plan_filters_expired_and_wrong_code() -> None:
    assert repo.get_latest_valid_plan("600000", AT) == active_plan
    assert repo.get_latest_valid_plan("000001", AT) is None
```

- [ ] **Step 2: Run repository tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_repositories.py
```

Expected: FAIL because v2 repository methods do not exist.

- [ ] **Step 3: Implement explicit safe upserts and readers**

Use named column maps, not a table name supplied by callers. Candidate conflict updates may change scores, sources, status, rejection reasons, evidence and `as_of`; they must not update `analysis_date`, `code`, type, rule version, or rows with `source <> 'short-term-auto-selection'`. Plan conflict updates the generated price/risk fields for the same deterministic ID and rule version. Latest plan SQL must require `code`, `data_status='VALID'`, `status='WAIT_ENTRY'`, `valid_until > :at`, and order by `trading_date DESC, as_of DESC`.

- [ ] **Step 4: Add rollback integration coverage**

Extend the existing household-MySQL transaction test to apply v2 records twice, assert one row, assert the updated score, and confirm `get_latest_valid_plan` round-trips all Decimal/date/tuple fields. Keep the test behind `STT_MYSQL_INTEGRATION=1`.

- [ ] **Step 5: Run unit tests, optional integration, and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_repositories.py a-share-short-term-trading/tests/test_migration_files.py
STT_MYSQL_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/integration/test_mysql_migrations.py a-share-short-term-trading/tests/integration/test_mysql_repositories.py
git add a-share-short-term-trading/short_term_trading/repositories/planning.py a-share-short-term-trading/tests/test_repositories.py a-share-short-term-trading/tests/integration/test_mysql_migrations.py a-share-short-term-trading/tests/integration/test_mysql_repositories.py
git commit -m "feat(stt): persist v2 candidates and plans idempotently"
```

Expected: unit tests PASS; integration tests PASS when configured, otherwise remain explicitly skipped in the normal suite.

---

### Task 5: Shape-Aware Price Plans and Fail-Closed Position Sizing

**Files:**
- Modify: `a-share-short-term-trading/short_term_trading/diagnosis.py`
- Modify: `a-share-short-term-trading/short_term_trading/intraday.py`
- Modify: `a-share-short-term-trading/tests/test_diagnosis.py`
- Modify: `a-share-short-term-trading/tests/test_intraday.py`

**Interfaces:**
- Consumes: completed `DailyBar` values, a valid close chip snapshot, `candidate_type`, `MarketStatus`, and optional approved account budgets.
- Produces: an extended `build_eod_trade_plan` accepting keyword arguments `candidate_type`, `market_status`, and `portfolio_approved`, returning legal prices, risk/reward metrics, and `maximum_shares: int | None`.

- [ ] **Step 1: Write failing breakout, pullback, and sizing tests**

```python
def test_breakout_plan_caps_entry_at_one_point_five_percent() -> None:
    plan = build_eod_trade_plan("600000", bars, chip, candidate_type="BREAKOUT", now=NOW)
    assert plan.entry_ceiling <= round(plan.trigger_price * 1.015 + 0.005, 2)
    assert plan.first_reduce_price > plan.entry_ceiling


def test_pullback_plan_uses_reversal_high_and_support_invalidation() -> None:
    plan = build_eod_trade_plan("000001", pullback_bars, chip, candidate_type="PULLBACK", now=NOW)
    assert plan.trigger_price == pullback_bars[-1].high
    assert plan.invalidation_price < min(plan.trigger_price, plan.entry_ceiling)


def test_unapproved_portfolio_never_invents_maximum_shares() -> None:
    plan = build_eod_trade_plan("600000", bars, chip, portfolio_approved=False, now=NOW)
    assert plan.maximum_shares is None


def test_limited_halves_budgets_and_freeze_forces_zero() -> None:
    assert limited.maximum_shares <= allowed.maximum_shares // 2
    assert frozen.maximum_shares == 0
```

- [ ] **Step 2: Run diagnosis tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_diagnosis.py
```

Expected: FAIL because candidate type, market state, and nullable sizing are not supported.

- [ ] **Step 3: Implement exact price rules**

For breakout, compute resistance from prior 20 highs excluding the analysis bar and `cost_90_high`; trigger is resistance plus `0.10 ATR`; entry ceiling is `min(trigger + 0.50 ATR, trigger * 1.015)`. For pullback, trigger is the analysis reversal bar high; entry uses the same cap. Breakout support is the maximum of prior platform low, MA10 and `cost_90_low`; pullback support is the maximum valid support below trigger among analysis-bar low, MA10 and `cost_90_low`. Invalidation is support minus `0.10 ATR`. First reduction is the nearest valid chip/previous-high resistance yielding at least `1.5R`, otherwise exactly `1.5R`. Round upward for entry/targets and downward for invalidation.

- [ ] **Step 4: Implement fail-closed sizing and validation**

Change `TradePlanDraft.maximum_shares` to `int | None`. Return `None` when portfolio approval/account freshness is absent, halve `RiskProfile.per_trade_loss_budget`, `ticket_limit`, and `remaining_exposure` under `LIMITED`, and return zero under `FREEZE`. Reject plans whose price order is illegal, risk distance is outside 1.5–5%, or reward/risk is below 1.5. In `verify_intraday_plan`, treat `plan.maximum_shares is None` as a failed portfolio gate before the final `min(...)`; this preserves fail-closed behavior and avoids nullable arithmetic.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_diagnosis.py a-share-short-term-trading/tests/test_intraday.py a-share-short-term-trading/tests/test_diagnose_stock_cli.py a-share-short-term-trading/tests/test_session_diagnosis.py
git add a-share-short-term-trading/short_term_trading/diagnosis.py a-share-short-term-trading/short_term_trading/intraday.py a-share-short-term-trading/tests/test_diagnosis.py a-share-short-term-trading/tests/test_intraday.py
git commit -m "feat(stt): build shape-aware short-term plans"
```

Expected: focused and existing diagnosis tests PASS.

---

### Task 6: Candidate-to-Plan Selection Service and Chat Renderer

**Files:**
- Create: `a-share-short-term-trading/short_term_trading/selection_service.py`
- Create: `a-share-short-term-trading/tests/test_selection_service.py`

**Interfaces:**
- Consumes: `SelectionResult` from Task 2, daily/evidence/planning repositories, `MarketStateView`, `RiskProfile`, account freshness, and next trade date.
- Produces: `SelectionItem`, `SelectionReport`, `materialize_short_term_selection` with the request/dependency objects below, and `render_selection_report(report) -> str`.

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_materializer_saves_candidate_and_executable_plan() -> None:
    report = materialize_short_term_selection(selection_result, dependencies(), request())
    assert report.items[0].status == "EXECUTABLE"
    assert planning.saved_candidates[0].candidate_type == "BREAKOUT"
    assert planning.saved_plans[0].risk_reward_ratio >= Decimal("1.5")


def test_missing_chip_keeps_observation_but_saves_no_executable_plan() -> None:
    report = materialize_short_term_selection(selection_result, dependencies(chip=None), request())
    assert report.items[0].status == "OBSERVE"
    assert "筹码" in report.items[0].reason
    assert planning.saved_plans == []


def test_one_symbol_failure_does_not_hide_other_valid_symbols() -> None:
    report = materialize_short_term_selection(two_symbols, dependencies(failing_code="600001"), request())
    assert [item.code for item in report.items] == ["000001"]
    assert report.rejection_counts["PLAN_ERROR"] == 1
```

- [ ] **Step 2: Run service tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_selection_service.py
```

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement deterministic materialization**

```python
@dataclass(frozen=True)
class SelectionRequest:
    analysis_date: date
    trading_date: date
    now: datetime
    market_state: MarketStateView
    risk_profile: RiskProfile
    portfolio_approved: bool
    rule_version: str = "short-term-selection-2.0.0"

def deterministic_id(kind: str, analysis_date: date, code: str, candidate_type: str, rule_version: str) -> str:
    return str(uuid5(SELECTION_NAMESPACE, f"{kind}:{analysis_date}:{code}:{candidate_type}:{rule_version}"))
```

For each final signal, first save a deterministic `EvidenceSnapshot` of kind `daily_technical` containing the selector metrics, analysis date, source strategies, and raw reference `mysql:stock_daily:<code>:<analysis_date>`; use that saved snapshot ID in the candidate evidence refs. Refresh chip evidence once only when the latest snapshot is not for `analysis_date`; then reload it and include its snapshot ID in the plan refs. Save a v2 candidate, build the plan, convert valid `WAIT_ENTRY` drafts into `TradePlanV2`, save with deterministic IDs, and mark failures as observations. Under `FREEZE`, persist the candidate and a zero-share non-actionable plan status without a risk approval. Limit executable results to two under `LIMITED` after plan validation.

- [ ] **Step 4: Implement stable text rendering**

Render header date/session/market, numbered candidates grouped by type, score/source/reasons, four prices, max shares or approval reason, rejection counts, and the final line `这是交易计划，不代表已经下单。`. Never print credentials, raw connection URLs, or holdings details.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_selection_service.py
git add a-share-short-term-trading/short_term_trading/selection_service.py a-share-short-term-trading/tests/test_selection_service.py
git commit -m "feat(stt): materialize automatic selection plans"
```

Expected: service and renderer tests PASS.

---

### Task 7: Manual Four-Lane CLI and Safe Data-Date Composition

**Files:**
- Create: `a-share-short-term-trading/scripts/select_short_term_candidates.py`
- Create: `a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py`
- Modify: `stock-ai/scripts/selection/short_term_trade_candidates.py`

**Interfaces:**
- Consumes: existing `run_parallel_selection.main`, `merge_selection_strategies_df`, `load_stock_daily_bars`, portfolio loaders, market-state provider, chip capture, selector, and selection service.
- Produces: manual command `select_short_term_candidates.py [--output text|json] [--at ISO] [--skip-lanes]`.

- [ ] **Step 1: Write failing CLI tests with injected dependencies**

```python
def test_intraday_uses_previous_completed_trade_date() -> None:
    result = main(["--at", "2026-08-10T10:00:00+08:00"], runtime_factory=factory)
    assert result == 0
    assert factory.analysis_date == date(2026, 8, 7)


def test_post_market_stale_daily_data_fails_without_prices() -> None:
    result = run_cli(post_market_runtime(latest_daily=date(2026, 8, 7)))
    assert result.returncode == 2
    assert "当日日线尚未完整入库" in result.stdout
    assert "触发价" not in result.stdout


def test_default_manual_run_executes_all_four_lanes() -> None:
    main([], runtime_factory=factory)
    assert factory.lane_calls == [("combined", "ma5", "five_factor", "bottom_breakout")]
```

- [ ] **Step 2: Run CLI tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py
```

Expected: FAIL because the CLI does not exist.

- [ ] **Step 3: Implement session/date resolution and adapters**

For pre-market, intraday, and midday use `calendar.latest_on_or_before(today - 1 day)`; post-market require `latest_stock_daily_trade_date() == today`; non-trading day use `latest_on_or_before(today)`. Default behavior runs the existing four-lane entry first. `--skip-lanes` only reuses already persisted lanes and is documented as a manual retry/test option. Require all four lane buckets for the resolved date; a missing lane fails closed instead of silently scoring a partial universe.

Load at most 120 completed bars per merged code, convert amount from thousands of yuan without changing stored data, and load ST codes, positions, account and industry information through existing MySQL helpers. Treat the portfolio as approved only when the account snapshot date is at least the resolved analysis date and available cash is present; otherwise pass `portfolio_approved=False`.

- [ ] **Step 4: Compose evidence, market state, persistence, and compatibility entry**

Load `.env` from `stock-ai/.env`, build one SQLAlchemy engine, one evidence repository and one planning repository, call Task 1 selector and Task 6 materializer, and render text or JSON. Catch configuration/data errors at the outer boundary and return exit code 2 with a sanitized Chinese explanation. Change the old stock-ai script to `runpy.run_path` or import/call this CLI so only one production rule path remains.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py stock-ai/tests/unit/test_short_term_trade.py stock-ai/tests/unit/test_run_parallel_selection.py
git add a-share-short-term-trading/scripts/select_short_term_candidates.py a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py stock-ai/scripts/selection/short_term_trade_candidates.py
git commit -m "feat(stt): add manual automatic-selection command"
```

Expected: CLI tests PASS; no scheduler or background process is created.

---

### Task 8: Automatically Reuse the Latest Frozen Plan in Diagnosis

**Files:**
- Modify: `a-share-short-term-trading/short_term_trading/diagnosis_runtime.py`
- Modify: `a-share-short-term-trading/scripts/diagnose_stock.py`
- Modify: `a-share-short-term-trading/tests/test_diagnose_stock_cli.py`

**Interfaces:**
- Consumes: `PlanningRepository.get_latest_valid_plan(code, at)` from Task 4.
- Produces: optional `plan_repository` on `DiagnosisRuntime` and automatic persisted-plan fallback; explicit `--plan-json` retains priority.

- [ ] **Step 1: Write failing fallback tests**

```python
def test_intraday_loads_latest_persisted_plan_when_no_json_override() -> None:
    subject = runtime(frozen_plan=None, plan_repository=FakePlanRepository(plan_v2()))
    build_runtime_diagnosis("600000", subject, now=SHANGHAI_INTRADAY, release_mode=ReleaseMode.SHADOW)
    assert subject.plan_repository.calls == [("600000", SHANGHAI_INTRADAY.astimezone(timezone.utc))]
    assert ("600000", "quote") in subject.evidence_repository.calls


def test_explicit_plan_override_does_not_query_repository() -> None:
    subject = runtime(frozen_plan=plan(), plan_repository=FakePlanRepository(plan_v2()))
    build_runtime_diagnosis("600000", subject, now=SHANGHAI_INTRADAY, release_mode=ReleaseMode.SHADOW)
    assert subject.plan_repository.calls == []
```

- [ ] **Step 2: Run diagnosis runtime tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_diagnose_stock_cli.py
```

Expected: FAIL because runtime cannot load persisted plans.

- [ ] **Step 3: Add plan-provider protocol and conversion**

```python
class PlanProvider(Protocol):
    def get_latest_valid_plan(self, code: str, at: datetime) -> TradePlanV2 | None:
        raise NotImplementedError

def trade_plan_v2_to_draft(plan: TradePlanV2) -> TradePlanDraft:
    return TradePlanDraft(
        code=plan.code, status=plan.status.value, reason="读取已冻结的自动选股计划",
        as_of=plan.as_of.isoformat(), trigger_price=float(plan.trigger_price),
        entry_ceiling=float(plan.entry_ceiling), invalidation_price=float(plan.invalidation_price),
        first_reduce_price=float(plan.first_reduce_price), pullback_low=None, pullback_high=None,
        maximum_shares=plan.maximum_shares, indicators={"atr14": float(plan.atr)},
        evidence_refs={"plan": plan.plan_id},
    )
```

Query only in intraday/midday paths and only when `frozen_plan` is absent. An absent/expired persisted plan keeps the existing fail-closed conclusion and must not start quote refresh.

- [ ] **Step 4: Inject the repository in the CLI**

Construct `PlanningRepository(create_mysql_engine(mysql_url))` in `default_runtime`. Preserve `--plan-json` as an explicit reproduction override and keep the portfolio gate defaulting to unapproved.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_diagnose_stock_cli.py a-share-short-term-trading/tests/test_session_diagnosis.py a-share-short-term-trading/tests/test_intraday.py
git add a-share-short-term-trading/short_term_trading/diagnosis_runtime.py a-share-short-term-trading/scripts/diagnose_stock.py a-share-short-term-trading/tests/test_diagnose_stock_cli.py
git commit -m "feat(stt): load persisted plans during diagnosis"
```

Expected: diagnosis tests PASS and explicit overrides remain deterministic.

---

### Task 9: Production-Rule Backtest, Documentation, and End-to-End Verification

**Files:**
- Modify: `stock-ai/scripts/analysis/backtest_short_term_trade.py`
- Modify: `a-share-short-term-trading/README.md`
- Test: `stock-ai/tests/unit/test_short_term_selection.py`
- Test: `a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py`

**Interfaces:**
- Consumes: production selector and plan rules from Tasks 1–8.
- Produces: reproducible per-shape metrics and documented manual commands.

- [ ] **Step 1: Write a failing no-lookahead backtest test**

```python
def test_backtest_entry_uses_only_the_next_session_after_signal() -> None:
    trades = run_backtest(fixture_frame(), candidate_type="BREAKOUT")
    assert trades[0].signal_date == date(2026, 8, 7)
    assert trades[0].entry_date == date(2026, 8, 10)
    assert trades[0].entry_price == fixture_frame().loc["2026-08-10", "open"]
```

- [ ] **Step 2: Run the backtest test and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_short_term_selection.py -k backtest
```

Expected: FAIL until the backtest exposes production-rule trade records.

- [ ] **Step 3: Rework the backtest to call production rules**

Evaluate `BREAKOUT` and `PULLBACK` separately. Shift entry to the next session, include configurable commission and slippage, never read bars after the signal while classifying, and print JSON/text metrics for `sample_size`, `win_rate`, `profit_loss_ratio`, `expectancy_pct`, and `max_drawdown_pct`. Do not add a profitability pass gate; fail only on invalid chronology, empty required fields, or non-reproducible output.

- [ ] **Step 4: Document the manual workflow and safety semantics**

Add these commands to README:

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/select_short_term_candidates.py --output text
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/diagnose_stock.py --code 600060 --output text
```

Document completed-bar dates, `ALLOW/LIMITED/FREEZE`, observation versus executable status, missing-account behavior, no automatic order, and `--skip-lanes` retry semantics.

- [ ] **Step 5: Run all relevant verification**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_market_codes.py stock-ai/tests/unit/test_short_term_selection.py stock-ai/tests/unit/test_short_term_trade.py stock-ai/tests/unit/test_run_parallel_selection.py a-share-short-term-trading/tests
PYTHONPATH=stock-ai stock-ai/.venv/bin/python stock-ai/scripts/analysis/backtest_short_term_trade.py --output json
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/apply_migrations.py --dry-run
```

Expected: all unit tests PASS, backtest emits both setup types without chronology errors, and dry-run lists migrations 001–005.

- [ ] **Step 6: Apply the migration and run configured MySQL integration verification**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/apply_migrations.py --apply
STT_MYSQL_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/integration/test_mysql_migrations.py a-share-short-term-trading/tests/integration/test_mysql_repositories.py
```

Expected: migration 005 reports `OK`; integration tests PASS against the configured MySQL. Applying the reviewed additive migration is an authorized implementation step, but never print the root password or connection URL.

- [ ] **Step 7: Run one manual shadow selection and inspect persistence**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/select_short_term_candidates.py --output text
```

Expected: a dated chat report with at most five names, both types when qualified, legal price ordering, explicit portfolio approval state, rejection summary, and no order execution. Re-run with `--skip-lanes`; candidate/plan row counts for the same date/rule remain unchanged.

- [ ] **Step 8: Commit final verification and documentation changes**

```bash
git add stock-ai/scripts/analysis/backtest_short_term_trade.py stock-ai/tests/unit/test_short_term_selection.py a-share-short-term-trading/README.md a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py
git commit -m "docs(stt): verify automatic short-term selection"
```

Expected: only automatic-selection files are committed; unrelated workspace changes remain untouched.
