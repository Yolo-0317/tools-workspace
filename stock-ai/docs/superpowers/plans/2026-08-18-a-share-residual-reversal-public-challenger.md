# A 股残差反转公开策略挑战者实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建三轨隔离的 A 股短期反转历史研究、冻结验证和一次性测试流水线，在不修改 V1/V2/V3 的前提下判断残差止跌确认策略是否具有独立、可执行的五日净收益。

**Architecture:** 新增独立的 `public_challenger_*` 模块族：纯领域信号负责公开反转和市场/行业残差，独立成交器负责直接开盘与止跌确认两种成交，组合层统一基础股票池和容量，验证层计算绝对门槛及可选 V3 配对结论，报告层只保存聚合、不可覆盖产物。MySQL、基准和点时参考数据仅由运行时适配器读取，CLI 只提供 `research`、`freeze`、`test` 三个手动阶段；前向影子筛选在一次性测试通过并再次批准后另写计划。

**Tech Stack:** Python 3.10+、标准库 `dataclasses`/`decimal`/`hashlib`/`json`/`random`、SQLAlchemy 2、现有 `BuyPointBar`/参考数据/交易成本/交易日历模块、pytest 9。

## Global Constraints

- 东财 AI 八维分析保持禁用；AI 文本不能创建、升级或覆盖交易资格。
- 只覆盖沪深主板 A 股；三轨必须使用相同点时基础股票池、日期、成本和容量。
- 三轨固定为 `A_SHARE_CONTRARIAN_REFERENCE`、`RESIDUAL_REVERSAL_CORE`、`RESIDUAL_RECLAIM_EXECUTION`。
- 原始反转固定形成期 5 日、最低 20%、持有 5 日；残差固定估计窗口 60 日、最少 40 个有效观测、信号窗口 5 日、最低 10%。
- 行业日收益使用点时成分股日收益中位数，每日有效成分少于 10 只则残差失败关闭，不得退化为仅减市场收益。
- 止跌确认固定 T+1/T+2、收盘位置不低于 60%、相对信号收盘最大反弹 3%。
- 执行层止损固定为确认日最低价减 `0.2 * ATR14`，风险距离必须处于 `1.5%—5%`，未止损第 5 个持有日收盘退出。
- `ALLOW` 最多 3 只、`LIMITED` 最多 1 只并减半风险预算、`FREEZE` 可执行数量为 0；同一行业最多 1 只。
- 历史公告缺失保留核心研究样本并标记缺口；执行时关键风险覆盖不完整只能观察且最大股数为 0。
- 至少 630 个完整信号交易日，固定 60%/20%/20% 时间切分；测试身份只能运行一次，测试结果不得反向调参。
- 公开核心两轨永远 `NO-TRADE`；执行层通过历史门槛也只允许进入后续另行批准的手动前向影子。
- 不修改 V1、V2、V3 代码、产物身份和发布状态；不触发通知、持仓、记忆或订单副作用。
- 新 JSON 只保存聚合统计、规则与指纹，不保存股票代码观察行、持仓、个人记忆或凭据。
- 不触碰当前工作区中无关的公众号、公告数据源、个人记忆或环境文件改动；每个提交只暂存本任务列出的文件。

---

## File Map

- Create `stock_ai/buy_point_selection/public_challenger_signals.py`: 三轨标识、信号模型、五日原始反转、行业日收益和确定性市场/行业残差。
- Create `stock_ai/buy_point_selection/public_challenger_execution.py`: 直接开盘成交、回踩收复确认、ATR 止损、固定五日退出和费用模拟。
- Create `stock_ai/buy_point_selection/public_challenger_portfolio.py`: 共同股票池资格、风险覆盖、市场容量、行业去集中和观察漏斗。
- Create `stock_ai/buy_point_selection/public_challenger_validation.py`: 时间段指标、集中度、确定性区块 bootstrap、独立资格和四类结论。
- Create `stock_ai/buy_point_selection/public_challenger_report.py`: research/validation/freeze/test 聚合产物、严格加载器、不可覆盖写入和血缘验证。
- Create `stock_ai/buy_point_selection/public_challenger_runtime.py`: 点时输入模型、MySQL/基准适配、三轨逐日构建以及 research/test review。
- Create `scripts/analysis/analyze_public_short_term_challenger.py`: 三阶段手动 CLI，失败时只输出固定中文错误。
- Create matching `tests/unit/test_public_challenger_*.py` and `tests/unit/test_analyze_public_short_term_challenger_cli.py`.
- Modify `docs/CAPABILITIES.md`: 仅在所有历史研究代码和测试完成后登记能力边界和 `NO-TRADE` 状态。

## Task 1: 三轨纯信号与确定性残差

**Files:**
- Create: `stock_ai/buy_point_selection/public_challenger_signals.py`
- Test: `tests/unit/test_public_challenger_signals.py`

**Interfaces:**
- Consumes: `BuyPointBar`, `SectorMembership`, `matched_index_id(code: str) -> str`。
- Produces: `ChallengerSignal`, `ResidualEstimate`, `build_contrarian_signals(*, signal_date: date, bars_by_code: Mapping[str, Sequence[BuyPointBar]], sector_by_code: Mapping[str, str]) -> tuple[ChallengerSignal, ...]`, `build_residual_signals(*, signal_date: date, bars_by_code: Mapping[str, Sequence[BuyPointBar]], memberships: Sequence[SectorMembership], index_closes: Mapping[str, Mapping[date, Decimal]]) -> tuple[ChallengerSignal, ...]`, `build_execution_signals(core_signals: Sequence[ChallengerSignal]) -> tuple[ChallengerSignal, ...]`, `PUBLIC_CHALLENGER_SIGNAL_VERSION`。

- [x] **Step 1: 写原始反转和五日边界的失败测试**

