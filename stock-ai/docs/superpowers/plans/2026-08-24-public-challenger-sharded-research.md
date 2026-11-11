# Public Challenger Sharded Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将公开短线挑战者的 630 日单体研究改造成 24 个可恢复、不可变、严格校验的 21 日分片，并在不读取测试结果、不执行交易的前提下汇总 evaluator v2 研究报告。

**Architecture:** 保留现有信号、执行和 evaluator v2 数学口径，在运行时增加“分片信号日 + 完整阶段日历”的双边界接口；新增分片领域模块负责 630 日切分、分片计算和无数据库汇总，新增分片产物模块负责严格序列化、内容身份、原子写入、状态检查和父链校验。CLI 只编排 `research-prepare`、`research-shard`、`research-status`、`research-finalize`，原 `research` 改为失败关闭提示，`freeze` 与 `test` 保持原语义。

**Tech Stack:** Python 3.11、标准库 dataclasses/json/hashlib/tempfile/fcntl、pytest、现有 SQLAlchemy/MySQL 只读输入适配器、现有 public challenger evaluator v2。

## Global Constraints

- 单个计算分片固定覆盖 21 个信号交易日；训练段固定 378 日、18 片，验证段固定 126 日、6 片，测试段固定 126 日且不生成分片。
- 分片结果边界必须使用所属完整训练或验证日历，不能使用 21 日分片边界。
- `test_outcomes_read=false`、`trade_permission=NO-TRADE`、`promotion_eligible=false` 在整个链路中不可覆盖。
- 主清单不得保存持仓代码、股票观察明细、数据库地址、账号、密码或完整连接串。
- 分片明细可以保存研究股票代码、行业、信号与已结算收益，但不得保存持仓列表、账户、凭据、订单或个人决策记忆，并且只能写入 Git 忽略目录。
- 主清单和分片使用内容哈希身份、严格父链、同目录临时文件、文件刷新和原子替换；同字节重写幂等，不同字节冲突失败关闭。
- 输入指纹变化必须重新 prepare，已完成分片不得自动重算或改挂父清单。
- `research-status` 不访问市场数据且不修改产物；`research-finalize` 不访问 MySQL。
- 单片超过 600 秒只记录并输出警告，不自动改变分片大小或研究规则。
- 原 `research` 不保留隐藏绕过参数；真实验收不执行 `freeze` 或 `test`。
- 不提交 `.env`、证书、订阅链接、持仓、分片股票明细或个人记忆。

---

## File map

- Create `stock_ai/buy_point_selection/public_challenger_shards.py`: 分片定义、确定性切分、分片计算、严格汇总和状态领域模型。
- Create `stock_ai/buy_point_selection/public_challenger_shard_report.py`: 主清单与分片明细的严格 JSON 编解码、内容身份、原子不可变写入和目录扫描。
- Modify `stock_ai/buy_point_selection/public_challenger_portfolio.py`: 风险标记按六位代码的一次性不可变索引。
- Modify `stock_ai/buy_point_selection/public_challenger_runtime.py`: 双日历分片计算接口和从观察明细构建 evaluator v2 研究结果的共享函数。
- Modify `scripts/analysis/analyze_public_short_term_challenger.py`: 四个分片阶段、原 research 安全提示及只读状态输出。
- Modify `.gitignore`: 明确忽略本地 manifest、分片明细、锁和临时文件目录。
- Create `tests/unit/test_public_challenger_shards.py`: 切分、边界、分片计算、合并等价、失败关闭。
- Create `tests/unit/test_public_challenger_shard_report.py`: 严格编解码、内容身份、原子不可变写入、恢复语义。
- Modify `tests/unit/test_public_challenger_portfolio.py`: 风险索引语义等价。
- Modify `tests/unit/test_public_challenger_runtime.py`: 分片边界和单体兼容回归。
- Modify `tests/unit/test_analyze_public_short_term_challenger_cli.py`: CLI 阶段、无数据库 status/finalize、旧 research 禁用。
- Modify `docs/BUY_POINT_SELECTION_CAPABILITIES.md`: 手动分片研究命令、状态含义、恢复步骤与安全边界。

