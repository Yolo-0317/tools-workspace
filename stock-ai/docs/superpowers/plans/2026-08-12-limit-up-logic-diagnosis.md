# Limit-Up Logic Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, replayable limit-up logic engine to single-stock and MySQL holdings diagnosis so reports explain acceleration setups, trend continuation, and relay failure instead of only support/resistance risk.

**Architecture:** A pure `stock_ai.limit_up_logic` package owns normalized bars, feature extraction, identity classification, scoring, probability allocation, and Chinese formatting. Diagnosis entry points load completed bars through the existing MySQL adapter, combine optional theme/fund-flow/risk evidence, and inject one immutable logic card beside the existing news-impact card.

**Tech Stack:** Python 3.11+, frozen dataclasses, SQLAlchemy via existing `portfolio_db`, pytest, existing MySQL `stock_daily`, existing OpenCLI adapters.

## Global Constraints

- Use only completed daily bars for close-stage analysis; never treat an intraday bar as completed.
- Main-board limit-up detection uses `pct_chg >= 9.5`; ChiNext and STAR use `pct_chg >= 19.5`; ST stocks are not executable candidates.
- Fewer than 10 bars returns `DATA_INSUFFICIENT`; 10–19 bars disclose incomplete trend/pressure evidence.
- Concept labels alone do not add theme/sector points; active-theme evidence is required.
- Missing auction or seal data caps close-stage limit-up acceleration probability at 45%; absolute close-stage cap is 55%.
- Material official risk produces `RISK_VETOED` for new risk but does not block protective reduction or exit.
- The three integer path probabilities must total exactly 100.
- The engine must not output auto-ordering, guaranteed returns, or inevitable-limit-up language.
- Existing news-impact interfaces remain backward compatible and the same event must not be double-counted.
- Preserve unrelated dirty-worktree files and do not commit holdings, credentials, or personal memory.
- User-visible output must not contain emoji.

---

### Task 1: Domain Models and Board-Aware Bar Normalization

**Files:**
- Create: `stock-ai/stock_ai/limit_up_logic/__init__.py`
- Create: `stock-ai/stock_ai/limit_up_logic/models.py`
- Create: `stock-ai/stock_ai/limit_up_logic/features.py`
- Test: `stock-ai/tests/unit/test_limit_up_features.py`

**Interfaces:**
- Produces: `LimitUpBar`, `LimitUpContext`, `LimitUpFeatures`, `LimitUpPaths`, `LimitUpResult` frozen dataclasses.
- Produces: `normalize_bars(rows) -> tuple[LimitUpBar, ...]`.
- Produces: `limit_up_threshold(code, *, is_st=False) -> float | None`.
- Produces: `extract_limit_up_features(code, bars, *, is_st=False) -> LimitUpFeatures`.

- [ ] **Step 1: Write the failing threshold and feature tests**

```python
def test_board_specific_limit_up_thresholds():
    assert limit_up_threshold("603011") == 9.5
    assert limit_up_threshold("300001") == 19.5
    assert limit_up_threshold("688001") == 19.5
    assert limit_up_threshold("603011", is_st=True) is None

def test_two_recent_limit_ups_create_strong_limit_up_gene():
    features = extract_limit_up_features("603011", two_board_fixture())
    assert features.recent_limit_up_count == 2
    assert features.limit_up_gene == "STRONG"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_features.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'stock_ai.limit_up_logic'`.

- [ ] **Step 3: Implement immutable models and deterministic feature extraction**

```python
@dataclass(frozen=True)
class LimitUpBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    pct_chg: float
    amount: float
    pre_close: float | None = None
    turnover_rate: float | None = None

@dataclass(frozen=True)
class LimitUpContext:
    concepts: tuple[str, ...] = ()
    active_themes: tuple[str, ...] = ()
    sector_change_pct: float | None = None
    sector_limit_up_count: int | None = None
    sector_leader_strength: str = "unknown"
    main_net_inflow_ratio: float | None = None
    consecutive_inflow_days: int | None = None
    material_risk: bool = False
    material_risk_reasons: tuple[str, ...] = ()
    auction_strength: str = "unknown"
    seal_quality: str = "unknown"
    reopen_count: int | None = None
    observed_at: datetime | None = None
```