```python
def test_contrarian_uses_t_minus_5_close_and_stable_code_tie_break():
    signals = build_contrarian_signals(
        signal_date=date(2026, 1, 12),
        bars_by_code={
            "600002": bars_with_closes("600002", [10, 9, 9, 9, 9, 9]),
            "600001": bars_with_closes("600001", [10, 9, 9, 9, 9, 9]),
            "600003": bars_with_closes("600003", [10, 10, 10, 10, 10, 10]),
            "600004": bars_with_closes("600004", [10, 11, 11, 11, 11, 11]),
            "600005": bars_with_closes("600005", [10, 12, 12, 12, 12, 12]),
        },
        sector_by_code={code: "S1" for code in ("600001", "600002", "600003", "600004", "600005")},
    )
    assert [row.code for row in signals if row.in_candidate_pool] == ["600001"]
    assert signals[0].formation_return == Decimal("-0.1")
    assert [row.code for row in signals if row.reference_bucket == "WINNER"] == ["600005"]
```

- [x] **Step 2: 运行定向测试确认因模块不存在而失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_signals.py::test_contrarian_uses_t_minus_5_close_and_stable_code_tie_break`

Expected: FAIL with `ModuleNotFoundError: stock_ai.buy_point_selection.public_challenger_signals`.

- [x] **Step 3: 实现三轨常量、不可变信号模型和原始反转排序**

```python
CONTRARIAN_TRACK = "A_SHARE_CONTRARIAN_REFERENCE"
RESIDUAL_TRACK = "RESIDUAL_REVERSAL_CORE"
EXECUTION_TRACK = "RESIDUAL_RECLAIM_EXECUTION"
PUBLIC_CHALLENGER_SIGNAL_VERSION = "public-challenger-signals-v1"

@dataclass(frozen=True)
class ChallengerSignal:
    track_id: str
    signal_date: date
    code: str
    sector_code: str
    matched_index_id: str
    signal_close: Decimal
    formation_return: Decimal
    residual_5d: Decimal | None
    market_percentile: Decimal
    sector_percentile: Decimal | None
    reference_bucket: str | None
    in_candidate_pool: bool
    audit_reasons: tuple[str, ...] = ()

def _five_session_return(bars: Sequence[BuyPointBar]) -> Decimal:
    if len(bars) < 6:
        raise ValueError("five-session return requires six closes")
    return bars[-1].close / bars[-6].close - Decimal("1")
```

`build_contrarian_signals` 必须对完整横截面按 `(formation_return, code)` 排序，以 `ceil(n * 0.20)` 之前的股票标记 `reference_bucket="LOSER"` 和候选，以最后同样数量标记 `reference_bucket="WINNER"`，其余为 `MIDDLE`；不得对不足 5 只的横截面产生候选。赢家行只用于价差诊断，不能进入只做多容量组合。

- [x] **Step 4: 写回归窗口、行业中位数和失败关闭测试**

```python
def test_residual_estimation_excludes_last_five_sessions():
    estimate = estimate_residual_signal(
        stock_returns=stock_returns_with_last_five_shock(),
        market_returns=flat_returns(65),
        sector_returns=flat_returns(65),
        estimation_dates=dates[:60],
        signal_dates=dates[60:65],
    )
    assert estimate.estimation_dates == tuple(dates[:60])
    assert estimate.signal_dates == tuple(dates[60:65])
    assert estimate.residual_5d == Decimal("-0.25")

def test_residual_rejects_sector_day_with_fewer_than_ten_members():
    with pytest.raises(ValueError, match="SECTOR_MEMBERS_BELOW_10"):
        build_sector_returns(signal_date, bars_by_code, membership, minimum_members=10)
```

- [x] **Step 5: 运行新增测试确认缺少残差接口而失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_signals.py -k 'residual or sector'`

Expected: FAIL with missing `estimate_residual_signal` and `build_sector_returns`.

- [x] **Step 6: 用 Decimal 正规方程实现 60/5 残差和最低 10% 排序**

```python
@dataclass(frozen=True)
class ResidualEstimate:
    alpha: Decimal
    beta_market: Decimal
    beta_sector: Decimal
    estimation_dates: tuple[date, ...]
    signal_dates: tuple[date, ...]
    residual_5d: Decimal

def _design_row(market: Decimal, sector: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    return Decimal("1"), market, sector - market

def estimate_residual_signal(
    *,
    stock_returns: Mapping[date, Decimal],
    market_returns: Mapping[date, Decimal],
    sector_returns: Mapping[date, Decimal],
    estimation_dates: Sequence[date],
    signal_dates: Sequence[date],
) -> ResidualEstimate:
    if set(estimation_dates) & set(signal_dates):
        raise ValueError("ESTIMATION_SIGNAL_OVERLAP")
    if len(estimation_dates) < 40 or len(signal_dates) != 5:
        raise ValueError("RESIDUAL_WINDOW_INCOMPLETE")
    rows = tuple(_design_row(market_returns[d], sector_returns[d]) for d in estimation_dates)
    targets = tuple(stock_returns[d] for d in estimation_dates)
    coefficients = _solve_decimal_normal_equations(rows, targets)
    residual = sum(
        stock_returns[d] - sum(x * b for x, b in zip(_design_row(market_returns[d], sector_returns[d]), coefficients))
        for d in signal_dates
    )
    return ResidualEstimate(*coefficients, tuple(estimation_dates), tuple(signal_dates), residual)
```

`_solve_decimal_normal_equations` 使用带稳定主元选择的 3×3 Decimal 高斯消元；奇异矩阵抛 `ValueError("RESIDUAL_REGRESSION_SINGULAR")`。`build_residual_signals` 只接纳完整估计，按 `(residual_5d, code)` 排序，以 `ceil(n * 0.10)` 标记候选，并计算全市场及行业内百分位。`build_execution_signals` 只允许接收 `RESIDUAL_REVERSAL_CORE` 行，并用 `dataclasses.replace(row, track_id=EXECUTION_TRACK)` 生成同一信号身份的执行轨，不得重新计算或重新排序残差。