### Task 1: 风险标记索引与语义等价

**Files:**
- Modify: `stock_ai/buy_point_selection/public_challenger_portfolio.py`
- Modify: `stock_ai/buy_point_selection/public_challenger_runtime.py`
- Test: `tests/unit/test_public_challenger_portfolio.py`
- Test: `tests/unit/test_public_challenger_runtime.py`

**Interfaces:**
- Consumes: `RiskFlag`、现有 `_code6()` 和 `qualify_track_signals()`。
- Produces: `index_risk_flags(flags: Sequence[RiskFlag]) -> Mapping[str, tuple[RiskFlag, ...]]`；运行时每个候选只传 `risk_flags_by_code.get(code6, ())`。

- [ ] **Step 1: 写乱序、带市场前缀和跨有效期的等价性失败测试**

```python
def test_indexed_risk_flags_preserve_veto_semantics() -> None:
    flags = (
        _risk("SZ000001", "2024-01-08", "2024-01-09", "WARN"),
        _risk("sh.600001", "2024-01-05", "2024-01-10", "VETO"),
        _risk("600001.SH", "2024-01-11", None, "VETO"),
        _risk("000001", "2024-01-01", None, "VETO"),
    )
    indexed = index_risk_flags(flags)
    for signal_date in (date(2024, 1, 4), date(2024, 1, 8), date(2024, 1, 11)):
        full = qualify_track_signals(
            signals=(_execution_signal("600001", signal_date),),
            coverage=_coverage(signal_date),
            risk_flags=flags,
            held_codes=frozenset(),
        )
        subset = qualify_track_signals(
            signals=(_execution_signal("600001", signal_date),),
            coverage=_coverage(signal_date),
            risk_flags=indexed["600001"],
            held_codes=frozenset(),
        )
        assert subset == full
```

- [ ] **Step 2: 运行测试并确认缺少索引函数**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_portfolio.py -q`

Expected: FAIL，导入 `index_risk_flags` 失败。

- [ ] **Step 3: 实现保持输入顺序的不可变代码索引**

```python
def index_risk_flags(
    flags: Sequence[RiskFlag],
) -> Mapping[str, tuple[RiskFlag, ...]]:
    grouped: dict[str, list[RiskFlag]] = {}
    for row in flags:
        grouped.setdefault(_code6(row.code), []).append(row)
    return {
        code: tuple(values)
        for code, values in sorted(grouped.items())
    }
```

在 `_segment_observations()` 进入日期循环前只构建一次 `risk_flags_by_code`，候选调用处使用当前六位代码对应的 tuple；不要修改 `_active_veto()` 的有效期、severity 或顺序语义。

- [ ] **Step 4: 运行组合回归**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_portfolio.py tests/unit/test_public_challenger_runtime.py -q`

Expected: PASS，且现有决策测试结果不变。

- [ ] **Step 5: 提交性能修复**

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_portfolio.py stock-ai/stock_ai/buy_point_selection/public_challenger_runtime.py stock-ai/tests/unit/test_public_challenger_portfolio.py stock-ai/tests/unit/test_public_challenger_runtime.py
git commit -m "perf(stock-ai)：索引挑战者风险标记"
```

### Task 2: 分片信号日与完整阶段边界

**Files:**
- Modify: `stock_ai/buy_point_selection/public_challenger_runtime.py`
- Modify: `tests/unit/test_public_challenger_runtime.py`

**Interfaces:**
- Consumes: Task 1 的 `index_risk_flags()`。
- Produces: `_segment_observations(*, inputs: PublicChallengerRuntimeInputs, signal_dates: Sequence[date], segment_dates: Sequence[date], funnel: Counter[str]) -> tuple[ChallengerObservation, ...]`；`build_research_review_from_observations(*, split: ChronologicalSplit, input_fingerprint: str, validation_observations: Sequence[ChallengerObservation], funnel_counts: Mapping[str, int]) -> PublicChallengerResearchReview`。

- [ ] **Step 1: 写分片末尾不被误判跨段的失败测试**

```python
def test_shard_tail_uses_full_segment_calendar(monkeypatch) -> None:
    inputs = _runtime_inputs()
    split = chronological_split(inputs.signal_dates)
    shard_dates = split.validation[:21]
    funnel: Counter[str] = Counter()
    monkeypatch.setattr(runtime, "build_execution_signals", _one_signal_per_day)
    monkeypatch.setattr(runtime, "simulate_reclaim_five_day", _resolved_trade_after_five_days)

    rows = runtime._segment_observations(
        inputs=inputs,
        signal_dates=shard_dates,
        segment_dates=split.validation,
        funnel=funnel,
    )

    assert any(row.signal.signal_date == shard_dates[-1] for row in rows)
    assert funnel["OUTCOME_CROSSES_SEGMENT"] == 0