Compute MA5/10/20, recent limit-up indices, post-board retention, post-board support break, five/20-day amount ratios, close location, upper-shadow ratio, five-day return, distance from recent board close, and prior-20-day-high distance. Return a structured insufficient-data result instead of raising for short histories.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_features.py -v`

Expected: PASS.

- [ ] **Step 5: Commit only Task 1 files**

```bash
git add stock-ai/stock_ai/limit_up_logic stock-ai/tests/unit/test_limit_up_features.py
git commit -m "feat(stock-ai): extract limit-up setup features"
```

### Task 2: Identity, Score, Risk Veto, and Three-Path Probability

**Files:**
- Create: `stock-ai/stock_ai/limit_up_logic/scoring.py`
- Create: `stock-ai/stock_ai/limit_up_logic/service.py`
- Test: `stock-ai/tests/unit/test_limit_up_scoring.py`
- Test: `stock-ai/tests/unit/test_limit_up_replay.py`

**Interfaces:**
- Consumes: `LimitUpFeatures` and `LimitUpContext` from Task 1.
- Produces: `classify_limit_up_identity(features, context) -> str`.
- Produces: `score_limit_up_setup(features, context) -> LimitUpScoreBreakdown`.
- Produces: `allocate_limit_up_paths(identity, score, context) -> LimitUpPaths`.
- Produces: `analyze_limit_up_logic(code, name, bars, context, *, is_st=False) -> LimitUpResult`.

- [ ] **Step 1: Write failing identity, veto, probability, and replay tests**

```python
def test_hedun_august_6_replay_is_second_wave_candidate():
    result = analyze_limit_up_logic(
        "603011",
        "合锻智能",
        hedun_bars_through_august_6(),
        LimitUpContext(
            concepts=("可控核聚变", "光通信模块", "工业母机"),
            active_themes=("可控核聚变",),
            sector_change_pct=2.1,
            sector_limit_up_count=3,
            sector_leader_strength="strong",
        ),
    )
    assert result.identity == "SECOND_WAVE_CANDIDATE"
    assert result.paths.acceleration <= 45
    assert sum(result.paths.as_tuple()) == 100
    assert any("首板后" in item for item in result.drivers)

def test_concepts_without_active_theme_do_not_add_sector_score():
    result = analyze_limit_up_logic(
        "603011", "合锻智能", ordinary_trend_bars(),
        LimitUpContext(concepts=("光通信模块", "工业母机", "核聚变")),
    )
    assert result.score.theme_sector == 0

def test_material_risk_vetoes_new_risk():
    result = analyze_limit_up_logic(
        "603011", "合锻智能", hedun_bars_through_august_6(),
        LimitUpContext(material_risk=True, material_risk_reasons=("官方重大风险公告",)),
    )
    assert result.identity == "RISK_VETOED"
    assert result.new_risk_forbidden
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_scoring.py tests/unit/test_limit_up_replay.py -v`

Expected: FAIL because scoring and service modules are absent.

- [ ] **Step 3: Implement the approved deterministic rules**

Use these score caps: gene `30`, price/volume `30`, theme/sector `25`, fund flow `15`. Classification priority is `DATA_INSUFFICIENT`, `RISK_VETOED`, `RELAY_FAILED`, `SECOND_WAVE_CANDIDATE`, `POST_LIMIT_HOLDING`, `FIRST_BOARD_SETUP`, `NORMAL_TREND`.

Probability allocation must start from identity bands, adjust by score in five-point steps, cap acceleration at `45` when auction/seal data are unknown, and assign the rounding remainder to trend continuation so the total remains 100.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_scoring.py tests/unit/test_limit_up_replay.py -v`

Expected: PASS, including the fixed 2026-08-06 replay.

- [ ] **Step 5: Commit only Task 2 files**

```bash
git add stock-ai/stock_ai/limit_up_logic/scoring.py stock-ai/stock_ai/limit_up_logic/service.py stock-ai/tests/unit/test_limit_up_scoring.py stock-ai/tests/unit/test_limit_up_replay.py
git commit -m "feat(stock-ai): classify limit-up acceleration paths"
```

### Task 3: Stable Chinese Logic Card