- [x] **Step 7: 运行信号测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_signals.py`

Expected: PASS.

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_signals.py stock-ai/tests/unit/test_public_challenger_signals.py
git commit -m "feat(stock-ai)：实现公开反转与五日残差信号"
```

## Task 2: 两种成交语义、止损和五日退出

**Files:**
- Create: `stock_ai/buy_point_selection/public_challenger_execution.py`
- Test: `tests/unit/test_public_challenger_execution.py`

**Interfaces:**
- Consumes: `ChallengerSignal`, `BuyPointBar`, `ExecutionCosts`, `atr14`, `evaluation_position`。
- Produces: `ChallengerPlan`, `ChallengerTrade`, `simulate_direct_five_day(signal: ChallengerSignal, bars: Sequence[BuyPointBar], costs: ExecutionCosts) -> ChallengerTrade`, `simulate_reclaim_five_day(signal: ChallengerSignal, bars: Sequence[BuyPointBar], costs: ExecutionCosts) -> ChallengerTrade`, `simulate_next_open_after_reclaim(signal: ChallengerSignal, bars: Sequence[BuyPointBar], costs: ExecutionCosts) -> ChallengerTrade`, `PUBLIC_CHALLENGER_EVALUATOR_VERSION`。

- [ ] **Step 1: 写直接开盘、第五日退出和一字板测试**

```python
def test_direct_track_enters_next_open_and_exits_fifth_holding_close():
    trade = simulate_direct_five_day(signal(), future_bars(), costs=zero_costs())
    assert trade.entry_date == date(2026, 1, 13)
    assert trade.entry_price == Decimal("9.80")
    assert trade.exit_date == date(2026, 1, 19)
    assert trade.exit_price == Decimal("10.30")
    assert trade.status == "TIME_EXIT_GAIN"

def test_direct_track_does_not_fill_locked_limit_up_or_down():
    assert simulate_direct_five_day(signal(), [locked_limit_up_bar()]).status == "CANCELLED"
    assert simulate_direct_five_day(signal(), [locked_limit_down_bar()]).status == "CANCELLED"
```

- [ ] **Step 2: 运行测试确认执行模块不存在**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_execution.py -k direct`

Expected: FAIL with module import error.

- [ ] **Step 3: 实现计划、成交结果和直接五日模拟**

```python
PUBLIC_CHALLENGER_EVALUATOR_VERSION = "public-challenger-evaluator-v1"

@dataclass(frozen=True)
class ChallengerPlan:
    signal: ChallengerSignal
    valid_entry_dates: tuple[date, ...]
    entry_kind: str
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"
    executable_shares: int = 0

@dataclass(frozen=True)
class ChallengerTrade:
    track_id: str
    signal_date: date
    status: str
    entry_date: date | None
    entry_price: Decimal | None
    exit_date: date | None
    exit_price: Decimal | None
    stop_price: Decimal | None
    net_return: Decimal | None
    mfe: Decimal | None
    mae: Decimal | None
    reasons: tuple[str, ...]
```

直接轨下一可交易日开盘加滑点成交，入口一字板或数据无效取消；持有日包含入场日，第 5 个持有日收盘减滑点、佣金和印花税退出。未达到五个持有日返回 `PENDING`，不得提前计算收益。

- [ ] **Step 4: 写 T+1/T+2 收复、3% 取消和 ATR 风险距离测试**

```python
def test_reclaim_requires_touch_reclaim_and_upper_sixty_percent_close():
    trade = simulate_reclaim_five_day(
        signal(), reclaim_bars(low="9.70", high="10.20", close="10.10"), costs=zero_costs()
    )
    assert trade.entry_price == Decimal("10.10")
    assert trade.stop_price == Decimal("9.60")

@pytest.mark.parametrize("reason", ["NO_TOUCH", "NO_RECLAIM", "WEAK_CLOSE", "CHASE_CANCELLED"])
def test_reclaim_rejects_invalid_confirmation(reason):
    assert reason in simulate_reclaim_five_day(signal(), bars_for(reason)).reasons

def test_reclaim_rejects_risk_outside_one_point_five_to_five_percent():
    assert simulate_reclaim_five_day(signal(), too_tight_stop_bars()).reasons == ("RISK_DISTANCE_OUT_OF_RANGE",)
```

- [ ] **Step 5: 运行测试确认回踩接口缺失**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_execution.py -k reclaim`

Expected: FAIL with missing `simulate_reclaim_five_day`.

- [ ] **Step 6: 实现止跌确认、止损、跌停延迟与下一开盘敏感性**

```python
def _reclaim_confirmed(signal_close: Decimal, bar: BuyPointBar) -> tuple[bool, str | None]:
    if bar.high <= bar.low:
        return False, "INVALID_RANGE"
    if bar.low > signal_close:
        return False, "NO_TOUCH"
    if bar.close < signal_close:
        return False, "NO_RECLAIM"
    if (bar.close - bar.low) / (bar.high - bar.low) < Decimal("0.60"):
        return False, "WEAK_CLOSE"
    if bar.close / signal_close - Decimal("1") > Decimal("0.03"):
        return False, "CHASE_CANCELLED"
    return True, None
```

确认窗口严格取 T 后前两个交易日；主结果按确认日收盘加滑点，敏感性结果调用独立 `simulate_next_open_after_reclaim`。失效价向下取分位价，止损遵循开盘穿越和一字跌停延迟；未止损第 5 个持有日退出，不设置 2R 止盈。

- [ ] **Step 7: 运行执行测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_execution.py`

Expected: PASS.

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_execution.py stock-ai/tests/unit/test_public_challenger_execution.py
git commit -m "feat(stock-ai)：实现残差反转确认与五日成交"
```

## Task 3: 共同资格、风险覆盖和同容量组合

**Files:**
- Create: `stock_ai/buy_point_selection/public_challenger_portfolio.py`
- Test: `tests/unit/test_public_challenger_portfolio.py`