```

另写真实阶段尾部测试：`signal_dates=split.validation[-7:]` 时仍按保守 7 日余量产生 `OUTCOME_CROSSES_SEGMENT`，且绝不读取 `split.test`。

- [ ] **Step 2: 运行两个边界测试并确认旧签名失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_runtime.py -q`

Expected: FAIL，`_segment_observations()` 不接受 `signal_dates`。

- [ ] **Step 3: 实现双日历接口和共享 evaluator 构建函数**

```python
def _segment_observations(*, inputs, signal_dates, segment_dates, funnel):
    work_dates = _strict_dates(signal_dates, "SHARD_SIGNAL")
    full_segment = _strict_dates(segment_dates, "SEGMENT")
    positions = {value: index for index, value in enumerate(full_segment)}
    if any(value not in positions for value in work_dates):
        raise ValueError("SHARD_DATES_OUTSIDE_SEGMENT")
    segment_end = full_segment[-1]
    # 原信号、筛选和执行循环只迭代 work_dates。
    # remaining 始终按 len(full_segment) - positions[signal_date] - 1 计算。
```

将现有 evaluator v2 汇总数学抽到 `build_research_review_from_observations()`；`build_public_challenger_research()` 继续分别以完整 train 和 validation 同时作为 `signal_dates`/`segment_dates` 调用，再通过共享函数生成完全相同的研究结果。

- [ ] **Step 4: 运行运行时全文件测试**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_runtime.py -q`

Expected: PASS；单体研究 fixture 的 payload 与改造前保持一致。

- [ ] **Step 5: 提交边界重构**

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_runtime.py stock-ai/tests/unit/test_public_challenger_runtime.py
git commit -m "refactor(stock-ai)：分离挑战者分片与阶段边界"
```

### Task 3: 确定性主清单与 24 个分片定义

**Files:**
- Create: `stock_ai/buy_point_selection/public_challenger_shards.py`
- Create: `tests/unit/test_public_challenger_shards.py`

**Interfaces:**
- Consumes: `PublicChallengerRuntimeInputs`、`chronological_split()`、四个现有版本常量。
- Produces: `ResearchShardDefinition`、`PublicChallengerResearchManifest`、`build_research_manifest(inputs: PublicChallengerRuntimeInputs, shard_size: int = 21) -> PublicChallengerResearchManifest`、`find_shard(manifest, shard_id) -> ResearchShardDefinition`。

- [ ] **Step 1: 写 630 日精确切分与敏感字段缺席测试**

```python
def test_manifest_partitions_exactly_18_train_and_6_validation_shards() -> None:
    manifest = build_research_manifest(_runtime_inputs(), shard_size=21)
    train = tuple(row for row in manifest.shards if row.segment == "TRAIN")
    validation = tuple(row for row in manifest.shards if row.segment == "VALIDATION")
    assert len(train) == 18
    assert len(validation) == 6
    assert all(len(row.signal_dates) == 21 for row in manifest.shards)
    assert tuple(day for row in train for day in row.signal_dates) == manifest.split.train
    assert tuple(day for row in validation for day in row.signal_dates) == manifest.split.validation
    assert not any(day in manifest.split.test for row in manifest.shards for day in row.signal_dates)
    assert [row.shard_id for row in manifest.shards] == [
        *(f"TRAIN-{index:02d}" for index in range(1, 19)),
        *(f"VALIDATION-{index:02d}" for index in range(1, 7)),
    ]
```

