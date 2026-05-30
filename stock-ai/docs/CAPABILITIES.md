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

## 2. 定时任务（launchd）

| Label | 安装脚本 | 调度 | 入口 | 说明 |
|-------|----------|------|------|------|
| `com.user.stock-ai-daily-selection` | `scripts/install-daily-selection-launchd.sh` | 周一至五 **17:30** | `push_selection_wechat.sh` | 选股 + SOP + 日线补缺 + 次日监控 + **收盘甄选战报** → 微信 |
| `com.user.stock-ai-daily-briefing` | `scripts/install-daily-briefing-launchd.sh` | 每天 **09/12/15/20:00** | `push_daily_briefing_wechat.sh` | 盘中/收盘/晚间战报 → 微信 |
| `com.user.stock-holdings-monitor` | `scripts/install-holdings-monitor-launchd.sh` | 每 **5 分钟** | `push_holdings_monitor.sh` | 脚本内仅 **9:30–11:30 / 13:00–15:00** 生效；触发才推微信 |
| `com.user.stock-watch-reminder-*` | `scripts/install-stock-watch-reminder-launchd.sh` | 一次性 | `push_stock_watch_reminder_wechat.sh` | 特定日期提醒（按需） |

Plist 源文件：`tools-workspace/launchd/`。

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
  └─ selection_watchlist --sync                # SOP → selection_watch_alerts.json
  └─ push_daily_briefing_wechat.sh 17:30       # 战报（含 Top5 段 + AI 解读）→ 微信
