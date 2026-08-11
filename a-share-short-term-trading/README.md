# A 股短线交易辅助系统

当前实现为 v1.1 第一阶段基础设施：严格数据契约、15 张 MySQL 业务表、完整券商事实、专用仓储层和最小权限运行账号。系统只响应聊天指令，不安装看板、定时刷新、推送任务或自动下单能力。

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

迁移按 `sql/001` 至 `sql/004` 顺序幂等执行。`004` 只为既有账户和持仓表补充缺失的券商事实列，不删除或重建原表。

## 券商持仓刷新

用户先在 Chrome 登录 `https://jywg.18.cn/Search/Position`，再通过聊天明确要求刷新。采集保存总持仓与可用持仓、成本、现价、市值、持仓盈亏、当日盈亏和券商采集时间；不保存完整账号、Cookie、密码或浏览器会话。

系统不会定时刷新持仓，也不会修改 `alert_rules`。未提供带时区的券商采集时间时，本轮数据会被拒绝，不使用估算时间补齐。

## 日线与交易诊断

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
