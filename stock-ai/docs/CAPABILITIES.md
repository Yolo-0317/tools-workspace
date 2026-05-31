# stock-ai 能力总览

> 工作目录：`/Users/yolo/dev/yolo/tools-workspace/stock-ai`  
> 投资 Agent：`investment-agent/`（决策纪律、持仓执行卡、微信对话上下文）  
> 本文档为**当前生产链路**的单一入口；细节见各子文档链接。

---

## 1. 架构一览

```text
数据层                策略 / 分析层              推送层
─────────            ─────────────            ────────
Tushare → MySQL      综合选股 Top5            wechat-acp
东财实时 / 盘中       东财 SOP + DeepSeek      （wechat-cursor-acp）
                     战报 + AI 解读
                     MCP 盘中 / 做T 信号
                     持仓 + 选股池监控
```

### 数据分层四档（审计口径）

Agent 排查「是否漏接 DB/OpenCLI」时，先对号入座；**只有第一档是 17:30 生产主链路**。

| 档位 | 含义 | 典型入口 / 产物 | 为何如此 |
|------|------|-----------------|----------|
| **① 主链路** | 该进 DB 的进 DB，该用 OpenCLI 的用 OpenCLI | Tushare sync → `stock_daily`；综合选股 → `selection_daily_results`；执行卡 sync → `portfolio_positions` / `alert_rules`；战报/SOP/监控现价 → `fetch_eastmoney_quotes.py` | 生产自动化单一真相源 |
| **② 不进 DB，用 OpenCLI** | 实时/页面型，抓完即用 | 现价、SOP 八维、7×24 快讯、战报指数/国际盘 | 变化快、结构杂，入库性价比低 |
| **③ 仍用文件（辅助）** | DB 已是主源，文件作备份或桥接 | 选股 CSV 备份；`sop_review_latest.json`（与 DB 双写，JSON 兜底）；监控去重 JSON | 人读备份 / 兼容桥接 |
| **④ 设计如此（不进 DB / 不用 OpenCLI）** | 既不当结构化数据源入库，也不靠浏览器抓东财 | 见下表 | 旁路、推理层或交付层，非行情主库 |

**④ 明细**

| 类型 | 路径 / 模块 | 说明 |
|------|-------------|------|
| 决策纪律（权威 Markdown） | `investment-agent/持仓执行卡.md`、`memory/trading-strategies.md` | 人改、可版本管理；MySQL 持仓/规则是 sync **副本** |
| MCP Tushare 直查 | `tushare_mcp.get_daily_data`、`analyze_and_suggest` | Cursor 临时查数；**只读不写** DB，不开 OpenCLI |
| LLM 推理层 | `deepseek_client.py`、MCP `deepseek_*` | 纯生成；输入可来自 DB/OpenCLI，本身不落库 |
| 微信推送 | `wechat_acp_push_text.py`、`wechat-cursor-acp` | 交付通道；token 在 `~/.wechat-acp/` |
| 研究 / 手动（非 launchd） | `core_v3/stock_selection_five_factor_mysql.py`（写 DB `strategy=five_factor` + CSV）、`deepseek_analyze_five_factor.py`、回测脚本 | 读 MySQL 或 CSV，产出 `output/` 报告 |
| 交付产物 | `output/*.md` / `*.txt`、`investment-agent/*_深度分析_*.md` | 给人看 / 推微信的结果文件，非配置库 |

**选股入库规则**：`selection_daily_results` 按 **`trade_date + strategy` 覆盖**（先删后插）；不同交易日或不同策略并存。生产默认读 `strategy=combined`。

**SOP 监控规则**：仅 `DECISION=买入观察/观察买入/小仓埋伏` 且 **非持仓** 写入次日监控；元数据 **MySQL `sop_review_items` 优先**，JSON 兜底。

**决策上下文（所有个股 AI 分析必带）**

| 优先级 | 来源 | 路径 |
|--------|------|------|
| 1 | 持仓执行卡 P0～P4 | `investment-agent/持仓执行卡.md` |
| 2 | 通用操盘策略 | `investment-agent/memory/trading-strategies.md`（qclaw 副本 fallback） |
| 3 | 个股东财 SOP | `investment-agent/docs/skills/eastmoney-browser-sop/` |

