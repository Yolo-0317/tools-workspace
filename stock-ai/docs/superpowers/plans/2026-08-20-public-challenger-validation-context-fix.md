# Public Challenger Validation Context Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让公开短线挑战者的独立指标始终使用调用方提供的完整阶段交易日历和正确阶段标签，并阻止 V3 日期错配。

**Architecture:** `compare_with_v3()` 保留现有配对结论职责，但不再推导或伪造日历；研究和测试运行时分别显式传入 validation/test 切分。评估语义修复后将 evaluator 版本升级到 v2，使错误的 v1 研究产物不能被继续用于冻结。

**Tech Stack:** Python 3.11、dataclasses、Decimal、pytest 9、现有不可变 JSON 报告链

## Global Constraints

- 不改变信号、成交、成本、容量、门槛或策略参数。
- 不读取或运行一次性测试段。
- 不执行 `freeze` 或 `test`。
- 不生成或拼接 V3 可比产物。
- 修复后只重新运行 `research`，产物保持 `test_outcomes_read=false`、`trade_permission=NO-TRADE`。
- 不写持仓、订单、个人决策记忆或凭据。

---

### Task 1: 用失败测试锁定显式阶段上下文

**Files:**
- Modify: `tests/unit/test_public_challenger_validation.py`
- Modify: `tests/unit/test_public_challenger_runtime.py`

**Interfaces:**
- Consumes: 当前 `compare_with_v3(*, challenger, v3_days, input_fingerprint)`。
- Produces: 新接口的行为契约：`compare_with_v3(*, challenger, v3_days, trading_dates, segment, input_fingerprint)`。

- [ ] **Step 1: 增加无 V3 的完整验证日历测试**

在 `tests/unit/test_public_challenger_validation.py` 增加：

```python
def test_compare_without_v3_uses_explicit_validation_calendar() -> None:
    calendar = _weekday_dates(126)
    challenger = _qualifying_observations()

    assessment = compare_with_v3(
        challenger=challenger,
        v3_days=None,
        trading_dates=calendar,
        segment="VALIDATION",
        input_fingerprint="fingerprint-validation-calendar",
    )
    expected = evaluate_execution_segment(
        challenger,
        trading_dates=calendar,
        segment="VALIDATION",
    )

    assert assessment.execution_metrics == expected
    assert assessment.verdict == "INCONCLUSIVE"
    assert assessment.reasons == ("V3_COMPARABLE_MISSING",)
```

- [ ] **Step 2: 增加 V3 日期错配失败关闭测试**

```python
def test_compare_rejects_v3_calendar_mismatch() -> None:
    calendar = _weekday_dates(126)
    challenger = _qualifying_observations()
    v3_days = _v3_calendar(
        challenger,
        return_builder=lambda _row, _index: Decimal("0"),
    )

    with pytest.raises(ValueError, match="V3_CALENDAR_MISMATCH"):
        compare_with_v3(
            challenger=challenger,
            v3_days=v3_days[:-1],
            trading_dates=calendar,
            segment="TEST",
            input_fingerprint="fingerprint-calendar-mismatch",
        )
```

- [ ] **Step 3: 强化运行时阶段标签断言**

在 `test_research_builds_train_and_validation_without_reading_test_outcomes` 中增加：

```python
assert review.validation_assessment.execution_metrics.segment == "VALIDATION"
assert (
    review.validation_assessment.execution_metrics.positive_window_ratio
    == review.track_metrics[EXECUTION_TRACK].positive_window_ratio
)
```

在 `test_test_builder_is_inconclusive_without_same_segment_v3` 中增加：

```python
assert review.assessment.execution_metrics.segment == "TEST"
```

- [ ] **Step 4: 运行新测试确认红灯**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_public_challenger_validation.py::test_compare_without_v3_uses_explicit_validation_calendar \
  tests/unit/test_public_challenger_validation.py::test_compare_rejects_v3_calendar_mismatch \
  tests/unit/test_public_challenger_runtime.py::test_research_builds_train_and_validation_without_reading_test_outcomes \
  tests/unit/test_public_challenger_runtime.py::test_test_builder_is_inconclusive_without_same_segment_v3 -q