**Interfaces:**
- Consumes: 三轨 `ChallengerSignal`、`ReferenceCoverage`、`RiskFlag`、市场状态和已有持仓代码。
- Produces: `ChallengerCandidateDecision`, `ChallengerDailySelection`, `eligible_universe_on(signal_date: date, bars_by_code: Mapping[str, Sequence[BuyPointBar]], memberships: Sequence[SectorMembership], held_codes: frozenset[str]) -> tuple[str, ...]`, `qualify_track_signals(*, signals: Sequence[ChallengerSignal], coverage: ReferenceCoverage, risk_flags: Sequence[RiskFlag], held_codes: frozenset[str]) -> Mapping[str, ChallengerCandidateDecision]`, `select_capacity_matched(decisions: Sequence[ChallengerCandidateDecision], market_status: str) -> ChallengerDailySelection`。

- [ ] **Step 1: 写三轨同股票池和风险缺失隔离测试**

```python
def test_missing_announcement_keeps_core_but_blocks_execution():
    decisions = qualify_track_signals(
        signals=three_track_signals("600001"),
        coverage=ReferenceCoverage(day, True, True, False),
        risk_flags=(),
        held_codes=frozenset(),
    )
    assert decisions[CONTRARIAN_TRACK].research_eligible is True
    assert decisions[RESIDUAL_TRACK].research_eligible is True
    assert decisions[EXECUTION_TRACK].executable_shares == 0
    assert "RISK_DATA_MISSING" in decisions[EXECUTION_TRACK].reasons

def test_veto_flag_blocks_execution_without_deleting_core_observation():
    decisions = qualify_track_signals(
        signals=three_track_signals("600001"),
        coverage=ReferenceCoverage(day, True, True, True),
        risk_flags=(veto_flag("600001"),),
        held_codes=frozenset(),
    )
    assert decisions[RESIDUAL_TRACK].research_eligible is True
    assert decisions[EXECUTION_TRACK].trade_permission == "NO-TRADE"
```

- [ ] **Step 2: 运行测试确认组合模块不存在**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_portfolio.py -k 'missing or veto'`

Expected: FAIL with module import error.

- [ ] **Step 3: 实现资格结果和确定性风险处理**

```python
@dataclass(frozen=True)
class ChallengerCandidateDecision:
    signal: ChallengerSignal
    research_eligible: bool
    execution_eligible: bool
    trade_permission: str
    executable_shares: int
    reasons: tuple[str, ...]

def _active_veto(code: str, signal_date: date, flags: Sequence[RiskFlag]) -> bool:
    return any(
        row.code == code
        and row.severity == "VETO"
        and row.effective_from <= signal_date
        and (row.effective_to is None or signal_date <= row.effective_to)
        for row in flags
    )
```

已有持仓、ST、退市整理、停牌、流动性不足和点时证券状态缺失在共同股票池阶段排除；公告缺失仅阻断执行轨。利好公告和 AI 文本不进入函数参数。

- [ ] **Step 4: 写 ALLOW/LIMITED/FREEZE、同业一只和漏斗测试**

```python
@pytest.mark.parametrize(("status", "expected"), [("ALLOW", 3), ("LIMITED", 1), ("FREEZE", 0)])
def test_capacity_matches_market_status(status, expected):
    result = select_capacity_matched(decisions_across_four_sectors(), market_status=status)
    assert len(result.selected) == expected

def test_capacity_keeps_only_one_stock_per_sector_and_counts_rejection():
    result = select_capacity_matched(two_best_same_sector(), market_status="ALLOW")
    assert [row.signal.code for row in result.selected] == ["600001"]
    assert result.funnel_counts["SECTOR_CAPACITY"] == 1
```

- [ ] **Step 5: 实现稳定容量选择与全候选反事实**

```python
@dataclass(frozen=True)
class ChallengerDailySelection:
    signal_date: date
    track_id: str
    all_eligible: tuple[ChallengerCandidateDecision, ...]
    selected: tuple[ChallengerCandidateDecision, ...]
    funnel_counts: Mapping[str, int]

def _ranking_key(row: ChallengerCandidateDecision) -> tuple[Decimal, str]:
    signal = row.signal
    score = signal.residual_5d if signal.residual_5d is not None else signal.formation_return
    return score, signal.code
```

容量落选仍保留在 `all_eligible`。`FREEZE` 只令 `selected=()`，不得清空核心研究候选。执行建议股数调用现有风险预算算法，`LIMITED` 减半，不足 100 股归零；历史统一名义仓位另由成交器计算。

- [ ] **Step 6: 运行组合测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_portfolio.py`

Expected: PASS.

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_portfolio.py stock-ai/tests/unit/test_public_challenger_portfolio.py
git commit -m "feat(stock-ai)：统一公开挑战者资格与容量"
```

## Task 4: 绝对门槛、区块置信区间和四类结论

**Files:**
- Create: `stock_ai/buy_point_selection/public_challenger_validation.py`
- Test: `tests/unit/test_public_challenger_validation.py`

**Interfaces:**
- Consumes: `ChallengerObservation`、交易日、可选 `V3ComparableDay`。
- Produces: `ChallengerSegmentMetrics`, `ChallengerPortfolioMetrics`, `PairedComparison`, `ChallengerAssessment`, `evaluate_execution_segment(observations: Sequence[ChallengerObservation], trading_dates: Sequence[date], segment: str) -> ChallengerSegmentMetrics`, `compare_with_v3(*, challenger: Sequence[ChallengerObservation], v3_days: Sequence[V3ComparableDay] | None, input_fingerprint: str) -> ChallengerAssessment`。

- [ ] **Step 1: 写独立收益、Wilson、止损、滚动窗口和集中度门槛测试**

```python
def test_execution_segment_requires_every_frozen_threshold():
    metrics = evaluate_execution_segment(
        qualifying_observations(40),
        trading_dates=weekday_dates(126),
        segment="VALIDATION",
    )
    assert metrics.qualifies is True
    assert metrics.reasons == ()