再断言 dataclass 字段只含 schema、artifact_identity、input_fingerprint、split、split_identity、shard_size、shards、signal/evaluator/cost/runtime/source_deviation versions、test_outcomes_read、trade_permission，不含 held_codes、bars、数据库信息或观察明细。

- [ ] **Step 2: 运行测试并确认新模块不存在**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_shards.py -q`

Expected: FAIL，无法导入 `public_challenger_shards`。

- [ ] **Step 3: 实现严格领域模型与确定性身份**

```python
@dataclass(frozen=True)
class ResearchShardDefinition:
    segment: str
    shard_id: str
    signal_dates: tuple[date, ...]
    segment_dates: tuple[date, ...]
    segment_identity: str

@dataclass(frozen=True)
class PublicChallengerResearchManifest:
    schema: str
    artifact_identity: str
    input_fingerprint: str
    split: ChronologicalSplit
    split_identity: str
    shard_size: int
    shards: tuple[ResearchShardDefinition, ...]
    signal_version: str
    evaluator_version: str
    cost_version: str
    runtime_version: str
    source_deviation_version: str
    test_outcomes_read: bool = False
    trade_permission: str = "NO-TRADE"
```

`build_research_manifest()` 必须先调用现有研究输入校验，拒绝非 630 日、非 21 分片大小和任何非精确 378/126/126 切分；segment identity 对完整阶段日期做 canonical JSON SHA-256，manifest identity 对除自身 identity 外全部公开字段做 canonical JSON SHA-256。

- [ ] **Step 4: 运行分片领域测试**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_shards.py -q`

Expected: PASS，包括不同输入指纹产生不同 manifest identity、测试段无分片、错误 shard id 失败。

- [ ] **Step 5: 提交主清单领域模型**

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_shards.py stock-ai/tests/unit/test_public_challenger_shards.py
git commit -m "feat(stock-ai)：定义挑战者研究分片清单"
```

### Task 4: 分片计算与单体结果等价

**Files:**
- Modify: `stock_ai/buy_point_selection/public_challenger_shards.py`
- Modify: `tests/unit/test_public_challenger_shards.py`

**Interfaces:**
- Consumes: Task 2 的 `_segment_observations()` 与 `build_research_review_from_observations()`，Task 3 的 manifest。
- Produces: `PublicChallengerResearchShard`、`build_research_shard(*, manifest, inputs, shard_id, started_at, finished_at) -> PublicChallengerResearchShard`、`finalize_research_shards(manifest, shards) -> PublicChallengerResearchReview`。

- [ ] **Step 1: 写指纹、父链、跨段与合并等价失败测试**

```python
def test_finalize_matches_monolithic_fixture() -> None:
    inputs = _small_deterministic_runtime_fixture()
    manifest = build_research_manifest(inputs)
    shards = tuple(
        build_research_shard(
            manifest=manifest,
            inputs=inputs,
            shard_id=definition.shard_id,
            started_at=datetime(2026, 8, 24, 9, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 8, 24, 9, 1, tzinfo=timezone.utc),
        )
        for definition in manifest.shards
    )
    sharded = finalize_research_shards(manifest, shards)
    monolithic = build_public_challenger_research(inputs)
    assert sharded == monolithic
```

独立参数化测试必须覆盖：输入指纹变化、manifest 父身份不符、缺失、重复、额外 shard、日期重叠、日期顺序错误、观察 signal_date 不在 shard、resolution_date 越过完整阶段、任何 TEST segment，均抛出稳定的 `ValueError` 原因码。

- [ ] **Step 2: 运行新测试并确认接口缺失**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_shards.py -q`

Expected: FAIL，缺少 shard builder/finalizer。

- [ ] **Step 3: 实现分片计算、严格验证和纯内存汇总**

```python
@dataclass(frozen=True)
class PublicChallengerResearchShard:
    schema: str
    artifact_identity: str
    parent_manifest_identity: str
    input_fingerprint: str
    segment: str
    shard_id: str
    signal_dates: tuple[date, ...]
    segment_start: date
    segment_end: date
    segment_identity: str
    observations: tuple[ChallengerObservation, ...]
    funnel_counts: Mapping[str, int]
    started_at: datetime
    finished_at: datetime
    duration_seconds: Decimal
    test_outcomes_read: bool = False
    trade_permission: str = "NO-TRADE"
```

