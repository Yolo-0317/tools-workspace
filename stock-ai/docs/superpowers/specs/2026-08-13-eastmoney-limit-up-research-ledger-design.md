# 东财涨停研究账本设计

## 1. 背景与目标

当前系统已经具备东财涨停池、炸板池、跌停池的 OpenCLI 采集能力，也能在情绪周期中计算涨停家数、炸板率和连板高度。但现有落库只保存市场汇总和少量龙头观察项，无法逐日回答以下问题：

- 当天所有涨停、连板和炸板股票分别是谁；
- 某只次日涨停股前一日是否进入过任何选股通道；
- 未入选是因为排名不足、硬门槛拒绝、数据缺失，还是对应策略没有解释能力；
- 涨停样本在 T+1、T+3、T+5 的收益、回撤和连板演化如何；
- 新规则是否真正提高抓涨能力，同时保持正期望和可接受风险。

本设计新增一个与正式 Top5 隔离的研究账本。用户每天手动触发一次命令，完成东财全量题材池采集、MySQL 幂等入库、选股归因、历史标签回填和当日复盘报告。系统不安装任何定时任务。

## 2. 范围

### 2.1 本次包含

- 从东财 OpenCLI 获取指定交易日的涨停、炸板、跌停全量池。
- 从涨停池原始字段读取连板高度，形成首板和连板梯队。
- 保存采集运行、股票级池事实、策略归因和 T+1/T+3/T+5 标签。
- 对照当日 `selection_daily_results` 中所有已运行策略。
- 通过确定性解释器生成选中、排名不足、硬门槛拒绝和数据缺失原因。
- 输出 Markdown 与 JSON 复盘产物。
- 对已到达目标交易日的历史样本补充前向表现标签。

### 2.2 本次不包含

- 不安装 cron、launchd 或 Docker 调度。
- 不启用东财八维个股诊断；该能力继续标记为 AI 弃用和禁止使用。
- 不让大模型生成或覆盖漏选原因。
- 不自动修改策略参数、晋级凭证或正式 Top5 来源。
- 不把 MySQL/Tushare 推导的涨停结果伪装成东财原始池事实。
- 不在本次增加新的看板页面或公众号发布流程。

## 3. 方案选择

采用独立研究账本，不扩展 `emotion_cycle_daily` 和 `emotion_cycle_dragon_watch`。情绪周期表继续承担市场汇总和龙头观察职责；新表承担全量股票级事实、策略归因和跨日结果。

相较于扩展现有情绪表，独立账本能避免汇总口径与逐股样本混杂；相较于仅保存 JSON/CSV，它支持幂等重跑、跨日标签回填、SQL 聚合和后续训练/验证切分。

## 4. 手动入口

新增单一入口：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.analysis.sync_limit_up_research \
  --date 2026-08-13