def test_positive_long_short_spread_cannot_rescue_negative_long_only_return():
    metrics = evaluate_reference_track(negative_losers_but_more_negative_winners())
    assert metrics.long_short_spread > 0
    assert metrics.long_only_net_expectancy < 0
    assert metrics.long_only_eligible is False
```

- [ ] **Step 2: 运行测试确认验证模块不存在**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_validation.py -k 'threshold or long_short'`

Expected: FAIL with module import error.

- [ ] **Step 3: 实现观察、段指标、组合集中度和独立资格**

```python
@dataclass(frozen=True)
class ChallengerObservation:
    signal: ChallengerSignal
    trade: ChallengerTrade
    selected: bool
    resolution_date: date

@dataclass(frozen=True)
class ChallengerSegmentMetrics:
    segment: str
    triggered_resolved: int
    net_expectancy: Decimal
    profit_factor: Decimal | None
    profitable_wilson_lower: Decimal
    stop_rate: Decimal
    positive_window_ratio: Decimal
    maximum_drawdown: Decimal
    qualifies: bool
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class ChallengerPortfolioMetrics:
    accepted_trades: int
    maximum_drawdown: Decimal
    maximum_stock_trade_share: Decimal
    maximum_stock_profit_share: Decimal
    maximum_sector_trade_share: Decimal
    maximum_sector_profit_share: Decimal
    top5_profit_share: Decimal
    qualifies: bool
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class V3ComparableDay:
    signal_date: date
    selected_keys: frozenset[str]
    net_return: Decimal

@dataclass(frozen=True)
class V3ComparableArtifact:
    schema: str
    parent_research_identity: str
    input_fingerprint: str
    split_identity: str
    days: tuple[V3ComparableDay, ...]

@dataclass(frozen=True)
class PairedComparison:
    paired_dates: int
    mean_difference: Decimal | None
    confidence_interval: tuple[Decimal, Decimal] | None
    jaccard: Decimal | None
    incremental_resolved: int
    incremental_expectancy: Decimal | None
    incremental_profit_factor: Decimal | None

@dataclass(frozen=True)
class ChallengerAssessment:
    execution_metrics: ChallengerSegmentMetrics
    portfolio_metrics: ChallengerPortfolioMetrics
    paired: PairedComparison | None
    verdict: str
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class PublicChallengerResearchReview:
    split: ChronologicalSplit
    input_fingerprint: str
    track_metrics: Mapping[str, ChallengerSegmentMetrics]
    validation_assessment: ChallengerAssessment
    funnel_counts: Mapping[str, int]
    point_in_time_complete: bool
    test_outcomes_read: bool = False
    trade_permission: str = "NO-TRADE"

@dataclass(frozen=True)
class PublicChallengerValidationReview:
    parent_research_identity: str
    input_fingerprint: str
    assessment: ChallengerAssessment
    test_eligible: bool
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class PublicChallengerFreezeReview:
    parent_research_identity: str
    input_fingerprint: str
    split_identity: str
    frozen_rule_hash: str
    test_eligible: bool
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class PublicChallengerTestReview:
    parent_freeze_identity: str
    parent_research_identity: str
    input_fingerprint: str
    assessment: ChallengerAssessment
    trade_permission: str = "NO-TRADE"
```

复用现有 Wilson 和最大回撤数学口径，但不把新观察强转成 V3 类型。验证/测试分别要求：净期望 `>0`、PF `>1.10`、Wilson 下界 `>=0.45`、止损率 `<=0.40`、63 日正窗口比例 `>=0.60`、最大回撤 `<=0.10`。实现股票、行业和 Top 5 盈利集中度门槛；不可计算即失败。

- [ ] **Step 4: 写确定性移动区块 bootstrap 和四结论测试**

```python
def test_bootstrap_is_byte_deterministic_for_same_fingerprint():
    first = moving_block_bootstrap_interval(differences(), block_size=5, samples=10_000, seed_material="abc")
    second = moving_block_bootstrap_interval(differences(), block_size=5, samples=10_000, seed_material="abc")
    assert first == second

@pytest.mark.parametrize(
    ("case", "verdict"),
    [
        (challenger_significantly_better(), "CHALLENGER_WINS"),
        (distinct_positive_incremental_pool(), "COMPLEMENTARY"),
        (v3_passes_challenger_fails(), "V3_RETAINS"),
        (missing_comparable_v3(), "INCONCLUSIVE"),
    ],
)
def test_frozen_verdicts(case, verdict):
    assert compare_with_v3(**case).verdict == verdict
```

- [ ] **Step 5: 实现配对日期、Jaccard、新增机会和区块 bootstrap**

```python
def moving_block_bootstrap_interval(
    values: Sequence[Decimal], *, block_size: int, samples: int, seed_material: str
) -> tuple[Decimal, Decimal]:
    if len(values) < block_size:
        raise ValueError("PAIRED_SAMPLE_INSUFFICIENT")
    seed = int(hashlib.sha256(seed_material.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    blocks = tuple(tuple(values[(start + offset) % len(values)] for offset in range(block_size)) for start in range(len(values)))
    means = []
    for _ in range(samples):
        draw = tuple(item for _ in range(math.ceil(len(values) / block_size)) for item in blocks[rng.randrange(len(blocks))])[: len(values)]
        means.append(sum(draw, Decimal("0")) / Decimal(len(draw)))
    ordered = sorted(means)
    return ordered[249], ordered[9749]
```

配对日期中单方无候选记 0；双方都无候选只计覆盖率。无合法同段 V3 身份时直接 `INCONCLUSIVE`。`COMPLEMENTARY` 还必须满足 Jaccard `<=0.50`、至少 30 个测试新增已解决机会、其净期望 `>0` 且 PF `>1.10`。

