# A 股短线交易辅助系统

当前实现包含 V1.3 买点优先选股：严格数据契约、点时行业/ST/公告风险、三类入场前结构、两日条件触发、五日退出模拟、不可覆盖计划事件和券商确认后的 3—5 日决策记忆。系统只响应聊天指令，不为该选股器安装定时刷新、推送任务或自动下单能力。

## 数据库管理

数据库管理与运行账号严格分离：

- `root` 只用于迁移和权限配置，密码从 `stock-ai/.env` 的 `MYSQL_ROOT_PASSWORD` 读取，不进入命令行、日志或 Git。
- `stt_app@%` 只用于 `stock_data` 的 `SELECT`、`INSERT`、`UPDATE`、`DELETE`，没有 `CREATE`、`DROP`、`ALTER`、`INDEX`。
- 运行连接继续使用 `stock-ai/.env` 的 `MYSQL_URL`。

所有管理脚本默认只展示计划；实际变更必须显式传入 `--apply`：

```bash
PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/apply_migrations.py

PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/apply_migrations.py --apply

PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/configure_mysql_permissions.py

PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/configure_mysql_permissions.py --apply
```

迁移按 `sql/001` 至 `sql/006` 顺序幂等执行。`004` 只为既有账户和持仓表补充缺失的券商事实列；`005` 为旧自动选股候选与计划增加 V1.2 字段；`006` 增加 V1.3 结构 ID、三层资格、计划状态、不可覆盖事件和手动前向运行账本。迁移不删除或重建业务表。投顾账本的 `stock-mysql/sql/016_buy_point_advisor_link.sql` 只新增可空的 `selection_plan_id`，需由数据库管理员显式应用。

## 券商持仓刷新

用户先在 Chrome 登录 `https://jywg.18.cn/Search/Position`，再通过聊天明确要求刷新。采集保存总持仓与可用持仓、成本、现价、市值、持仓盈亏、当日盈亏和券商采集时间；不保存完整账号、Cookie、密码或浏览器会话。

系统不会定时刷新持仓，也不会修改 `alert_rules`。未提供带时区的券商采集时间时，本轮数据会被拒绝，不使用估算时间补齐。

## 日线与交易诊断

### 手动买点优先选股

正式手动入口使用规则 `buy-point-selection-3.1.0`。它一次有界读取完整沪深主板日线面板，不从旧四轨候选池反推全市场；旧 `combined / ma5 / five_factor / bottom_breakout` 即使运行失败也不能阻塞新引擎，已有结果只进入影子研究。

新引擎只允许三类入场前结构：平台临界突破、强趋势缩量回踩、首次启动后的浅回踩。普通三连阳、连续加速、旧策略高分和事件利好不能独立取得交易资格。报告固定分为：

- `正式候选`：通过全部门禁的 0—3 只，可为 0；只有这一层显示最大股数。
- `准备中观察`：结构接近成立但缺少筹码、点时参考、账户或组合证据，固定无交易资格。
- `影子研究`：旧策略、未晋级的新计划和漏选复盘，最大股数为 0。
- `拒绝统计`：保留每条硬门槛的当日拒绝数量。

手动运行：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/select_short_term_candidates.py --output text
```

点时行业、ST/停牌和重大公告风险默认由巨潮资讯 + BaoStock 提供。普通选股不刷新参考数据，只读 MySQL 缓存；覆盖缺失即失败关闭正式资格。下面的同步命令是手动入口，不会安装定时任务：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2024-01-02 --end latest
```

Tushare 保留为显式回退；token 缺少行业、ST 或公告接口权限时预期失败，不会伪造完整覆盖：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2024-01-02 --end latest --provider tushare
```

选择器的 `--refresh-reference-data` 使用同一默认 provider；不传该参数时不会联网。

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/select_short_term_candidates.py \
  --refresh-reference-data --output text
```

收盘计划不代表已经成交。后两个交易日真实价格触及触发价才把条件状态记为 `TRIGGERED`；高开超过 3%、触发时相对信号收盘超过 5%、市场冻结、风险否决或结构跌破会取消。模拟触发不会开启持仓决策周期，只有券商事实确认持仓从 0 变为正数，且能匹配同代码的 V1.3 `TRIGGERED` 计划时，才把 `selection_plan_id` 和冻结触发计划写入新的 3—5 日周期。

3.1.0 的主要成功路径是：计划真实触发后最多跟踪五个交易日，在结构失效价之前先达到冻结的 2R 目标。系统同时保留未触发、先止损、到期盈利、到期亏损、到期持平、同日目标/止损歧义、MFE、MAE 和扣费后净收益。只有日线无法判断同日先后时，固定按先止损处理。

