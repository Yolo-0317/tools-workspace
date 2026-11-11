# 公开短线挑战者分片研究设计

## 目标

把公开短线挑战者一次超过一小时且中断后无法复用进度的 `research`，拆成可独立运行、不可变落盘、可校验恢复的任务。单个计算分片固定覆盖 21 个信号交易日，目标运行时间不超过约 10 分钟；实际耗时由产物记录，超出目标时不得静默改变研究口径。

本设计只拆分训练与验证研究，不读取测试结果，不执行 `freeze` 或一次性 `test`，也不让挑战者获得正式选股资格。

## 根因与边界

当前 `research` 先一次性加载 630 日完整输入，再顺序计算 378 日训练段和 126 日验证段，最后才写聚合 JSON。任何中断都会丢失已经完成的内存计算。

中断堆栈还显示 `_active_veto()` 在候选循环中反复遍历完整 `risk_flags` 并重复标准化代码。这是已观察到的性能热点，应先按代码建立索引消除重复扫描；但本设计不假定这一项能把全量任务缩短到可接受范围，因此仍实现可恢复分片。

## 阶段

### 1. `research-prepare`

输入完整 630 个确认交易日，加载与当前真实研究相同的 MySQL、基准指数、点时行业、风险覆盖、市场状态和持仓过滤输入，并生成主清单。

主清单只保存：

- schema、内容身份和输入指纹；
- 信号、评估器、成本、运行时和来源偏离版本；
- 630 日交易日历与 378/126/126 切分；
- 固定 `shard_size=21`；
- 18 个训练分片和 6 个验证分片的编号、日期范围与预期日期列表；
- `test_outcomes_read=false`、`trade_permission=NO-TRADE`。

主清单不保存持仓代码、股票观察明细、数据库地址、账号、密码或完整连接串。输入指纹仍覆盖真实持仓过滤等完整输入，使持仓或数据变化后旧分片不能混入新运行。

### 2. `research-shard`

命令接受一个严格主清单和一个 `shard_id`。每次重新加载同一完整输入并重算输入指纹，只有与主清单一致才开始计算。

训练段 378 日拆成 18 片，验证段 126 日拆成 6 片，每片恰好 21 个信号交易日。测试段不生成分片。

分片计算必须同时接收：

- 当前分片的 21 个待处理信号日；
- 所属完整阶段的全部交易日。

是否跨阶段的判断使用完整训练或验证日历，不能使用 21 日分片边界。因此分片最后若干信号日只要能在所属完整阶段内完成五日持有结果，就必须正常计算；只有真正跨入下一个阶段才记为 `OUTCOME_CROSSES_SEGMENT`。

每个分片保存：

- schema、内容身份、父主清单身份、输入指纹；
- segment、shard_id、21 个信号日期；
- 完整阶段起止与阶段身份；
- 逐笔 `ChallengerObservation` 研究明细；
- 漏斗计数；
- 开始、结束与耗时秒数；
- `test_outcomes_read=false`、`trade_permission=NO-TRADE`。

逐笔明细可包含研究股票代码、行业、信号与已结算收益，只能保存在 Git 忽略的本地受控目录。不得包含持仓列表、账户、凭据、订单或个人决策记忆。

### 3. `research-status`

状态命令只读主清单和分片目录，输出：

- 24 个预期分片中已完成、缺失、无效和冲突的数量；
- 每个分片的阶段、日期、耗时和身份；
- 是否具备 finalize 资格。

状态命令不得加载市场结果、修改分片或自动补跑。

### 4. `research-finalize`

汇总前必须严格验证：

- 主清单身份、输入指纹和版本均匹配；
- 恰好存在 18 个训练分片与 6 个验证分片；
- 分片日期与主清单完全一致，无缺口、重叠、额外日期或顺序错误；
- 每个分片内容身份、父身份和阶段身份可重算；
- 没有测试分片或测试结果字段；
- 观察明细的信号日和结果日没有越过所属阶段。

汇总器合并训练与验证观察和漏斗，沿用 evaluator v2 的三轨指标、执行轨 validation assessment 和聚合报告 writer。最终 JSON 仍只保存聚合指标，不包含股票代码明细，并保持：

```text
test_outcomes_read=false
trade_permission=NO-TRADE
promotion_eligible=false
```

## 性能修复

在 `_segment_observations()` 进入日期循环前，将 `risk_flags` 一次性规范化为按六位股票代码索引的不可变映射。`qualify_track_signals()` 对当前信号只接收该代码的风险标记子集，结果语义必须与完整顺序扫描一致。

该优化必须先用等价性测试证明：同一组乱序、带市场前缀、跨有效期的风险标记，在索引前后产生相同 `POINT_IN_TIME_RISK_VETO` 结论。

## 不可变与恢复语义

- 主清单和分片均使用内容哈希身份。
- 写入采用同目录临时文件、刷新并原子改名；中断时临时文件不具备合法身份。
- 同一路径相同字节为幂等成功；同一路径不同内容失败关闭。
- 已完成分片不会自动重算。
- 输入指纹变化时必须重新运行 `research-prepare`，不得把旧分片改挂到新主清单。
- `research-finalize` 不访问 MySQL；缺少任何分片即失败关闭。

## CLI

现有 `freeze` 和 `test` 语义不变。新增手动阶段：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py \
  research-prepare --signal-start YYYY-MM-DD --signal-end YYYY-MM-DD

PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py \
  research-shard --manifest <manifest.json> --shard-id TRAIN-01

PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py \
  research-status --manifest <manifest.json>

PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_public_short_term_challenger.py \
  research-finalize --manifest <manifest.json>
```

原 `research` 在分片链完成后改为安全提示，禁止继续触发不可恢复的单进程全量计算；不提供绕过分片链的隐藏参数。

## 错误处理

以下情况失败关闭且不覆盖任何合法产物：

- 交易日不是恰好 630 日；
- 分片大小、日期或阶段与主清单不一致；
- 当前输入指纹与主清单不同；
- 分片缺失、重复、冲突或身份损坏；
- 观察结果越过训练/验证边界；
- 任何测试段结果进入主清单、分片或 finalize；
- 临时文件无法原子提交；
- 单片耗时超过 10 分钟只记录并报警，不自动缩短日期或改变规则。

## 测试与验收

实施采用 TDD，并至少证明：

1. 630 日确定性生成 18 个训练分片和 6 个验证分片，每片 21 日；
2. 测试段不产生分片；
3. 分片尾部结果按完整阶段边界判断，不按 21 日边界误删；
4. 风险标记索引与原顺序扫描结果等价；
5. 主清单、分片和 finalize 严格验证身份及父链；
6. 中断临时文件不会被 status 或 finalize 视为完成；
7. 缺失、重复、冲突、跨段或输入指纹变化均失败关闭；
8. 相同分片重跑字节幂等；
9. 分片合并结果与同一小型 fixture 的单体研究结果完全一致；
10. 公开挑战者完整单元测试通过；
11. 手动逐片真实运行后，24 个分片均可被 status 验证，finalize 生成 evaluator v2 聚合研究产物；
12. 真实链全程不执行 `freeze` 或一次性 `test`。