注入方式：

- Python：`from scripts.tools.decision_context import inject_decision_context`
- 或：`load_full_decision_context()`（`scripts/tools/holdings_context.py`）
- MCP：`tushare_mcp.py` 内 `_maybe_inject_decision_context()`（`SKIP_DECISION_CONTEXT=1` 可跳过）

**Agent Skill 权威副本**（与 `~/.codex/skills/` 不一致时以 repo 为准）：

- 东财 SOP：`investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md`
- 选股工作台：`investment-agent/docs/skills/stock-strategy-selector/SKILL.md`

---

## 2. 定时任务（统一调度）

> **权威文档**：[docs/SCHEDULING.md](SCHEDULING.md) — 设计原因、架构图、安装、日志、回滚。

**生产（2026-05-31 起）**：Docker `stock-ai-scheduler` 管 cron；OpenCLI/微信任务经本机 `host-jobs`（`:9876`）执行。

| 任务 | 调度 | 执行位置 | 入口 |
|------|------|----------|------|
| Tushare 日线同步 | 工作日 **17:00** | scheduler **容器内** | `run_sync_daily.sh` |
| 选股 + SOP + 战报 | 工作日 **17:30** | 本机 host-jobs | `push_selection_wechat.sh` |
| 每日战报 | **09 / 12 / 15 / 20:00** | 本机 | `push_daily_briefing_wechat.sh` |
| 持仓 + 选股池监控 | 工作日 **每 5 分钟** | 本机 | `push_holdings_monitor.sh`（9:30–11:30 / 13:00–15:00 生效） |

**安装**：`./scripts/install-stock-ai-scheduler.sh`（会停用旧 launchd 三个 plist，移除 `stock-daily-sync`）。

**仍用 launchd（非 cron）**：`com.user.stock-ai-host-jobs`、`docker-stacks`、`home-hub`、`wechat-cursor-acp`、DDNS/证书等 — 见 SCHEDULING.md §7。

**旧 launchd 安装脚本**（仅回滚）：`install-daily-selection-launchd.sh`、`install-daily-briefing-launchd.sh`、`install-holdings-monitor-launchd.sh`。

**手动试跑**

```bash
cd stock-ai
./push_selection_wechat.sh                      # 完整 17:30
REPORT_ONLY=1 ./push_selection_wechat.sh        # 跳过选股，仅战报+推送
FETCH_ONLY=1 ./push_daily_briefing_wechat.sh 15:00
uv run python -m scripts.monitor.monitor_holdings_alerts --force --push
```

**微信前置**（详见 [wechat-cursor-acp](../../wechat-cursor-acp/README.md)）：

| 项 | 说明 |
|----|------|
| 桥接 | `wechat-cursor-acp`（`npx wechat-acp` + `agent acp`） |
| 实例 | `WECHAT_ACP_INSTANCE=tools-workspace`（默认） |
| Token | `~/.wechat-acp/instances/tools-workspace/token.json`（扫码后生成） |
| 推送脚本 | `scripts/tools/wechat_acp_push_text.py` |
| 后端 | `WECHAT_PUSH_BACKEND=wechat-acp`（`qclaw` 为兼容） |
| 目标 | `WECHAT_TARGET`（`.env` 或 shell 导出） |
| 互斥 | 启动前停用 QClaw `openclaw-weixin`，避免 iLink 冲突 |

```bash
agent login
cd wechat-cursor-acp && cp -n .env.example .env && ./scripts/start.sh
```

---

## 3. 17:30 收盘甄选链路（主流程）

```text
push_selection_wechat.sh
  └─ run_selection_daily.sh
       ├─ ensure_daily_bars --sync-if-stale     # MySQL 落后则 Tushare by_date 补同步
       └─ daily_selection_report              # 综合选股 Top5 + 东财 SOP（默认）
  └─ selection_watchlist --sync                # SOP → MySQL selection_watch_picks + alert_rules
  └─ push_daily_briefing_wechat.sh 17:30       # 战报（含 Top5 段 + AI 解读）→ 微信
```