- [ ] **Step 6: 运行验证测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_validation.py`

Expected: PASS.

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_validation.py stock-ai/tests/unit/test_public_challenger_validation.py
git commit -m "feat(stock-ai)：冻结公开挑战者评估与胜负结论"
```

## Task 5: 聚合不可变产物与严格加载器

**Files:**
- Create: `stock_ai/buy_point_selection/public_challenger_report.py`
- Test: `tests/unit/test_public_challenger_report.py`

**Interfaces:**
- Consumes: `PublicChallengerResearchReview`、`PublicChallengerValidationReview`、`PublicChallengerFreezeReview`、`PublicChallengerTestReview` 的聚合内容。
- Produces: `write_challenger_research(review: PublicChallengerResearchReview, output_dir: Path) -> Path`, `load_challenger_research(path: Path) -> PublicChallengerResearchArtifact`, `write_challenger_validation(review: PublicChallengerValidationReview, output_dir: Path) -> Path`, `write_challenger_freeze(review: PublicChallengerFreezeReview, output_dir: Path) -> Path`, `load_challenger_freeze(path: Path) -> PublicChallengerFreezeArtifact`, `write_challenger_test_once(review: PublicChallengerTestReview, output_dir: Path) -> Path`。

- [ ] **Step 1: 写规范序列化、无代码明细、幂等和冲突测试**

```python
def test_research_payload_is_aggregate_only_and_byte_stable(tmp_path):
    first = write_challenger_research(research_review(), tmp_path)
    second = write_challenger_research(research_review(), tmp_path)
    assert first == second
    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text())
    assert "600001" not in first.read_text()
    assert payload["trade_permission"] == "NO-TRADE"

def test_same_identity_with_different_content_is_rejected(tmp_path):
    path = write_challenger_research(research_review(), tmp_path)
    path.write_text("{}\n")
    with pytest.raises(ValueError, match="immutable public challenger artifact conflict"):
        write_challenger_research(research_review(), tmp_path)
```

- [ ] **Step 2: 运行测试确认报告模块不存在**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_report.py -k 'aggregate or identity'`

Expected: FAIL with module import error.

- [ ] **Step 3: 实现四类 schema、内容身份和不可覆盖写入**

```python
RESEARCH_SCHEMA = "public-short-term-challenger-research-v1"
VALIDATION_SCHEMA = "public-short-term-challenger-validation-v1"
FREEZE_SCHEMA = "public-short-term-challenger-freeze-v1"
TEST_SCHEMA = "public-short-term-challenger-test-v1"

@dataclass(frozen=True)
class PublicChallengerResearchArtifact:
    artifact_identity: str
    input_fingerprint: str
    split_identity: str
    validation_eligible: bool
    review: PublicChallengerResearchReview
    payload: Mapping[str, object]

@dataclass(frozen=True)
class PublicChallengerFreezeArtifact:
    artifact_identity: str
    parent_research_identity: str
    input_fingerprint: str
    split_identity: str
    test_eligible: bool
    review: PublicChallengerFreezeReview
    payload: Mapping[str, object]

def _artifact_identity(content: Mapping[str, object]) -> str:
    raw = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()

def _write_exclusive_or_verify(path: Path, serialized: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError("immutable public challenger artifact conflict") from None
```

research 产物保存三轨聚合、时间切分、数据完整性、规则版本、来源偏离说明和 `test_outcomes_read=false`。validation 只保存执行层验证聚合；freeze 保存全部冻结常数、验证资格和父身份；test 文件名由 freeze 身份唯一决定并独占创建。

- [ ] **Step 4: 写严格加载、父血缘、篡改和测试污染测试**

```python
def test_loader_recomputes_identity_and_rejects_tampering(tmp_path):
    path = write_challenger_freeze(freeze_review(), tmp_path)
    payload = json.loads(path.read_text())
    payload["residual_fraction"] = "0.15"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="artifact identity mismatch"):
        load_challenger_freeze(path)

def test_test_writer_rejects_parent_or_input_fingerprint_mismatch(tmp_path):
    with pytest.raises(ValueError, match="parent lineage mismatch"):
        write_challenger_test_once(test_review(parent_freeze_identity="wrong"), tmp_path)
```

- [ ] **Step 5: 实现严格字段集合和父链校验**

加载器必须验证 schema、文件名、内容哈希、父 identity、输入 fingerprint、切分、三轨版本、成本/评估器版本、`NO-TRADE` 和污染标志。未知字段、缺失字段、股票代码明细键或 `promotion_eligible=true` 均拒绝。

- [ ] **Step 6: 运行报告测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_report.py`

Expected: PASS.

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_report.py stock-ai/tests/unit/test_public_challenger_report.py
git commit -m "feat(stock-ai)：保存公开挑战者不可变研究产物"
```

## Task 6: 点时运行时、MySQL 和双基准输入

**Files:**
- Create: `stock_ai/buy_point_selection/public_challenger_runtime.py`
- Test: `tests/unit/test_public_challenger_runtime.py`

**Interfaces:**
- Consumes: `_load_daily_bars`, `_trade_dates`, `SQLReferenceRepository`, `load_required_benchmark_closes`, `classify_market` 和前三层纯函数。
- Produces: `PublicChallengerRuntimeInputs`, `load_mysql_public_challenger_inputs(signal_dates: Sequence[date], history_start: date, outcome_cutoff: date, *, benchmark_loader: Callable) -> PublicChallengerRuntimeInputs`, `build_public_challenger_research(inputs: PublicChallengerRuntimeInputs) -> PublicChallengerResearchReview`, `build_public_challenger_test(freeze: PublicChallengerFreezeReview, research: PublicChallengerResearchReview, inputs: PublicChallengerRuntimeInputs, v3: V3ComparableArtifact | None) -> PublicChallengerTestReview`。

- [ ] **Step 1: 写有界数据加载、引擎释放和无凭据指纹测试**

```python
def test_mysql_loader_uses_literal_bounds_and_disposes_engine():
    inputs = load_mysql_public_challenger_inputs(
        signal_dates=weekday_dates(630),
        history_start=date(2023, 1, 1),
        outcome_cutoff=date(2026, 1, 31),
        engine_factory=fake_engine_factory,
        benchmark_loader=fake_benchmark_loader,
    )
    assert fake_engine.disposed is True
    assert inputs.signal_dates[0] >= date(2023, 1, 1)
    assert "mysql" not in inputs.input_fingerprint.lower()
    assert "password" not in inputs.input_fingerprint.lower()

