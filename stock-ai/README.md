# tushare-mcp

> **能力总览**：[docs/CAPABILITIES.md](docs/CAPABILITIES.md) · **文档索引**：[docs/README.md](docs/README.md)

## 数据入库（MySQL）

本目录提供三类数据入库方案：

### 方案 1：Tushare 全量日线同步（推荐✨）

**适用场景**：需要全市场股票的完整历史数据

- **特点**：
  - ✅ 免费（Tushare `daily` 接口，不需要积分）
  - ✅ **无需 stock_basic 接口**（避免 1 次/小时限制）
  - ✅ 数据完整（覆盖全部 A 股）
  - ✅ 效率极高（按日期批量拉取，7 天只需 7 次 API 调用）
  - ✅ 自动增量更新
  - ✅ 支持定时任务

详细文档：
- [Tushare 同步指南](docs/TUSHARE_SYNC_GUIDE.md)
- [无需 stock_basic 说明](docs/NO_STOCK_BASIC_GUIDE.md)

### 方案 2：东财接口（快速补齐特定股票）

**适用场景**：只需要少数几只股票的数据，或作为 Tushare 的补充

- **历史日线补齐**：`scripts/sync/ingest_eastmoney_daily_to_mysql.py`
- **盘中增量更新**：`scripts/sync/poll_eastmoney_intraday_to_mysql.py`
- **盘中快照**：`scripts/sync/poll_eastmoney_intraday_snapshot_to_mysql.py`

#### 快速开始（方案 1：Tushare，推荐）

```bash
# 1. 建表
mysql -u user -p database < sql/create_stock_daily_table.sql

# 2. 配置环境变量
export TUSHARE_TOKEN="your_token"
export MYSQL_URL="mysql+pymysql://user:pass@host/db"

# 3. 复制并编辑 .env（见 .env.example）
cp .env.example .env

# 4. 全量 / 增量同步（CLI 参数）
uv run python scripts/sync_tushare_daily_to_mysql.py --mode full --start-date 20200101
uv run python scripts/sync_tushare_daily_to_mysql.py --mode by_date --days 7

# 5. 日常更新（本机）
./run_sync_daily.sh

# 6. Docker 定时（工作日 17:00，MySQL 在宿主机时用 host.docker.internal）
# 见 docker/daily-sync/README.md
cd docker/daily-sync && docker compose up -d --build
```

**优势：**
- 无需 `stock_basic` 接口（避免 1 次/小时限制）
- 按日期批量拉取，效率极高
- 立即可用，无需等待

#### 方案 2 使用方法（东财接口）

##### 1) 建表

执行 `sql/create_stock_daily_table.sql` 创建 `stock_daily`（主键：`(ts_code, trade_date)`）。

##### 2) 先补历史（一次性）

使用东财接口拉取最近 N 条日线并入库：

```bash
MYSQL_URL="mysql+pymysql://user:pass@localhost:3306/stock_data" \
uv run python scripts/sync/ingest_eastmoney_daily_to_mysql.py
```

你也可以改脚本里的 `CODES` 或自行扩展参数化（当前脚本示例默认包含 `159218/159840`）。

##### 3) 盘中每分钟更新（常驻）

盘中东财“最新一根日线”会动态变化，本脚本会对同一天做 upsert，便于 `intraday_trade_signal` 使用 MySQL 历史做更稳定的盘中分析：

```bash
MYSQL_URL="mysql+pymysql://user:pass@localhost:3306/stock_data" \
uv run python scripts/sync/poll_eastmoney_intraday_to_mysql.py --codes 159218,159840 --interval 60
```

如果你想用 `cron`，可以用单次模式：

```bash
MYSQL_URL="mysql+pymysql://user:pass@localhost:3306/stock_data" \
uv run python scripts/sync/poll_eastmoney_intraday_to_mysql.py --codes 159218,159840 --once
```

##### 4) 盘中快照表（方案 A：每分钟留痕）

如果你希望保留盘中轨迹（而不是不断覆盖 `stock_daily` 当天数据），可以建表并启动快照轮询：

- 建表：`sql/create_stock_intraday_snapshot_table.sql`
- 脚本：`scripts/sync/poll_eastmoney_intraday_snapshot_to_mysql.py`