| 步骤 | 模块 | 输出 |
|------|------|------|
| 日线补缺 | `scripts/tools/ensure_daily_bars.py` | MySQL `stock_daily` 至期望交易日（17:00 后较稳） |
| 综合选股 | `core_v2/stock_selection_combined.py` | MySQL `selection_daily_results` + CSV 导出 |
| SOP 采集 | `scripts/tools/fetch_eastmoney_quotes.py` → `eastmoney_sop_extract.py` | OpenCLI 8 维度 → `output/sop_preliminary/YYYYMMDD/` |
| SOP + DeepSeek | `scripts/analysis/sop_review_top5_concurrent.py` | MySQL `sop_review_*` + `sop_review_latest.json` 双写 |
| 干净 AI 摘要 | `daily_selection_report.py` | `output/daily_selection_ai_latest.txt`（无 stderr 日志） |
| 次日监控 | `scripts/tools/selection_watchlist.py` | MySQL `selection_watch_picks` + `alert_rules`（source=selection） |
| 战报 | `scripts/tools/daily_briefing_report.py` | `output/daily_briefing_1730_latest.txt` |

**环境变量**

- `DISABLE_SOP_TOP5=1` — 跳过 SOP，改用轻量 DeepSeek 简评（不推荐）
- `SOP_WORKERS` — 已弃用（OpenCLI 单会话）；`DEEPSEEK_WORKERS` — 并发数（默认 3）
- `REPORT_ONLY=1` — 不重跑选股，仅战报+推送

**SOP 监控规则**：仅 `DECISION=买入观察/观察买入/小仓埋伏` 且 **非持仓** 写入次日监控；解析以 **DECISION 优先**（`scripts/tools/sop_watch_parse.py`）。

---

## 4. 每日战报（09 / 12 / 15 / 20）

| 模块 | 说明 |
|------|------|
| `scripts/tools/daily_briefing_report.py` | 大盘 + 东财 7×24 + 国际 + 持仓 + **【AI 综合解读】** |
| `scripts/tools/market_session.py` | 休市/非交易时段标注 |
| `scripts/tools/fetch_eastmoney_macro_news.py` | OpenCLI 抓东财 7×24 快讯 |
| `scripts/tools/wechat_format.py` | AI 解读分节排版、SOP 摘要去日志 |

**17:30 战报**额外包含：第五节 Top5 + `── SOP / AI 投资决策 ──`（读 `daily_selection_ai_latest.txt`）。

**AI 解读格式**（微信友好）：

```text
【AI 综合解读】

📊 大盘与外围
...

📰 国内要闻
· ...

📋 持仓关注点
· P0 ...

👀 选股观察
· ...
```

---

## 5. 盘中监控

| 能力 | 模块 | 规则来源 |
|------|------|----------|
| 持仓 P0～P4 | `scripts/monitor/monitor_holdings_alerts.py` | MySQL `alert_rules`（source=holdings，由执行卡 sync） |
| 选股池（SOP 观察） | 同上（合并读取） | MySQL `selection_watch_picks` + `alert_rules`（source=selection，`--sync` 写入） |

**改执行卡后同步**：`uv run python -m scripts.tools.sync_portfolio_from_card`

现价来源：东财行情页（OpenCLI Browser）。  
与 `持仓执行卡.md` 冲突时以执行卡为准。

---

## 6. 数据同步

| 能力 | 入口 | 说明 |
|------|------|------|
| Tushare 日线 → MySQL | `scripts/sync/sync_tushare_daily_to_mysql.py` | 主入口；`./run_sync_daily.sh` |
| 缺失自动补同步 | `scripts/tools/ensure_daily_bars.py` | 17:30 选股前；期望日规则见脚本 |
| 执行卡 → 持仓/监控 | `scripts/tools/sync_portfolio_from_card.py` | `portfolio_positions` / `portfolio_account` / `alert_rules` |
| 实时行情 / SOP | `scripts/tools/fetch_eastmoney_quotes.py` | OpenCLI；东财 HTTP 入库脚本已移除 |
| Docker 统一调度 | `docker/scheduler/` | sync 17:00 + 选股/战报/监控 cron；见 [SCHEDULING.md](SCHEDULING.md) |

详见 [TUSHARE_SYNC_GUIDE.md](TUSHARE_SYNC_GUIDE.md)。

**注意**：本机运行时 `MYSQL_URL` 中 `host.docker.internal` 会在 sync 脚本内替换为 `127.0.0.1`。

---