`build_research_shard()` 先重验 manifest identity、版本、inputs fingerprint 和完整 630 日历，再只对 definition.signal_dates 调用 `_segment_observations()`，完整 `definition.segment_dates` 只作为边界；duration 必须非负。`finalize_research_shards()` 只消费 manifest/shards，按 manifest 顺序合并 observations 和 Counter，拒绝所有结构偏差，最后调用共享 evaluator 构建函数，绝不接收 engine 或 loader。

- [ ] **Step 4: 运行领域与运行时回归**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_shards.py tests/unit/test_public_challenger_runtime.py -q`

Expected: PASS，且小 fixture 的分片与单体 review 完全相等。

- [ ] **Step 5: 提交分片计算与汇总**

```bash
git add stock-ai/stock_ai/buy_point_selection/public_challenger_shards.py stock-ai/tests/unit/test_public_challenger_shards.py
git commit -m "feat(stock-ai)：实现挑战者分片计算与汇总"
```

### Task 5: 严格分片产物、原子写入和恢复状态

**Files:**
- Create: `stock_ai/buy_point_selection/public_challenger_shard_report.py`
- Create: `tests/unit/test_public_challenger_shard_report.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 3/4 的 manifest、definition 和 shard dataclasses。
- Produces: `write_research_manifest()`、`load_research_manifest()`、`write_research_shard()`、`load_research_shard()`、`inspect_research_status()`、`ResearchShardStatus`；所有 path 参数和返回值使用 `pathlib.Path`。

- [ ] **Step 1: 写严格身份、幂等、冲突和临时文件恢复测试**

```python
def test_atomic_writer_is_idempotent_and_conflict_closed(tmp_path) -> None:
    manifest = _manifest()
    path = write_research_manifest(manifest, tmp_path)
    assert write_research_manifest(manifest, tmp_path) == path
    path.write_text('{"corrupt":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="IMMUTABLE_ARTIFACT_CONFLICT"):
        write_research_manifest(manifest, tmp_path)

def test_status_ignores_interrupted_temp_file(tmp_path) -> None:
    path = write_research_manifest(_manifest(), tmp_path)
    temp = path.parent / f".{path.name}.interrupted.tmp"
    temp.write_text("partial", encoding="utf-8")
    status = inspect_research_status(load_research_manifest(path), tmp_path)
    assert status.completed == 0
    assert status.missing == 24
    assert status.finalize_eligible is False
```

再覆盖 JSON 精确键集合、identity/filename/parent/version 重算、Decimal 有限值、日期顺序、观察 signal/trade 一致、敏感键递归拒绝、损坏/重复/冲突分类，以及 `duration_seconds > 600` 的 warning 状态。