```

`--date` 可省略，默认按交易日历解析最近已收盘交易日。默认命令依次执行：

1. 验证目标日期是已收盘交易日；
2. 通过 OpenCLI 获取东财涨停、炸板、跌停池；
3. 校验和标准化原始记录；
4. 更新运行审计，并在一个数据库事务中保存全量事实、归因和标签；
5. 对照当日所有已入库选股策略并生成归因；
6. 回填所有已经到达 T+1、T+3、T+5 的历史样本；
7. 生成当日复盘 Markdown 和机器可读 JSON。

命令返回非零状态表示采集、校验、入库或归因存在阻断性失败。成功但部分股票缺少非关键字段时返回零，并在运行记录与报告中披露缺失字段。

## 5. 数据模型

数据库迁移归属 `stock-mysql/sql/`，运行时读写接口归属 `stock-ai/scripts/tools/portfolio_db.py`。

### 5.1 `limit_up_research_runs`

每次手动调用保存一条运行审计记录：

- `run_id`：运行主键；
- `trade_date`：研究交易日；
- `status`：`STARTED|SUCCEEDED|FAILED`；
- `source`：固定为 `eastmoney-opencli-topic-pool`；
- `snapshot_hash`：三个原始池规范化后的内容哈希；
- `limit_up_count`、`exploded_count`、`limit_down_count`；
- `missing_fields_json`、`error_code`、`error_message`；
- `started_at`、`completed_at`、`raw_meta_json`。

每次调用都保留运行审计。`STARTED` 在业务事务外先写入；业务事务成功后更新为 `SUCCEEDED`，失败时使用独立短事务更新为 `FAILED`。相同交易日、相同 `snapshot_hash` 的成功快照不重复写股票事实，但仍保留本次调用记录。

### 5.2 `limit_up_research_pool`

保存东财股票级池事实，唯一键为 `(trade_date, pool_kind, ts_code)`：

- `pool_kind`：`LIMIT_UP|EXPLODED|LIMIT_DOWN`；
- `ts_code`、`name`；
- `pct_chg`、`amount_wan`；
- `board_height`，涨停池至少为 1；
- `main_theme`；
- 东财存在时保存 `first_seal_time`、`last_seal_time`、`reopen_count`、`seal_amount_wan`；
- `missing_fields_json`；
- `source_run_id`、`raw_json`、`created_at`、`updated_at`。

重跑采用 upsert：同一交易日、池类型和股票只有一条当前事实，`source_run_id` 指向最近成功快照。无法从东财取到的字段必须记入 `missing_fields_json`，不得以零值表示负面事实。

### 5.3 `limit_up_selection_attribution`

唯一键为 `(trade_date, ts_code, strategy)`，保存涨停池股票与当日每个已运行策略的关系：

- `selected`、`rank_no`、`score`、`action`；
- `attribution`：`SELECTED|RANKED_OUT|HARD_REJECTED|DATA_MISSING|EXPLAINER_UNAVAILABLE|STRATEGY_NOT_RUN`；
- `first_reason_code`；
- `reason_codes_json`、`evidence_json`；
- `rule_version`、`source_run_id`、`created_at`、`updated_at`。

归因只允许来自版本化的确定性解释器。解释器必须返回稳定原因码和当时可验证的证据值。无法解释的旧策略明确记录 `EXPLAINER_UNAVAILABLE`，不能由 AI 补写看似合理的原因。

首期为当前生产策略建立适配器：`short_term_trade`、`combined`、`five_factor`、`ma5`、`watch`、`bottom_breakout` 和 `limit_up_gene_watch`。如果某策略当日没有任何入库结果且无法证明任务已运行，记录 `STRATEGY_NOT_RUN`，不能误判为硬拒绝。

### 5.4 `limit_up_forward_labels`

唯一键为 `(signal_date, ts_code, horizon)`，其中 `horizon` 为 `T1|T3|T5`：

- `outcome_date`；
- `signal_close`、`outcome_close`、`close_return_pct`；
- 区间 `max_return_pct`、`max_drawdown_pct`；
- `closed_limit_up`、`board_height`；
- `data_complete`、`missing_fields_json`；
- `label_version`、`created_at`、`updated_at`。

交易日映射以 MySQL 交易日序列为准，不按自然日推算。停牌或日线缺失时 `data_complete=false`，不向前偷换其他日期。标签可幂等重算，但必须保存 `label_version`。

## 6. 采集和校验

采集复用现有 `fetch_emotion_topic_pools_opencli()`，但在研究流水线中增加严格校验：

- 三个池的响应都必须是列表；
- 股票代码必须可规范为六位 A 股代码；
- 涨停池的连板高度不得小于 1；
- 同一股票同一池重复时按规范化内容去重并记录告警；
- 池为空不是自动成功。只有东财明确返回有效空池结构且市场数据证明目标日有效时，才允许作为空池保存；否则标记采集失败；
- 原始 payload 必须原样进入 `raw_json`；
- 目标日尚未收盘、非交易日或东财返回日期不匹配时拒绝写入成功快照。

东财采集失败时，运行记录写入 `FAILED`，不修改该交易日已有的成功事实，也不使用 MySQL 推导结果代替东财事实。

## 7. 策略归因

归因分两层执行：

### 7.1 持久化结果对照

先读取目标日各策略的 `selection_daily_results`：

- 股票存在且在策略正式保留名额内：`SELECTED`；
- 股票存在于完整候选但未进入该策略保留名额：`RANKED_OUT`；
- 当日没有策略运行证据：`STRATEGY_NOT_RUN`。

排名判断只使用当日已经持久化的排名和分数，不能用今天的代码重新排序过去的数据。

### 7.2 确定性解释器

对于未出现在候选结果中的股票，使用该策略版本对应的 explain 适配器，在严格截止到目标日的数据上重放门槛。解释器输出：

- 是否数据齐全；
- 按真实执行顺序排列的原因码；
- 第一个阻断原因；
- 每个原因对应的阈值、实际值和数据截止时间；
- 解释器和策略规则版本。

禁止将自然语言模型输出作为原因码或证据。若当前策略无法安全重放，则记录 `EXPLAINER_UNAVAILABLE`，同时把缺口列入报告，后续再为该策略补解释器。

## 8. 前向标签与防泄漏

- T 日事实、归因和规则版本在 T 日快照中固定。
- T+1/T+3/T+5 标签只能在对应交易日行情完整入库后生成。
- 回填只更新标签表，不回写 T 日归因、分数或原因。
- 训练、验证、测试按 `signal_date` 切分，不能按 `outcome_date` 混切。
- 每次策略研究必须报告样本覆盖率、缺失率和各原因码分布。
- 正式晋级仍使用独立的样本外验证凭证；研究账本本身无晋级权限。

## 9. 报告

每次成功运行生成：

- `output/research/limit_up/YYYY-MM-DD.md`；
- `output/research/limit_up/YYYY-MM-DD.json`。

报告至少包含：

- 涨停、首板、二板及以上、炸板、跌停数量；
- 连板高度梯队和主要题材分布；
- 当日各策略覆盖率；
- 涨停股逐只归因；
- 已完成的 T+1/T+3/T+5 标签回填数量；
- 按原因码聚合的漏选排行；
- 数据源、数据截止、缺失字段和运行 ID。

报告是研究产物，不生成买入动作，不写入个人投顾决策账本，也不改变持仓。

## 10. 错误处理与幂等

- OpenCLI 或东财失败：记录失败运行，保留旧成功快照，退出非零。
- MySQL 业务事务失败：事实、归因和标签全部回滚；随后用独立短事务把运行状态更新为失败。若连失败状态都无法写入，命令仍以非零退出并在本地错误输出中保留 `run_id`。
- 选股策略未运行：保存 `STRATEGY_NOT_RUN`，整次采集仍可成功。
- 解释器失败：该策略归因保存 `EXPLAINER_UNAVAILABLE` 和错误码，不阻断其他策略。
- 标签行情未到期：跳过，不视为失败。
- 标签到期但行情缺失：保存不完整标签并披露缺失，不伪造收益。
- 重复运行：事实、归因和标签按唯一键 upsert；运行审计追加，报告原子替换。

## 11. 测试与验收

### 11.1 单元测试

- 东财三类池的正常、空、重复、缺字段和错误日期标准化。
- 连板高度、板块、金额和封板字段映射。
- snapshot hash 稳定性和重复运行幂等。
- 六类归因状态及原因顺序。
- explain 适配器只读取目标日及以前数据。
- T+1/T+3/T+5 交易日映射、停牌和缺行情处理。
- 研究账本不能改变 `wechat_top5_strategies()`。
- 东财八维诊断模块不能被研究入口导入或调用。

### 11.2 MySQL 集成测试

- 迁移可重复执行。
- 成功快照全量写入四张表。
- 同日同 payload 重跑不重复股票事实和标签。
- 失败重跑不覆盖既有成功事实。
- 事务异常不留下半套数据。

### 11.3 手动验收

选择一个东财可查询的历史交易日执行完整命令，核对：

- 东财页面池数量与 MySQL 股票事实数量一致；
- 连板梯队与东财字段一致；
- 当日已入库选股结果能够正确匹配；
- 至少抽查一只 `SELECTED`、一只 `HARD_REJECTED` 和一只 `EXPLAINER_UNAVAILABLE`；
- 已到期样本生成正确的 T+1/T+3/T+5 标签；
- 最终 Top5 策略列表和运行前完全一致。

## 12. 实施边界

实现分为数据库迁移、纯领域模型、持久化接口、归因适配器、手动 CLI、报告和验证七个小步骤。每一步采用测试先行，并保留工作区内与本任务无关的改动。数据库连接、OpenCLI 实采和迁移应用均在需要时单独请求权限。