历史校准按“形态 × 市场状态 × 板块共振、形态 × 市场状态、形态”逐级回退，选择第一个不少于 30 笔已触发交易的样本组。候选先按扣费后净期望，再按 2R 成功率、先止损率和 63 日滚动稳定性排序。报告中的概率为该历史样本组的 95% Wilson 区间，只描述同类历史频率，不是对单只股票的精确预测或上涨保证。

历史研究采用按时间顺序的 60%/20%/20% 训练、验证和一次性冻结测试，至少需要 252/126/126 个交易日。研究数据准备后依次运行：

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --research-train-validation --trading-dates <dates.json> --observations <outcome-observations.json>

PYTHONPATH=stock-ai stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --freeze-profile --trading-dates <dates.json>

PYTHONPATH=stock-ai stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --run-test --write-artifact --trading-dates <dates.json> \
  --observations <outcome-observations.json>
```

`outcome-observations.json` 每行必须包含 `exit_date`、`setup_type`、`sector_code`、`net_return`、`net_pnl`、`outcome`、`market_status`、`sector_resonating`、`mfe` 和 `mae`。验证产物 schema 为 `buy-point-selection-validation-v2`。旧 v1 产物、缺少任一结果字段、空校准、规则版本或哈希不一致时统一失败关闭。

历史通过仍不足以切到 `LIVE`：还必须有至少 20 个不同手动前向日期、20 个已触发/取消/失效/过期的完整计划，并且完整性违规为 0。验证产物缺失、规则哈希不一致、样本不足或任何门槛失败时保持 `SHADOW`；旧负期望策略不作正式兜底。回测和输出都不构成盈利承诺。

#### V1.2 历史研究记录

以下内容仅保留旧 V1.2/2.1 实验的可复现结果，不再描述当前正式手动入口。旧规则继续作为影子基线，不得覆盖 V1.3 硬门禁：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/select_short_term_candidates.py --output text
```

盘前、盘中和午间只使用上一完整交易日；盘后必须确认当日日线已经完整入库；非交易日使用最近完整交易日。`--skip-lanes` 只用于人工重试或测试，复用同一分析日已经落库的完整四轨结果；缺少任意一轨会停止评分。

生产入口先读取 `stock-ai/config/short_term_selection_validation.json`。只有产物结构完整、数据截止日等于当前分析日、样本外门禁全部通过时，才启用 `short-term-selection-2.1.0`；产物缺失、损坏、过期或验收失败时均使用 `short-term-selection-2.0.0`。聊天报告会显示实际规则版本。

2.1 是高精度实验规则。在 2.0 形态基础上增加：

- Wilder ADX14，用于过滤趋势强度不足；
- RSI14，用于过滤弱动量和过热；
- ATR14/收盘价，用于限制异常低波动或高波动；
- 最近 20 日对数收盘趋势的 R² 与斜率，用于过滤锯齿或下行趋势；
- 全市场同一基准日的 20 日相对强度分位；
- 突破幅度、突破量比，或回踩前后五日量能收缩与止跌确认。

相对强度必须按全体有效沪深主板计算，不能只在四轨候选中排名。分析日和 20 个交易日前两端有效价格的覆盖率低于 95% 时，整次 2.1 失败关闭，不输出触发价。指标、日线或截面缺失时不补造数据，也不放宽阈值凑满候选。

候选状态分为：

- `EXECUTABLE`：价格计划、目标交易日筹码、市场状态和组合账户新鲜度均通过。
- `OBSERVE`：研究形态成立，但筹码、账户、组合审批或市场许可不完整，禁止据此开仓。

2.0 下，`ALLOW` 按正常风险预算计算，`LIMITED` 将风险预算和仓位上限减半并最多保留两只可执行候选，`FREEZE` 只保存最大股数为 0 的观察计划。若将来 2.1 通过验收，`LIMITED` 会比 2.0 更严格：所有 2.1 候选只保存观察计划，不新增风险许可；`FREEZE` 仍保存零股观察计划。账户快照日期早于分析日或缺少可用资金时不会猜测仓位。输出的触发价、入场上限、失效价和第一减仓价都是交易计划，不代表已下单；系统没有自动委托能力。

完成自动选股后，可直接诊断个股。盘中和午间在没有 `--plan-json` 时会自动读取数据库中最新、未过期的冻结计划：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/diagnose_stock.py --code 600060 --output text
```

技术执行代理回测固定使用 T 日及以前的数据生成信号。T+1 只有触及触发价且开盘未越过入场上限才成交；日内止损和止盈同时出现时按先止损处理，最多持有 5 个交易日。同股持仓期间不重复入场，退出后冷却 5 个交易日；组合最多同时两仓，每仓使用初始资金的 50%，买卖两侧默认各计 0.1% 佣金和 0.1% 滑点。组合回撤按每日现金加持仓市值计算。

回测不重建历史筹码、盘口、资金流或板块证据，因此固定标记为 `technical_execution_proxy`，不能表述为完整实盘回测。冻结验收命令为：

```bash
PYTHONPATH=stock-ai \
stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_short_term_trade.py \
  --start 2024-01-02 --end 2026-07-31 --output json \
  --write-validation stock-ai/config/short_term_selection_validation.json