```

Expected: 新接口参数尚不存在，或研究阶段仍返回 `segment="TEST"`，测试失败。

---

### Task 2: 实现显式日历与阶段传播

**Files:**
- Modify: `stock_ai/buy_point_selection/public_challenger_validation.py`
- Modify: `stock_ai/buy_point_selection/public_challenger_runtime.py`
- Modify: `tests/unit/test_public_challenger_validation.py`

**Interfaces:**
- Consumes: Task 1 的显式接口测试。
- Produces: `compare_with_v3(*, challenger, v3_days, trading_dates: Sequence[date], segment: str, input_fingerprint: str) -> ChallengerAssessment`。

- [ ] **Step 1: 修改比较器签名并删除合成日历**

实现核心逻辑：

```python
def compare_with_v3(
    *,
    challenger: Sequence[ChallengerObservation],
    v3_days: Sequence[V3ComparableDay] | None,
    trading_dates: Sequence[date],
    segment: str,
    input_fingerprint: str,
) -> ChallengerAssessment:
    if not input_fingerprint:
        raise ValueError("INPUT_FINGERPRINT_EMPTY")
    if segment not in {"VALIDATION", "TEST"}:
        raise ValueError("SEGMENT_INVALID")
    calendar = _calendar(trading_dates)
    if v3_days is not None and tuple(row.signal_date for row in v3_days) != calendar:
        raise ValueError("V3_CALENDAR_MISMATCH")
    execution_metrics = evaluate_execution_segment(
        challenger,
        trading_dates=calendar,
        segment=segment,
    )
```

保留现有 portfolio、paired comparison 和 verdict 规则，不再生成 63 个连续自然日。

- [ ] **Step 2: 更新所有验证层测试调用**

所有 `compare_with_v3()` 调用显式传入完整 `trading_dates` 与阶段。现有冻结结论测试使用：

```python
trading_dates = (
    tuple(row.signal_date for row in v3_days)
    if v3_days is not None
    else _weekday_dates(126)
)
assessment = compare_with_v3(
    challenger=challenger,
    v3_days=v3_days,
    trading_dates=trading_dates,
    segment="TEST",
    input_fingerprint=f"fingerprint-{case}",
)
```

- [ ] **Step 3: 更新研究与测试运行时调用**

研究阶段传入：

```python
assessment = compare_with_v3(
    challenger=execution_observations,
    v3_days=None,
    trading_dates=split.validation,
    segment="VALIDATION",
    input_fingerprint=inputs.input_fingerprint,
)
```

测试阶段传入：

```python
assessment = compare_with_v3(
    challenger=execution_observations,
    v3_days=v3.days if v3 is not None else None,
    trading_dates=split.test,
    segment="TEST",
    input_fingerprint=inputs.input_fingerprint,
)
```

- [ ] **Step 4: 运行 Task 1 测试确认绿灯**

Run: Task 1 Step 4 的完整命令。

Expected: `4 passed`。

---

### Task 3: 升级评估器版本并回归不可变产物链

**Files:**
- Modify: `stock_ai/buy_point_selection/public_challenger_execution.py`
- Modify: `tests/unit/test_public_challenger_report.py`
- Test: `tests/unit/test_analyze_public_short_term_challenger_cli.py`

**Interfaces:**
- Consumes: 修复后的评估语义。
- Produces: `PUBLIC_CHALLENGER_EVALUATOR_VERSION = "public-challenger-evaluator-v2"`，新研究产物获得新身份，旧 v1 产物不能取得冻结资格。

- [ ] **Step 1: 增加版本断言**

在 `tests/unit/test_public_challenger_report.py` 增加：

```python
def test_public_challenger_artifact_uses_validation_context_evaluator_v2() -> None:
    assert PUBLIC_CHALLENGER_EVALUATOR_VERSION == "public-challenger-evaluator-v2"