def test_loader_rejects_missing_index_or_point_in_time_sector_coverage():
    with pytest.raises(ValueError, match="POINT_IN_TIME_INPUT_INCOMPLETE"):
        build_public_challenger_research(incomplete_runtime_inputs())
```

- [ ] **Step 2: 运行测试确认运行时模块不存在**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_runtime.py -k 'loader or coverage'`

Expected: FAIL with module import error.

- [ ] **Step 3: 实现独立运行时输入和有界 MySQL 适配器**

```python
@dataclass(frozen=True)
class PublicChallengerRuntimeInputs:
    signal_dates: tuple[date, ...]
    trading_dates: tuple[date, ...]
    bars_by_code: Mapping[str, tuple[BuyPointBar, ...]]
    memberships: tuple[SectorMembership, ...]
    risk_flags: tuple[RiskFlag, ...]
    coverage_by_date: Mapping[date, ReferenceCoverage]
    market_status_by_date: Mapping[date, str]
    index_closes: Mapping[str, Mapping[date, Decimal]]
    held_codes: frozenset[str]
    input_fingerprint: str
```

加载器读取 `MYSQL_URL` 但指纹只包含规范化数据值、日期、来源版本和规则版本。使用 `try/finally` 释放 engine。基准只允许 `sh.000001`、`sz.399001`、`sh.000688`，按 `matched_index_id` 映射；缺失端点失败关闭。持仓加载器默认只读并可在单元测试注入空集合。

- [ ] **Step 4: 写 630 日切分、边界不泄漏和三轨漏斗测试**

```python
def test_research_builds_train_and_validation_without_reading_test_outcomes():
    review = build_public_challenger_research(complete_runtime_inputs(630))
    assert len(review.split.train) == 378
    assert len(review.split.validation) == 126
    assert len(review.split.test) == 126
    assert review.test_outcomes_read is False
    assert review.trade_permission == "NO-TRADE"

def test_train_holding_period_cannot_cross_validation_boundary():
    review = build_public_challenger_research(inputs_with_boundary_signal())
    assert review.funnel_counts["OUTCOME_CROSSES_SEGMENT"] == 1
```

- [ ] **Step 5: 实现 research 和 test 构建器**

research 构建器逐日执行共同股票池、三轨信号、容量和成交，训练/验证结果按段聚合；测试日期只保存身份，不加载其结果。test 构建器必须接收严格 freeze artifact，重新加载同一测试日期输入，验证父 fingerprint 前缀，执行一次三轨评估，并在可选 V3 同段产物缺失时输出 `INCONCLUSIVE`。

- [ ] **Step 6: 运行运行时测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_public_challenger_runtime.py`

Expected: PASS.

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_runtime.py stock-ai/tests/unit/test_public_challenger_runtime.py
git commit -m "feat(stock-ai)：构建公开挑战者点时研究运行时"
```

## Task 7: 三阶段手动 CLI 和一次性测试门

**Files:**
- Create: `scripts/analysis/analyze_public_short_term_challenger.py`
- Test: `tests/unit/test_analyze_public_short_term_challenger_cli.py`

**Interfaces:**
- Consumes: Task 5 严格 artifact API、Task 6 runtime builder、现有 BaoStock/东财备用基准加载器。
- Produces: `build_parser() -> argparse.ArgumentParser`, `dispatch_stage(args: argparse.Namespace, research_input_loader: RuntimeInputLoader, test_input_loader: RuntimeInputLoader) -> tuple[Path, ...]`, `main(argv: Sequence[str] | None = None) -> int`，命令 `research`、`freeze`、`test`。

- [ ] **Step 1: 写命令面、research 失败关闭和固定错误输出测试**

```python
def test_parser_exposes_only_three_manual_stages():
    parser = module.build_parser()
    assert set(parser._subparsers._group_actions[0].choices) == {"research", "freeze", "test"}

def test_research_cli_writes_no_trade_artifact(tmp_path):
    paths = module.dispatch_stage(
        parser_args("research", tmp_path),
        research_input_loader=lambda *_: complete_runtime_inputs(630),
        test_input_loader=forbidden_loader,
    )
    assert paths[0].name.startswith("public-short-term-challenger-research-")

def test_freeze_stage_writes_validation_then_freeze(tmp_path):
    paths = module.dispatch_stage(
        valid_freeze_args(tmp_path),
        research_input_loader=forbidden_loader,
        test_input_loader=forbidden_loader,
    )
    assert paths[0].name.startswith("public-short-term-challenger-validation-")
    assert paths[1].name.startswith("public-short-term-challenger-freeze-")

def test_main_sanitizes_failure(capsys):
    assert module.main(["research", "--signal-start", "bad"]) == 2
    assert capsys.readouterr().err == "公开短线策略挑战者执行失败\n"
```

- [ ] **Step 2: 运行测试确认 CLI 不存在**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_analyze_public_short_term_challenger_cli.py -k 'parser or research or sanitizes'`

Expected: FAIL because script file does not exist.

- [ ] **Step 3: 实现 parser 和 research/freeze 分派**

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    stages = parser.add_subparsers(dest="stage", required=True)
    research = stages.add_parser("research")
    research.add_argument("--signal-start", type=_date, required=True)
    research.add_argument("--signal-end", type=_date, required=True)
    research.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    freeze = stages.add_parser("freeze")
    freeze.add_argument("--research-artifact", type=Path, required=True)
    freeze.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    test = stages.add_parser("test")
    test.add_argument("--freeze-artifact", type=Path, required=True)
    test.add_argument("--research-artifact", type=Path, required=True)
    test.add_argument("--v3-test-artifact", type=Path)
    test.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser
```