```

2026-08-11 的冻结验收结果可重复复现，2.1 未晋级，当前生产规则仍为 2.0：

- 2.0 测试集 85 笔，胜率 27.06%，单笔期望 -1.7002%，组合最大回撤 73.73%。
- `STRICT_A` 验证集 95 笔，胜率 42.11%，单笔期望 -0.5191%；因期望为负不具备候选资格。
- `STRICT_B` 验证集 91 笔，胜率 41.76%，单笔期望 -0.4611%；因期望为负不具备候选资格。
- `STRICT_C` 验证集 60 笔，胜率 51.67%，单笔期望 0.4009%；虽然方向改善，但低于预先冻结的 75 笔总样本门槛，因此不得用测试集表现补选。
- 最终 `selected_profile` 为空，产物原因是 `NO_VALIDATION_PROFILE`。系统保留 2.1 代码与实验证据，但不会降低门槛、修改区间或自动启用。

该结果说明新增指标提高了部分配置的过滤精度，但尚未形成满足样本量和稳定性要求的可上线优势。回测不构成盈利承诺，也不会触发自动下单。

关键标的日线同步示例：

```bash
PYTHONPATH=a-share-short-term-trading \
stock-ai/.venv/bin/python a-share-short-term-trading/scripts/daily_bar_sync.py \
  --scope critical --codes 600000,688001 --target-date auto --output json
```

收盘诊断只生成 `NO_TRADE` 或 `WAIT_ENTRY`。个股诊断会自动读取或按需采集大盘状态：上证指数、深证成指、科创 50 的 MA20 关系，加上全市场广度、成交额比和盘中强势板块数量，共同生成 `ALLOW / LIMITED / FREEZE`。盘中只有冻结计划、行情证据、自动市场状态和组合风控全部通过时才会计算 `BUY_ALLOWED`；影子模式仍向聊天窗口输出不可执行的 `NO_TRADE` 主信号。任何流程都不会自动提交券商订单。

统一个股诊断入口会根据上海时区和 SSE 交易日历自动识别盘前、盘中、午间休市、盘后或非交易日，不接受手工指定时段。盘前和非交易日使用最近完整收盘数据；盘中可刷新行情与资金流；午间只读取已保存证据；盘后若今日完整日线尚未入库，会明确回退到最近完整收盘日。

静态诊断缺少目标交易日筹码时，会按需通过 OpenCLI 获取东财日 K 与换手率并计算一次 CYQ 估算快照，写入采集审计后重新诊断。该快照是成交与换手衰减模型的估算值，不是交易所披露的真实持仓成本；其有效性按最近完整交易日判断，不使用固定 24 小时过期。盘中和午间不会临时重算收盘筹码，也不会定时批量抓取。

默认是 `SHADOW`，且组合风控默认不放行，因此不会仅凭命令调用产生可执行买入信号。市场状态由系统自动取得，不接受普通运行参数人工升级：

```bash
PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/python a-share-short-term-trading/scripts/diagnose_stock.py \
  --code 600000
```

JSON 输出和关闭盘中实时采集：

```bash
PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/python a-share-short-term-trading/scripts/diagnose_stock.py \
  --code 600000 --output json --no-intraday-refresh
```

完全离线复现时可以同时关闭筹码补采：

```bash
PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/python a-share-short-term-trading/scripts/diagnose_stock.py \
  --code 600000 --output json --no-intraday-refresh --no-chip-refresh
```

只有同时提供已冻结的收盘计划、自动市场状态、组合风控放行和 `LIVE` 模式，盘中五项证据全部通过后才可能输出可执行的 `BUY_ALLOWED`。盘中状态以上一完整交易日为基准，只能维持或降级；市场核心证据缺失或超过 15 分钟时固定 `FREEZE`。`FREEZE` 禁止新增风险，但不会阻止已有持仓触发保护性 `REDUCE / EXIT`。`--at` 仅用于带时区的历史复现和测试，不用于手工选择交易时段。

## 验证

本地单元与回归测试不会连接 MySQL：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests stock-ai/tests/unit/test_jywg_portfolio_sync.py
```

家庭 MySQL 集成测试必须显式启用。业务对象和券商数据测试都在事务内回滚；权限测试只尝试一条预期失败的建表语句，并确认没有残留：

```bash
STT_MYSQL_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/integration
```
