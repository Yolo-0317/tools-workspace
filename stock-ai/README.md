# tushare-mcp

> **能力总览**：[docs/CAPABILITIES.md](docs/CAPABILITIES.md) · **文档索引**：[docs/README.md](docs/README.md) · **统一调度**：[docs/SCHEDULING.md](docs/SCHEDULING.md)

## 数据入库（MySQL）

本目录提供两类数据能力：**Tushare 日线入库** + **OpenCLI 实时行情/SOP**。

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

### 实时行情与 SOP（OpenCLI）

**适用场景**：盘中现价、战报指数、SOP 多维数据、宏观快讯

- **统一入口**：`scripts/tools/fetch_eastmoney_quotes.py`（OpenCLI 浏览器）
- **宏观快讯**：`scripts/tools/fetch_eastmoney_macro_news.py`
- **日线历史**：仍用方案 1 Tushare → MySQL；盘中信号用 OpenCLI 现价 + MySQL 历史均线

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

# 6. Docker 统一调度（sync 17:00 + 选股/战报/监控，见 docs/SCHEDULING.md）
./scripts/install-stock-ai-scheduler.sh
```

**优势：**
- 无需 `stock_basic` 接口（避免 1 次/小时限制）
- 按日期批量拉取，效率极高
- 立即可用，无需等待

## 每日综合选股 + 收盘甄选战报（17:30 · scheduler → host-jobs）

工作日 **17:30** 由 Docker scheduler 触发本机 host-jobs：**日线补缺 → 综合选股 Top5 → 东财 SOP → DeepSeek → 次日监控 → 微信推送**（需 wechat-acp token 有效，见 [wechat-cursor-acp](../wechat-cursor-acp)）：

```bash
./scripts/install-stock-ai-scheduler.sh          # 安装统一调度（含 17:30）
curl -s -X POST http://127.0.0.1:9876/run/selection -H 'Content-Type: application/json' -d '{}'  # 手动
./push_selection_wechat.sh                       # 或直接跑脚本
REPORT_ONLY=1 ./push_selection_wechat.sh       # 跳过选股/SOP，仅推送已有产物
DISABLE_SOP_TOP5=1 ./push_selection_wechat.sh    # 紧急跳过 SOP（改用轻量简评）
```

- **SOP 值得关注**（非持仓、`WATCH: 是` / 买入观察）→ 写入 MySQL `selection_watch_picks` + `alert_rules`，**次日交易时段 5 分钟监控**（支撑/止损/目标/禁追高）
- 快速跳过 SOP：环境变量 `DISABLE_SOP_TOP5=1`（不推荐）

默认 `WECHAT_PUSH_BACKEND=wechat-acp`。请在 QClaw 中关闭 cron `daily_stock_selection_17:30`，避免重复推送。

## 快讯与 AI 解读（每 15 分钟 · launchd）

```bash
./sync_macro_news.sh    # 与 com.user.stock-macro-news-sync 相同
```

东财 7×24 落库 + AI 解读（看板 `/news`）。**09/12/15/20 战报微信推送已停用**；手动战报仍可用 `scripts/tools/daily_briefing_report.py`。

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
./scripts/install-stock-ai-scheduler.sh
curl -s -X POST http://127.0.0.1:9876/run/monitor -H 'Content-Type: application/json' -d '{}'
uv run python -m scripts.monitor.monitor_holdings_alerts --force --push
```

规则：MySQL `alert_rules`（持仓由 `sync_portfolio_from_card` 同步；选股由 17:30 `--sync` 写入）。详见 [docs/CAPABILITIES.md](docs/CAPABILITIES.md) §5。

**改执行卡后**：

```bash
uv run python -m scripts.tools.sync_portfolio_from_card
```

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