**Files:**
- Create: `stock-ai/stock_ai/limit_up_logic/formatting.py`
- Modify: `stock-ai/stock_ai/limit_up_logic/__init__.py`
- Test: `stock-ai/tests/unit/test_limit_up_formatting.py`

**Interfaces:**
- Consumes: `LimitUpResult` from Task 2.
- Produces: `format_limit_up_logic_card(result) -> str`.

- [ ] **Step 1: Write the failing formatting test**

```python
def test_card_contains_required_audit_fields_without_inevitable_language():
    card = format_limit_up_logic_card(second_wave_result())
    for text in ("【涨停逻辑】", "涨停基因", "封板驱动", "封板前提", "压制因素", "三路径", "数据缺口", "数据截止"):
        assert text in card
    assert "必然涨停" not in card
    assert "自动买入" not in card
```

- [ ] **Step 2: Run test and verify RED**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_formatting.py -v`

Expected: FAIL because the formatter is absent.

- [ ] **Step 3: Implement identity labels and compact audit formatting**

```python
IDENTITY_LABELS = {
    "DATA_INSUFFICIENT": "数据不足",
    "RISK_VETOED": "风险否决",
    "RELAY_FAILED": "接力失败",
    "SECOND_WAVE_CANDIDATE": "二波加速候选",
    "POST_LIMIT_HOLDING": "首板后承接",
    "FIRST_BOARD_SETUP": "首板预备",
    "NORMAL_TREND": "普通趋势",
}
```

The card must show a maximum of four drivers and four suppressors, preserve all missing-field labels, and render `涨停加速N% / 趋势延续N% / 接力失败N%`.

- [ ] **Step 4: Run test and verify GREEN**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_formatting.py -v`

Expected: PASS.

- [ ] **Step 5: Commit only Task 3 files**

```bash
git add stock-ai/stock_ai/limit_up_logic stock-ai/tests/unit/test_limit_up_formatting.py
git commit -m "feat(stock-ai): format limit-up diagnosis card"
```

### Task 4: MySQL Bar Adapter and Independent Diagnosis Command

**Files:**
- Create: `stock-ai/scripts/analysis/analyze_limit_up_logic.py`
- Test: `stock-ai/tests/unit/test_analyze_limit_up_logic_cli.py`

**Interfaces:**
- Consumes: existing `load_stock_daily_bars(code, limit, end_date)` output.
- Produces: CLI arguments `--code`, `--name`, `--as-of`, `--concept`, `--active-theme`, `--sector-change`, `--sector-limit-ups`, `--sector-leader`, `--main-inflow-ratio`, `--inflow-days`, `--material-risk`, and `--json`.
- Produces: `build_limit_up_result_from_db(...) -> LimitUpResult`.

- [ ] **Step 1: Write the failing CLI test against a fake bar loader**

```python
def test_cli_prints_replay_card(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_stock_daily_bars", lambda *args, **kwargs: hedun_bars_through_august_6())
    assert cli.main(["--code", "603011", "--name", "合锻智能", "--as-of", "2026-08-06", "--active-theme", "可控核聚变"]) == 0
    assert "二波加速候选" in capsys.readouterr().out
```

- [ ] **Step 2: Run test and verify RED**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_analyze_limit_up_logic_cli.py -v`

Expected: FAIL because the CLI module is absent.

- [ ] **Step 3: Implement CLI orchestration on the existing end-date-aware bar loader**

Use the existing `load_stock_daily_bars(code, limit=60, end_date=None, engine=None)` adapter. The CLI normalizes MySQL rows into `LimitUpBar`, constructs `LimitUpContext`, calls the pure service, and prints either the card or `dataclasses.asdict(result)` JSON.

- [ ] **Step 4: Run CLI and existing portfolio DB tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_analyze_limit_up_logic_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Commit only Task 4 files**

```bash
git add stock-ai/scripts/analysis/analyze_limit_up_logic.py stock-ai/tests/unit/test_analyze_limit_up_logic_cli.py
git commit -m "feat(stock-ai): add limit-up replay command"
```

### Task 5: Inject the Same Card into Single-Stock and Holdings Diagnosis

**Files:**
- Modify: `stock-ai/core_v2/analyze_specific_stocks.py`
- Modify: `stock-ai/scripts/analysis/analyze_holdings_v2.py`
- Modify: `stock-ai/tests/unit/test_diagnosis_news_prompt.py`

**Interfaces:**
- Consumes: `LimitUpResult | None` and `format_limit_up_logic_card`.
- Updates: `build_single_stock_prompt(..., limit_up_result=None)`.
- Updates: `build_holdings_prompt(..., limit_up_result=None)`.

- [ ] **Step 1: Write failing prompt integration tests**

```python
def test_single_stock_prompt_contains_limit_up_card():
    prompt = build_single_stock_prompt(..., news_result=RESULT, limit_up_result=LIMIT_UP_RESULT)
    assert "【涨停逻辑】" in prompt
    assert "涨停加速" in prompt
    assert "消息只允许有限修正概率" in prompt