```

并从 `public_challenger_execution` 导入该常量。

- [ ] **Step 2: 运行版本测试确认红灯**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_public_challenger_report.py::test_public_challenger_artifact_uses_validation_context_evaluator_v2 -q
```

Expected: v1 与期望 v2 不一致，测试失败。

- [ ] **Step 3: 升级评估器版本**

将：

```python
PUBLIC_CHALLENGER_EVALUATOR_VERSION = "public-challenger-evaluator-v1"
```

改为：

```python
PUBLIC_CHALLENGER_EVALUATOR_VERSION = "public-challenger-evaluator-v2"
```

- [ ] **Step 4: 运行公开挑战者完整单元测试**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_public_challenger_*.py \
  tests/unit/test_analyze_public_short_term_challenger_cli.py -q
```

Expected: 全部通过，0 failed。

- [ ] **Step 5: 检查差异并提交修复**

Run:

```bash
git diff --check -- \
  stock-ai/stock_ai/buy_point_selection/public_challenger_validation.py \
  stock-ai/stock_ai/buy_point_selection/public_challenger_runtime.py \
  stock-ai/stock_ai/buy_point_selection/public_challenger_execution.py \
  stock-ai/tests/unit/test_public_challenger_validation.py \
  stock-ai/tests/unit/test_public_challenger_runtime.py \
  stock-ai/tests/unit/test_public_challenger_report.py
```

Expected: 退出码 0。

提交仅暂存上述六个文件，提交信息：

```text
fix(stock-ai)：修正挑战者验证阶段上下文
```

---

### Task 4: 重新运行真实 research 并核验新产物

**Files:**
- Runtime output: `output/research/public_short_term_challenger/`（Git 忽略，由不可变 writer 按内容身份命名）
- Reference: `scripts/analysis/analyze_public_short_term_challenger.py`

**Interfaces:**
- Consumes: Task 3 已验证并提交的 evaluator v2。
- Produces: 使用外网 MySQL、630 日窗口与完整 validation 日历的新研究产物。

- [ ] **Step 1: 只读确认最新 630 个交易日边界**

从项目 `.env` 读取外网 `MYSQL_URL`，只打印日期数量、最早日期和最晚日期，不输出连接串或凭据。

- [ ] **Step 2: 运行真实 research**

Run:

```python
from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from scripts.analysis.analyze_public_short_term_challenger import main

load_dotenv(Path(".env"), override=False)
engine = create_engine(os.environ["MYSQL_URL"], pool_pre_ping=True)
with engine.connect() as connection:
    dates = [
        str(row[0])
        for row in connection.execute(
            text(
                "SELECT DISTINCT trade_date FROM stock_daily "
                "ORDER BY trade_date DESC LIMIT 630"
            )
        )
    ]
engine.dispose()
dates.reverse()
if len(dates) != 630:
    raise SystemExit("RESEARCH_CALENDAR_NOT_630")
raise SystemExit(
    main(
        [
            "research",
            "--signal-start",
            dates[0],
            "--signal-end",
            dates[-1],
        ]
    )
)
```

将上述代码通过 `.venv/bin/python -c` 在项目根目录执行；不得打印 `MYSQL_URL`。

Expected: 生成新的不可变 research JSON；不执行 `freeze` 或 `test`。

- [ ] **Step 3: 严格加载并核验**

使用 `load_challenger_research()` 验证产物身份，并确认：

```text
validation_assessment.execution_metrics.segment == VALIDATION
validation_assessment.execution_metrics.positive_window_ratio
  == track_metrics.RESIDUAL_RECLAIM_EXECUTION.positive_window_ratio
test_outcomes_read == false
trade_permission == NO-TRADE
evaluator_version == public-challenger-evaluator-v2
```

- [ ] **Step 4: 汇报真实结果**

报告新窗口、三轨验证指标、验证资格、产物绝对路径以及运行耗时。若仍不合格，明确保持 `NO-TRADE`，不得执行后续阶段。