freeze 必须先严格加载 research，验证点时完整和 `test_outcomes_read=false`；随后从 research 中已冻结的训练/验证聚合构造并写 validation artifact，再以 validation 为父写唯一 freeze。没有验证资格时仍写带完整失败原因的 validation 和空 freeze，不补位，也不加载测试日期。

- [ ] **Step 4: 写 test 先验加载、重复执行和 V3 缺失测试**

```python
def test_test_stage_loads_freeze_before_market_data(tmp_path):
    with pytest.raises(ValueError, match="freeze"):
        module.dispatch_stage(bad_test_args(tmp_path), forbidden_loader, recording_test_loader)
    assert recording_test_loader.calls == []

def test_test_stage_reuses_identical_existing_bytes_but_rejects_conflict(tmp_path):
    first = module.dispatch_stage(
        valid_test_args(tmp_path),
        research_input_loader=forbidden_loader,
        test_input_loader=lambda *_: complete_runtime_inputs(630),
    )
    second = module.dispatch_stage(
        valid_test_args(tmp_path),
        research_input_loader=forbidden_loader,
        test_input_loader=forbidden_loader,
    )
    assert first == second

def test_missing_v3_comparable_artifact_forces_inconclusive(tmp_path):
    path = module.dispatch_stage(
        valid_test_args_without_v3(tmp_path),
        research_input_loader=forbidden_loader,
        test_input_loader=lambda *_: complete_runtime_inputs(630),
    )[0]
    assert json.loads(path.read_text())["verdict"] == "INCONCLUSIVE"
```

- [ ] **Step 5: 实现 test 一次性身份和可选 V3 严格适配**

V3 参数只接受未来批准的 `five-day-ranking-v3-comparable-test-v1` 聚合 schema、相同父观察集、相同切分和相同输入 fingerprint。当前不存在合法 V3 同段测试产物时不得读取 validation 或其他区间替代。测试 writer 使用 freeze identity 命名；已存在内容相同只校验，内容冲突报错。

- [ ] **Step 6: 运行 CLI 测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_analyze_public_short_term_challenger_cli.py`

Expected: PASS.

```bash
git add stock-ai/scripts/analysis/analyze_public_short_term_challenger.py stock-ai/tests/unit/test_analyze_public_short_term_challenger_cli.py
git commit -m "feat(stock-ai)：增加公开挑战者三阶段研究命令"
```

## Task 8: 交叉验证、能力文档和历史阶段收口

**Files:**
- Modify: `docs/CAPABILITIES.md`
- Test: all new unit tests plus existing buy-point regression suite.

**Interfaces:**
- Consumes: Tasks 1—7 全部接口。
- Produces: 通过完整回归的历史研究能力说明；不产生真实研究结果、不执行 MySQL、不运行一次性测试。

- [ ] **Step 1: 运行新模块全套测试**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider \
  tests/unit/test_public_challenger_signals.py \
  tests/unit/test_public_challenger_execution.py \
  tests/unit/test_public_challenger_portfolio.py \
  tests/unit/test_public_challenger_validation.py \
  tests/unit/test_public_challenger_report.py \
  tests/unit/test_public_challenger_runtime.py \
  tests/unit/test_analyze_public_short_term_challenger_cli.py
```

Expected: all tests pass, zero failures.

- [ ] **Step 2: 运行既有买点和 V3 回归套件**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider \
  tests/unit/test_buy_point_execution.py \
  tests/unit/test_five_day_return_execution.py \
  tests/unit/test_five_day_return_validation.py \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3_report.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_component_attribution.py \
  tests/unit/test_analyze_five_day_ranking_v3_cli.py
```

Expected: all tests pass, zero failures.

- [ ] **Step 3: 在能力文档登记准确边界**

在 `docs/CAPABILITIES.md` 的短线研究能力段新增：

```markdown
- A 股公开短线策略挑战者：已具备原始五日反转、市场/行业五日残差、T+1/T+2 止跌确认三轨历史研究与不可变冻结接口。当前仅 `NO-TRADE` 历史研究；未执行一次性测试，未获准进入正式选股。公开多空价差与只做多绝对收益分开报告。
```

- [ ] **Step 4: 运行项目完整单元测试**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider tests/unit`

Expected: all tests pass, zero failures. 记录实际通过数量，不沿用旧的 `573 passed`。

- [ ] **Step 5: 检查禁止副作用、敏感内容和差异范围**

Run:

```bash
rg -n "notify|order|position_sync|advisor_memory|Eastmoney.*AI|八维" \
  stock-ai/stock_ai/buy_point_selection/public_challenger_*.py \
  stock-ai/scripts/analysis/analyze_public_short_term_challenger.py
git diff --check -- \
  stock-ai/stock_ai/buy_point_selection/public_challenger_*.py \
  stock-ai/scripts/analysis/analyze_public_short_term_challenger.py \
  stock-ai/tests/unit/test_public_challenger_*.py \
  stock-ai/tests/unit/test_analyze_public_short_term_challenger_cli.py \
  stock-ai/docs/CAPABILITIES.md
git status --short
```

Expected: 第一条无运行时副作用引用；`git diff --check` 无输出；状态中只暂存本任务文档和测试相关文件，其他用户改动保持未暂存。

- [ ] **Step 6: 提交能力文档并停在人工研究运行前**

```bash
git add stock-ai/docs/CAPABILITIES.md
git commit -m "docs(stock-ai)：登记公开短线挑战者研究能力"
```

到此只完成代码和离线测试。不要连接 MySQL，不要运行 `research` 真实产物，不要执行 `freeze` 或一次性 `test`。下一轮先由用户确认实际数据范围和手动 `research` 命令；只有研究及验证证据通过后，才另行请求一次性测试授权。