def test_holdings_prompt_discloses_missing_limit_up_data():
    prompt = build_holdings_prompt(..., news_result=RESULT, limit_up_result=None)
    assert "涨停逻辑数据未提供" in prompt
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_diagnosis_news_prompt.py -v`

Expected: FAIL because both prompt builders reject `limit_up_result`.

- [ ] **Step 3: Inject the card and load one result per stock**

Both diagnosis flows load up to 60 completed MySQL bars, construct a conservative context from available concepts and current fund flow, and keep active themes empty unless verified by the existing news/board evidence. The task text must require the model to distinguish direct business from equity-investment or concept mapping and to list explicit seal prerequisites.

- [ ] **Step 4: Run prompt, news-impact, and holdings tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_diagnosis_news_prompt.py tests/unit/test_news_impact.py tests/unit/test_news_impact_integration.py -v`

Expected: PASS with existing news cards unchanged.

- [ ] **Step 5: Commit only Task 5 files**

```bash
git add stock-ai/core_v2/analyze_specific_stocks.py stock-ai/scripts/analysis/analyze_holdings_v2.py stock-ai/tests/unit/test_diagnosis_news_prompt.py
git commit -m "feat(stock-ai): inject limit-up logic into diagnosis"
```

### Task 6: Documentation and Full Verification

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md`
- Modify: `stock-ai/investment-agent/短线交易投顾系统设计书.md`

**Interfaces:**
- Documents: the independent command, data sources, identity states, probability caps, missing-data behavior, and relation to the news-impact service.

- [ ] **Step 1: Add the capability entry and diagnosis contract**

Document this runnable example:

```bash
uv run python scripts/analysis/analyze_limit_up_logic.py \
  --code 603011 --name 合锻智能 --as-of 2026-08-06 \
  --concept 可控核聚变,光通信模块,工业母机 \
  --active-theme 可控核聚变
```

- [ ] **Step 2: Run focused and related test suites**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_limit_up_features.py tests/unit/test_limit_up_scoring.py tests/unit/test_limit_up_replay.py tests/unit/test_limit_up_formatting.py tests/unit/test_analyze_limit_up_logic_cli.py tests/unit/test_diagnosis_news_prompt.py tests/unit/test_news_impact.py tests/unit/test_news_impact_integration.py -q`

Expected: all tests pass with zero failures.

- [ ] **Step 3: Run the fixed historical replay**

Run: `cd stock-ai && .venv/bin/python scripts/analysis/analyze_limit_up_logic.py --code 603011 --name 合锻智能 --as-of 2026-08-06 --concept 可控核聚变,光通信模块,工业母机 --active-theme 可控核聚变`

Expected: output identity is `二波加速候选`; it cites the August 3 board and post-board holding; acceleration probability is no greater than 45%; missing fields include auction and seal evidence.

- [ ] **Step 4: Run repository diff and syntax checks**

Run: `git diff --check`

Run: `cd stock-ai && .venv/bin/python -m compileall -q stock_ai/limit_up_logic scripts/analysis/analyze_limit_up_logic.py core_v2/analyze_specific_stocks.py scripts/analysis/analyze_holdings_v2.py`

Expected: both commands exit zero.

- [ ] **Step 5: Commit documentation**

```bash
git add stock-ai/docs/CAPABILITIES.md stock-ai/investment-agent/短线交易投顾系统设计书.md
git commit -m "docs(stock-ai): document limit-up diagnosis"
```