- [ ] **Step 2: 运行产物测试并确认模块不存在**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_shard_report.py -q`

Expected: FAIL，无法导入 shard report。

- [ ] **Step 3: 实现 canonical JSON、完整观察编解码和原子不可变 writer**

```python
def _atomic_write_exclusive_or_verify(path: Path, serialized: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / f".{path.name}.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if path.exists():
            if path.read_bytes() != serialized:
                raise ValueError("IMMUTABLE_ARTIFACT_CONFLICT")
            return
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temp_path, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temp_path.unlink(missing_ok=True)
```

manifest 路径固定为 `manifests/public-short-term-challenger-manifest-{identity}.json`；分片路径固定为 `shards/{manifest_identity}/{shard_id}.json`。序列化显式列出 `ChallengerSignal`、`ChallengerTrade` 和 `ChallengerObservation` 的全部 dataclass 字段，不使用 `asdict()`；loader 使用精确键集合和内容哈希重算，拒绝未知字段。状态扫描只接受 manifest 中 24 个精确目标文件名，点前缀 lock/tmp 不算完成。

- [ ] **Step 4: 明确 Git 忽略并验证**

在 `stock-ai/.gitignore` 加入：

```gitignore
output/research/public_short_term_challenger/manifests/
output/research/public_short_term_challenger/shards/
```

Run: `cd stock-ai && mkdir -p output/research/public_short_term_challenger/shards/check && touch output/research/public_short_term_challenger/shards/check/TRAIN-01.json && git check-ignore output/research/public_short_term_challenger/shards/check/TRAIN-01.json`

Expected: 输出该分片路径。

- [ ] **Step 5: 运行产物与领域测试**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_shard_report.py tests/unit/test_public_challenger_shards.py -q`

Expected: PASS，包括相同 bytes 幂等、冲突不覆盖、临时文件不计完成、缺片不可 finalize。

- [ ] **Step 6: 提交不可变产物协议**

```bash
git add stock-ai/.gitignore stock-ai/stock_ai/buy_point_selection/public_challenger_shard_report.py stock-ai/tests/unit/test_public_challenger_shard_report.py
git commit -m "feat(stock-ai)：持久化不可变挑战者研究分片"
```

### Task 6: 四阶段 CLI 与旧 research 失败关闭

**Files:**
- Modify: `scripts/analysis/analyze_public_short_term_challenger.py`
- Modify: `tests/unit/test_analyze_public_short_term_challenger_cli.py`

**Interfaces:**
- Consumes: Task 3–5 的 prepare/build/load/status/finalize API，现有 `write_challenger_research()`。
- Produces: `StageResult(paths: tuple[Path, ...], output_lines: tuple[str, ...])`；CLI stages `research-prepare`、`research-shard`、`research-status`、`research-finalize`；原 `research` 返回安全错误；`freeze`/`test` 参数和行为不变。

- [ ] **Step 1: 写 parser 和 dispatch 失败测试**

```python
def test_parser_exposes_sharded_manual_stages() -> None:
    parser = module.build_parser()
    assert set(parser._subparsers._group_actions[0].choices) == {
        "research",
        "research-prepare",
        "research-shard",
        "research-status",
        "research-finalize",
        "freeze",
        "test",
    }

def test_status_and_finalize_never_load_mysql(tmp_path) -> None:
    manifest_path = _complete_shard_chain(tmp_path)
    status_args = module.build_parser().parse_args(
        ["research-status", "--manifest", str(manifest_path), "--output-dir", str(tmp_path)]
    )
    finalize_args = module.build_parser().parse_args(
        ["research-finalize", "--manifest", str(manifest_path), "--output-dir", str(tmp_path)]
    )
    status_result = module.dispatch_stage(status_args, _forbidden_loader, _forbidden_loader)
    finalize_result = module.dispatch_stage(finalize_args, _forbidden_loader, _forbidden_loader)
    status = json.loads(status_result.output_lines[0])
    assert status["finalize_eligible"] is True
    assert load_challenger_research(finalize_result.paths[0]).review.trade_permission == "NO-TRADE"
```

另写：prepare 恰好调用一次 loader；shard 每次都重载完整输入并重算 fingerprint，不一致失败；已存在合法 shard 在指纹验证后直接返回且不重复计算；缺片 finalize 失败；原 research 不调用 loader 并返回安全提示；freeze/test 原测试保持通过。

- [ ] **Step 2: 运行 CLI 测试并确认阶段集合失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_analyze_public_short_term_challenger_cli.py -q`

Expected: FAIL，parser 尚无四个新阶段。

- [ ] **Step 3: 实现参数和分支编排**

```python
prepare = stages.add_parser("research-prepare")
prepare.add_argument("--signal-start", type=_date, required=True)
prepare.add_argument("--signal-end", type=_date, required=True)
_add_output_dir(prepare)

for stage in ("research-shard", "research-status", "research-finalize"):
    parser = stages.add_parser(stage)
    parser.add_argument("--manifest", type=Path, required=True)
    _add_output_dir(parser)
stages.choices["research-shard"].add_argument("--shard-id", required=True)
```

定义 `@dataclass(frozen=True) class StageResult`，字段为 `paths: tuple[Path, ...]` 和 `output_lines: tuple[str, ...]`。`research-prepare` 加载一次完整输入并写 manifest；`research-shard` 重新加载完整输入并重算 fingerprint 后，合法已完成则返回现有路径，否则计时构建并写 shard；`research-status` 只返回稳定的一行 JSON 摘要；`research-finalize` load 24 片、纯内存汇总、调用现有聚合 writer。超过 600 秒把警告写入 stderr，但仍保留合法产物。原 `research` 在任何 loader 调用前抛 `USE_RESEARCH_SHARDED_WORKFLOW`。

将上述 shard 顺序修正为：load manifest 后始终按 manifest 首尾日期重新加载完整输入并校验 fingerprint；若目标分片已经存在，再严格 load 并核对父链后返回，只有不存在时才计时计算。所有分支返回 `StageResult`；`main()` 只打印 `output_lines`，产物阶段把路径字符串放入 output_lines，status 放入一行 canonical JSON，因此 dispatch 本身不直接打印。

- [ ] **Step 4: 运行 CLI、产物和既有 freeze/test 回归**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_analyze_public_short_term_challenger_cli.py tests/unit/test_public_challenger_shard_report.py tests/unit/test_public_challenger_report.py -q`

Expected: PASS；status/finalize 的 forbidden loader 未触发，原 freeze/test 测试不变。

- [ ] **Step 5: 提交 CLI**

```bash
git add stock-ai/scripts/analysis/analyze_public_short_term_challenger.py stock-ai/tests/unit/test_analyze_public_short_term_challenger_cli.py
git commit -m "feat(stock-ai)：接入挑战者分片研究命令"
```

### Task 7: 文档、全量验证与安全审计

**Files:**
- Modify: `docs/BUY_POINT_SELECTION_CAPABILITIES.md`
- Verify: all files from Tasks 1–6

**Interfaces:**
- Consumes: 完整四阶段 CLI。
- Produces: 可复制的手动操作说明和实现验收证据。

- [ ] **Step 1: 写明四阶段操作和恢复规则**

在能力文档加入四条完整命令，明确固定 21 日、18+6、status 字段、已完成分片不重算、输入变化重新 prepare、单片超时仅警告、finalize 不访问 MySQL，以及禁止执行 freeze/test。示例日期使用已知 630 日研究窗口 `2024-01-12` 至 `2026-08-20`，并注明真实运行前先确认数据库最新 630 日窗口。

- [ ] **Step 2: 运行公开挑战者完整单元测试**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_public_challenger_portfolio.py tests/unit/test_public_challenger_runtime.py tests/unit/test_public_challenger_shards.py tests/unit/test_public_challenger_shard_report.py tests/unit/test_public_challenger_report.py tests/unit/test_analyze_public_short_term_challenger_cli.py tests/unit/test_public_challenger_validation.py tests/unit/test_public_challenger_signals.py tests/unit/test_public_challenger_execution.py -q`

Expected: PASS，无 skipped、xfailed 或 failed。

- [ ] **Step 3: 运行静态和敏感信息检查**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m compileall -q stock_ai/buy_point_selection scripts/analysis/analyze_public_short_term_challenger.py`

Expected: exit 0。

Run: `cd stock-ai && mkdir -p output/research/public_short_term_challenger/manifests output/research/public_short_term_challenger/shards && rg -n "MYSQL_URL|password|account|holdings|positions|orders|个人决策" output/research/public_short_term_challenger/manifests output/research/public_short_term_challenger/shards`

Expected: exit 1 且无输出；测试生成的受控 fixture 不得包含这些键。

Run: `git diff --check`

Expected: exit 0。

- [ ] **Step 4: 提交文档与验收更新**

```bash
git add stock-ai/docs/BUY_POINT_SELECTION_CAPABILITIES.md
git commit -m "docs(stock-ai)：说明挑战者分片研究流程"
```

### Task 8: 真实链按片运行与最终聚合

**Files:**
- Create locally, Git ignored: `output/research/public_short_term_challenger/manifests/public-short-term-challenger-manifest-*.json`
- Create locally, Git ignored: `output/research/public_short_term_challenger/shards/*/*.json`
- Create locally, aggregate only: `output/research/public_short_term_challenger/public-short-term-challenger-research-*.json`

**Interfaces:**
- Consumes: Task 7 已验证 CLI、MySQL 只读数据源、现有 benchmark loader。
- Produces: 24 个 status 合法分片和一个 evaluator v2 聚合研究产物；不产生 freeze/test。

- [ ] **Step 1: 只读确认最新 630 个交易日窗口**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -c 'from scripts.analysis.analyze_public_short_term_challenger import _mysql_signal_dates; from datetime import date; values=_mysql_signal_dates(date(2020,1,1), date.today()); window=values[-630:]; assert len(window)==630; print(window[0].isoformat(), window[-1].isoformat())'`

Expected: 输出严格递增窗口的首尾日期；记录这两个实际值，不把数据库连接或持仓写入计划、日志或 Git。

- [ ] **Step 2: 用实际首尾日期 prepare 并立即检查 status**

Run:

```bash
cd stock-ai
read CHALLENGER_SIGNAL_START CHALLENGER_SIGNAL_END <<< "$(PYTHONPATH=. .venv/bin/python -c 'from scripts.analysis.analyze_public_short_term_challenger import _mysql_signal_dates; from datetime import date; values=_mysql_signal_dates(date(2020,1,1), date.today())[-630:]; assert len(values)==630; print(values[0].isoformat(), values[-1].isoformat())')"
CHALLENGER_MANIFEST="$(PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-prepare --signal-start "$CHALLENGER_SIGNAL_START" --signal-end "$CHALLENGER_SIGNAL_END")"
test -f "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
```

Expected: `completed=0`、`missing=24`、`invalid=0`、`conflicts=0`、`finalize_eligible=false`。

- [ ] **Step 3: 运行 TRAIN-01 并检查 status**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-01 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"`

Expected: `completed=1`，其余错误计数为 0；失败时停止，不运行下一片。

- [ ] **Step 4: 运行 TRAIN-02**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-02 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"`

- [ ] **Step 5: 运行 TRAIN-03**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-03 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"`

- [ ] **Step 6: 运行 TRAIN-04 至 TRAIN-06，每片单独执行并检查 status**

Run `TRAIN-04`: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-04 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"`

Run `TRAIN-05`: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-05 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"`

Run `TRAIN-06`: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-06 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"`

- [ ] **Step 7: 运行 TRAIN-07 至 TRAIN-12，每片单独执行并检查 status**

依次执行以下六条，不使用循环或并发；每条结束后 status 的 completed 必须只增加 1：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-07 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-08 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-09 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-10 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-11 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-12 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
```

- [ ] **Step 8: 运行 TRAIN-13 至 TRAIN-18，每片单独执行并检查 status**

依次执行以下六条，不使用循环或并发；`TRAIN-18` 完成后必须为 `completed=18`：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-13 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-14 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-15 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-16 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-17 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id TRAIN-18 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
```

- [ ] **Step 9: 运行 VALIDATION-01 至 VALIDATION-06，每片单独执行并检查 status**

依次执行以下六条，不使用循环或并发：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id VALIDATION-01 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id VALIDATION-02 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id VALIDATION-03 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id VALIDATION-04 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id VALIDATION-05 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-shard --manifest "$CHALLENGER_MANIFEST" --shard-id VALIDATION-06 && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST"
```

Expected: 每片 completed 恰好增加 1；最终 `completed=24`、`missing=0`、`invalid=0`、`conflicts=0`、`finalize_eligible=true`。单片超过 600 秒只 warning；任何 fingerprint 变化立即停止并重新 prepare。

- [ ] **Step 10: 在 24 片全部合法后 finalize**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-status --manifest "$CHALLENGER_MANIFEST" && PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py research-finalize --manifest "$CHALLENGER_MANIFEST"`

Expected: 生成 `public-short-term-challenger-research-{identity}.json`，loader 校验通过，schema 使用 evaluator v2，且 `test_outcomes_read=false`、`trade_permission=NO-TRADE`、`promotion_eligible=false`。

- [ ] **Step 11: 验证没有冻结或测试产物被创建**

Run: `cd stock-ai && find output/research/public_short_term_challenger -maxdepth 1 -type f \( -name '*freeze*' -o -name '*test*' \) -print`

Expected: 无新增输出；真实链到此停止，不执行 `freeze` 或 `test`。