常驻轮询：

```bash
MYSQL_URL="mysql+pymysql://user:pass@localhost:3306/stock_data" \
uv run python scripts/sync/poll_eastmoney_intraday_snapshot_to_mysql.py --codes 159218,159840 --interval 60
```

cron 单次：

```bash
MYSQL_URL="mysql+pymysql://user:pass@localhost:3306/stock_data" \
uv run python scripts/sync/poll_eastmoney_intraday_snapshot_to_mysql.py --codes 159218,159840 --once
```

## 每日综合选股 + 收盘甄选战报（17:30 · launchd）

工作日 **17:30** 自动运行：**日线补缺 → 综合选股 Top5 → 东财 SOP → DeepSeek → 次日监控 → 收盘甄选战报 → 微信**（需已登录 [wechat-cursor-acp](../wechat-cursor-acp)）：

```bash
./scripts/install-daily-selection-launchd.sh   # 安装 launchd
./push_selection_wechat.sh                     # 手动：完整 17:30 流程
REPORT_ONLY=1 ./push_selection_wechat.sh       # 跳过选股/SOP，重生成战报并推送
FETCH_ONLY=1 ./push_daily_briefing_wechat.sh 17:30
DISABLE_SOP_TOP5=1 ./push_selection_wechat.sh  # 紧急跳过 SOP（改用轻量简评）
```

- **SOP 值得关注**（非持仓、`WATCH: 是` / 买入观察）→ 写入 `selection_watch_alerts.json`，**次日交易时段 5 分钟监控**（支撑/止损/目标/禁追高）
- 快速跳过 SOP：环境变量 `DISABLE_SOP_TOP5=1`（不推荐）

默认 `WECHAT_PUSH_BACKEND=wechat-acp`。请在 QClaw 中关闭 cron `daily_stock_selection_17:30`，避免重复推送。

## 每日战报（09 / 12 / 15 / 20 点 · launchd）

```bash
./scripts/install-daily-briefing-launchd.sh   # 安装 launchd（替代 QClaw cron）
FETCH_ONLY=1 ./push_daily_briefing_wechat.sh 15:00  # 仅生成不推送
./push_daily_briefing_wechat.sh 15:00             # 生成 + 推微信
```

战报内容：DeepSeek AI 综合解读 + 大盘 + 东财 7×24 + 国际 + 持仓。非交易日自动标注「休市简报」。

## 选股策略（盘后 / 研究）

17:30 默认 **综合选股**；其它单策略条件见 [docs/SELECTION_STRATEGIES.md](docs/SELECTION_STRATEGIES.md)。

```bash
# 综合选股（与 17:30 相同）
uv run python core_v2/stock_selection_combined.py

# 单策略示例
uv run python scripts/selection/stock_selection.py
uv run python scripts/selection/stock_selection_ma5.py
uv run python core_v3/stock_selection_five_factor_mysql.py
```

输出目录：`output/stock_selection_*.csv`

## 盘中监控（持仓 + 选股池 → 微信）

交易时段 **9:30–11:30 / 13:00–15:00** 每 5 分钟检查；**触发才推微信**（wechat-acp）。

```bash
./scripts/install-holdings-monitor-launchd.sh
uv run python -m scripts.monitor.monitor_holdings_alerts --force --push   # 试跑
```

规则：`investment-agent/config/holdings_alerts.json` + `selection_watch_alerts.json`（17:30 生成）。详见 [docs/CAPABILITIES.md](docs/CAPABILITIES.md) §5。

## 盘前总结（开盘前）

```bash
uv run python scripts/analysis/run_premarket_analysis.py
```

## 盘后总结（收盘后）

```bash
uv run python scripts/analysis/run_aftermarket_analysis.py
```

## 午盘分析（午间）

```bash
uv run python scripts/analysis/run_midday_analysis.py
```

## 在 Cursor 里启用 MCP（可选）

如果你想把 `tushare_mcp.py` 作为 Cursor 的 MCP 工具使用，参考：
- `docs/CURSOR_MCP_SETUP.md`
- `cursor-mcp.example.json`