## 7. LLM 调用（DeepSeek API 或 Cursor auto）

统一封装：`scripts/tools/deepseek_client.py`（Cursor 实现见 `cursor_agent_client.py`）

| `LLM_BACKEND` | 说明 | 前置 |
|---------------|------|------|
| `deepseek`（**默认**） | DeepSeek API | `DEEPSEEK_API_KEY` |
| `cursor` | Cursor CLI `agent --model auto` | `agent login`，走订阅额度 |

| 函数 | deepseek 默认模型 | cursor 模型 | 典型调用方 |
|------|-------------------|-------------|------------|
| `call_deepseek(messages=…)` | `deepseek-v4-flash`（`DEEPSEEK_MODEL`） | `auto`（`CURSOR_AGENT_MODEL`） | 战报、SOP 汇总 |
| `call_deepseek_prompt(…)` | `deepseek-v4-flash`（`DEEPSEEK_MCP_MODEL`） | 同上 | MCP、持仓分析 |

Cursor 相关：`CURSOR_AGENT_WORKSPACE`（默认 `investment-agent`）、`CURSOR_AGENT_MODE=ask`（只读问答）、`CURSOR_AGENT_TIMEOUT_SECONDS`（默认 300）。

MCP 工具：`tushare_mcp.py` — `deepseek_trade_signal` 等。详见 [DEEPSEEK_USAGE.md](DEEPSEEK_USAGE.md)。

---

## 8. 选股策略（手动 / 研究）

| 策略 | 脚本 | 输出 |
|------|------|------|
| 综合选股（17:30 默认） | `core_v2/stock_selection_combined.py` | MySQL `selection_daily_results` + CSV 备份 |
| 五因子（v3） | `core_v3/stock_selection_five_factor_mysql.py` | MySQL `strategy=five_factor` + CSV 备份 |
| 量价突破 | `scripts/selection/stock_selection.py` | `stock_selection_*.csv` |
| MA5 回踩 | `scripts/selection/stock_selection_ma5.py` | `stock_selection_ma5_*.csv` |
| 底部突破 | `scripts/selection/stock_selection_bottom_breakout.py` | `stock_selection_bottom_breakout_*.csv` |

筛选条件详解见 [SELECTION_STRATEGIES.md](SELECTION_STRATEGIES.md)。

盘后 DeepSeek 审查（非 17:30 自动化路径）：见 [pipelines/daily_stock_deepseek_pipeline.md](pipelines/daily_stock_deepseek_pipeline.md)。

---

## 9. 分析与工具

| 能力 | 模块 |
|------|------|
| 换仓 / 试探仓执行表 | `scripts/tools/position_sizing.py`（CLI：`uv run python -m scripts.tools.position_sizing`） |
| 持仓 + 策略上下文 | `scripts/tools/holdings_context.py`（读 MySQL + 执行卡计划/红线） |
| 执行卡同步 MySQL | `scripts/tools/sync_portfolio_from_card.py` |
| 决策 prompt 注入 | `scripts/tools/decision_context.py` |
| 东财 SOP 单股 | `investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md` |
| 持仓 DeepSeek 整合 | `scripts/analysis/analyze_holdings_v2.py` |
| 五因子 DeepSeek 逐股 | `core_v3/deepseek_analyze_five_factor.py`（读 MySQL `five_factor` 优先） |
| 看板数据导出 | `scripts/tools/dashboard_data.py` |
| 微信推送 | `scripts/tools/wechat_acp_push_text.py` |

---

## 10. 关键配置文件

| 文件 | 用途 |
|------|------|
| `stock-ai/.env` | `MYSQL_URL`、`TUSHARE_TOKEN`、`DEEPSEEK_API_KEY` |
| `investment-agent/持仓执行卡.md` | 权威操作纪律（sync → MySQL） |
| `investment-agent/memory/trading-strategies.md` | 通用策略（版本管理） |
| MySQL `portfolio_positions` | 当前持仓（由执行卡同步） |
| MySQL `portfolio_account` | 账户快照 |
| MySQL `selection_daily_results` | 综合选股全量结果（Top5/SOP 主读源） |
| MySQL `selection_watch_picks` | 选股次日监控标的 |
| MySQL `alert_rules` | 盘中监控（holdings + selection） |
| MySQL `portfolio_account_daily` / `portfolio_positions_daily` | 看板：持仓每日快照 |
| MySQL `sop_review_daily` / `sop_review_items` | 看板：SOP 审查历史 |