```

| 步骤 | 模块 | 输出 |
|------|------|------|
| 日线补缺 | `scripts/tools/ensure_daily_bars.py` | MySQL `stock_daily` 至期望交易日（17:00 后较稳） |
| 综合选股 | `core_v2/stock_selection_combined.py` | `output/stock_selection_combined_YYYYMMDD.csv` |
| SOP 采集 | `scripts/analysis/eastmoney_sop_extract.py` | `output/sop_preliminary/YYYYMMDD/{code}_初步报告_SOP版.md` |
| SOP + DeepSeek | `scripts/analysis/sop_review_top5_concurrent.py` | `output/stock_selection_combined_*_sop_review.md`、`sop_review_latest.json` |
| 干净 AI 摘要 | `daily_selection_report.py` | `output/daily_selection_ai_latest.txt`（无 stderr 日志） |
| 次日监控 | `scripts/tools/selection_watchlist.py` | `investment-agent/config/selection_watch_alerts.json` |
| 战报 | `scripts/tools/daily_briefing_report.py` | `output/daily_briefing_1730_latest.txt` |

**环境变量**

- `DISABLE_SOP_TOP5=1` — 跳过 SOP，改用轻量 DeepSeek 简评（不推荐）
- `SOP_WORKERS` / `DEEPSEEK_WORKERS` — 并发数（默认 3）
- `REPORT_ONLY=1` — 不重跑选股，仅战报+推送

**SOP 监控规则**：仅 `DECISION=买入观察/观察买入/小仓埋伏` 且 **非持仓** 写入次日监控；解析以 **DECISION 优先**（`scripts/tools/sop_watch_parse.py`）。

---

## 4. 每日战报（09 / 12 / 15 / 20）

| 模块 | 说明 |
|------|------|
| `scripts/tools/daily_briefing_report.py` | 大盘 + 东财 7×24 + 国际 + 持仓 + **【AI 综合解读】** |
| `scripts/tools/market_session.py` | 休市/非交易时段标注 |
| `scripts/tools/fetch_eastmoney_macro_news.py` | Playwright 抓东财快讯 |
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

| 能力 | 模块 | 规则文件 |
|------|------|----------|
| 持仓 P0～P4 | `scripts/monitor/monitor_holdings_alerts.py` | `investment-agent/config/holdings_alerts.json` |
| 选股池（SOP 观察） | 同上（合并读取） | `investment-agent/config/selection_watch_alerts.json`（运行时生成，不入 git） |

现价来源：东财行情页（OpenCLI Browser）。  
与 `持仓执行卡.md` 冲突时以执行卡为准。

---

## 6. 数据同步

| 能力 | 入口 | 说明 |
|------|------|------|
| Tushare 日线 → MySQL | `scripts/sync/sync_tushare_daily_to_mysql.py` | 主入口；`./run_sync_daily.sh` |
| 缺失自动补同步 | `scripts/tools/ensure_daily_bars.py` | 17:30 选股前；期望日规则见脚本 |
| 东财历史补齐 | `scripts/sync/ingest_eastmoney_daily_to_mysql.py` | 少数标的快速补齐 |
| 东财盘中更新 | `scripts/sync/poll_eastmoney_intraday_to_mysql.py` | 盘中 upsert 当日 K 线 |
| Docker 定时同步 | `docker/daily-sync/` | 工作日 17:00（可选） |

详见 [TUSHARE_SYNC_GUIDE.md](TUSHARE_SYNC_GUIDE.md)。

**注意**：本机运行时 `MYSQL_URL` 中 `host.docker.internal` 会在 sync 脚本内替换为 `127.0.0.1`。

---

## 7. DeepSeek 调用

统一封装：`scripts/tools/deepseek_client.py`

| 函数 | 默认模型 | 环境变量 | 典型调用方 |
|------|----------|----------|------------|
| `call_deepseek(messages=…)` | `deepseek-chat` | `DEEPSEEK_MODEL` | 战报、SOP 汇总、选股简评 |
| `call_deepseek_prompt(prompt=…)` | `deepseek-v4-flash` | `DEEPSEEK_MCP_MODEL` | MCP、持仓深度分析 |

公共环境变量：`DEEPSEEK_API_KEY`（必需）、`DEEPSEEK_MAX_TOKENS`、`DEEPSEEK_RETRIES`、`DEEPSEEK_CONTINUE_ON_LENGTH` 等。

MCP 工具（Cursor）：`tushare_mcp.py` — `deepseek_trade_signal`、`deepseek_intraday_t_signal`、盘前/盘后分析等。详见 [DEEPSEEK_USAGE.md](DEEPSEEK_USAGE.md)。

---

## 8. 选股策略（手动 / 研究）

| 策略 | 脚本 | 输出 |
|------|------|------|
| 综合选股（17:30 默认） | `core_v2/stock_selection_combined.py` | `stock_selection_combined_*.csv` |
| 五因子（v3） | `core_v3/stock_selection_five_factor_mysql.py` | `stock_selection_five_factor_*.csv` |
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
| 持仓 + 策略上下文 | `scripts/tools/holdings_context.py` |
| 决策 prompt 注入 | `scripts/tools/decision_context.py` |
| 东财 SOP 单股 | `investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md` |
| 持仓 DeepSeek 整合 | `scripts/analysis/analyze_holdings_v2.py` |
| 五因子 DeepSeek 逐股 | `core_v3/deepseek_analyze_five_factor.py` |
| 微信推送 | `scripts/tools/wechat_acp_push_text.py` |

---

## 10. 关键配置文件

| 文件 | 用途 |
|------|------|
| `stock-ai/.env` | `MYSQL_URL`、`TUSHARE_TOKEN`、`DEEPSEEK_API_KEY` |
| `investment-agent/持仓执行卡.md` | 权威操作纪律 |
| `investment-agent/memory/trading-strategies.md` | 通用策略（版本管理） |
| `investment-agent/config/holdings_alerts.json` | 持仓监控规则 |
| `investment-agent/config/selection_watch_alerts.json` | 选股次日监控（自动生成） |
| `holdings/current.csv` | 持仓 CSV（`investment-agent/holdings.csv` 链到此） |

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

## 13. 维护约定

- 新增自动化能力时：**先更新本文档**，再改 launchd / shell 入口。
- `output/`、`logs/`、`.env` 不入 git；`selection_watch_alerts.json` 运行时生成。
- 决策支持非投资建议；微信文案避免绝对买卖指令。

*最后更新：2026-05-30*