---

## 11. MCP 工具（`tushare_mcp.py`）

Cursor 挂载见 [CURSOR_MCP_SETUP.md](CURSOR_MCP_SETUP.md)。DeepSeek 类工具自动注入决策上下文。

| 工具 | 用途 |
|------|------|
| `get_daily_data` | Tushare 日线查询（兼容官方参数） |
| `get_stock_daily_data` | 单股历史日线 |
| `analyze_and_suggest` | MA5/MA20 规则建议 |
| `realtime_trade_signal` | 东财日线 K + MA 规则信号 |
| `intraday_trade_signal` | MySQL 历史 + 东财盘中价 + MA 规则 |
| `deepseek_trade_signal` | 上者 + DeepSeek 买卖/观望（`deepseek-v4-flash`） |
| `deepseek_intraday_t_signal` | 盘中做 T + DeepSeek |

环境变量：`TUSHARE_TOKEN`、`MYSQL_URL`、`DEEPSEEK_API_KEY`。

---

## 12. 相关文档索引

| 文档 | 内容 |
|------|------|
| [README.md](README.md) | **文档索引** |
| [README.md](../README.md) | 快速开始、同步、选股、监控 |
| [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md) | 目录结构 |
| [pipelines/daily_stock_deepseek_pipeline.md](pipelines/daily_stock_deepseek_pipeline.md) | 日线→选股→DeepSeek 手动流水线 |
| [SELECTION_STRATEGIES.md](SELECTION_STRATEGIES.md) | 单策略筛选条件 |
| [DEEPSEEK_USAGE.md](DEEPSEEK_USAGE.md) | MCP DeepSeek 信号 |
| [TUSHARE_SYNC_GUIDE.md](TUSHARE_SYNC_GUIDE.md) | Tushare 同步 |
| [wechat-cursor-acp/README.md](../../wechat-cursor-acp/README.md) | 微信桥接 |
| [investment-agent/README.md](../investment-agent/README.md) | Agent 工作区 |
| [investment-agent/持仓执行卡.md](../investment-agent/持仓执行卡.md) | P0～P4 与红线 |
| [scripts/README.md](../scripts/README.md) | 脚本分目录 |

---

## 14. 看板入库（每日历史保留）

| 表 | 保留策略 | 自动写入时机 |
|----|----------|--------------|
| `portfolio_account_daily` | 按 `snapshot_date + slot` **覆盖**；不同日期累积 | 15:00 `midday`；17:30 `eod`；改卡 `sync` |
| `portfolio_positions_daily` | 同上 | 同上（含 OpenCLI 现价、盈亏） |
| `sop_review_daily` / `sop_review_items` | 按 `trade_date + strategy` **覆盖** | 17:30 SOP 完成后 |
| `selection_daily_results` | 按 `trade_date + strategy` 累积 | 已有 |
| `stock_daily` | 按交易日累积 | 已有 |

```bash
uv run python -m scripts.tools.dashboard_data snapshot-portfolio --slot eod
./scripts/tools/run_portfolio_snapshot.sh midday   # 15:00 战报后自动调用
uv run python -m scripts.tools.dashboard_data export -o output/dashboard.json
```

快照失败写入 `logs/snapshot_alerts.log`（不阻断战报/选股推送；`SNAPSHOT_STRICT=1` 时 shell 返回非零）。

**已删除遗留表**（2026-05-31）：`capital_flow`、`stock_intraday_snapshot`、`stock_orderbook_snapshot`（见 `006_drop_legacy_eastmoney_tables.sql`）。

---

## 13. 维护约定

- 新增自动化能力时：**先更新本文档**，再改 launchd / shell 入口。
- `output/`、`logs/`、`.env` 不入 git。
- 持仓/监控数据源为 MySQL；改执行卡后运行 `sync_portfolio_from_card`。
- 决策支持非投资建议；微信文案避免绝对买卖指令。
- 数据分层四档见 **§1 数据分层四档**；勿把 ④ 档旁路误判为「漏接 DB/OpenCLI」。

*最后更新：2026-05-30*
