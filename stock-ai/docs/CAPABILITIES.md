# stock-ai 能力总览

> 工作目录：`/Users/yolo/dev/yolo/tools-workspace/stock-ai`  
> 投资 Agent：`investment-agent/`（**投顾带操**：`投顾主策略.md` 决策 → 工具执行 → 看板/微信交付）  
> 本文档为**当前生产链路**的单一入口；细节见各子文档链接。

---

## 个股诊断涨停逻辑

- 领域模块：`stock_ai/limit_up_logic/`，同时服务指定个股与 MySQL 持仓诊断。
- 日线输入：MySQL `stock_daily` 最近最多 60 根完整日线；支持 `--as-of` 历史回放。
- 外部证据：已验证活跃题材、板块涨幅与涨停梯队、领涨股强度、主力资金连续性和重大风险。
- 输出身份：数据不足、风险否决、接力失败、二波加速候选、首板后承接、首板预备、普通趋势。
- 输出概率：涨停加速、趋势延续、接力失败三路径；整数且总和为 100。
- 约束：概念标签本身不加板块分；缺少竞价或封单时涨停加速概率不超过 45%；任何结果都不能绕过账户与公告风险门禁。

独立回放命令：

```bash
uv run python scripts/analysis/analyze_limit_up_logic.py \
  --code 603011 --name 合锻智能 --as-of 2026-08-06 \
  --concept 可控核聚变,光通信模块,工业母机 \
  --active-theme 可控核聚变
```

消息面服务负责确认催化与产业链传导；涨停逻辑引擎负责日线身份、承接和加速结构。同一事件不在两个模块重复加分，重大利空可触发涨停逻辑风险否决。

## 东财涨停研究账本（手动）

```bash
PYTHONPATH=. .venv/bin/python -m scripts.analysis.sync_limit_up_research --date YYYY-MM-DD
```

- 东财 OpenCLI 全量采集涨停、炸板、跌停池；连板高度来自涨停池原始字段。
- `trade_date` 的涨停事实与前一交易日 `selection_date` 的全部选股策略对照，避免未来信息污染。
- 幂等保存原始事实、确定性漏选归因及 T+1/T+3/T+5 标签，并输出 Markdown/JSON 复盘。
- 仅手动运行，不安装调度；不调用已弃用的东财八维诊断，不改变持仓、决策账本、策略参数或正式 Top5。

### 东财八维 SOP 的 AI 边界

```text
AI_STATUS: DEPRECATED
AI_USAGE: FORBIDDEN
HUMAN_USAGE: AUDIT_ONLY
```

东财八维/十一维遗留脚本和历史产物仅作为人工审计遗留能力保留。AI 不得调用、推荐、继续读取其 SOP 正文，也不得依据其输出生成个股结论；AI 单股分析统一使用 `stock-strategy-selector` 的新版个股诊断链路。

---

## 个股诊断消息面影响

- 共用模块：`stock_ai/news_impact/`，同时服务单股诊断与 MySQL 批量持仓诊断。
- 输入来源：MySQL `macro_news_items`、已核验标准事件缓存 `news_impact_events`；缺少海外公司级消息时明确降级，不以模型常识补事实。
- 时效：海外公司/市场24小时，政策/产业3天，A股公告/业绩/监管7天。
- 输出：消息分、传导类型、相关度、证据、基础/修正/最终三路径概率、重大利空门禁和数据截止时间。
- 约束：利好最高 `+12`，利空最低 `-20`；传闻不计分；单一利好不能生成交易结论或绕过风险门禁。
- 独立命令：

```bash
uv run python scripts/analysis/analyze_news_impact.py \
  --code 600186 --name 莲花控股 --concept 算力租赁 \
  --base 35,45,20 --existing-holding
```

- 可通过 `--event-json <文件>` 导入经官方来源核验的标准事件并写入缓存。
- 国际市场快照包含美股主要指数、恒生、日经225、韩国KOSPI与韩国KOSDAQ；单个指数采集失败时跳过并保留其他结果。
- 后续已确认但尚未实施：短线选股采用“技术面候选池＋重大新闻事件池”并行合并评分。

---

## 0. 投顾带操（总原则）

**所有面向用户的自动化输出**，须先符合 `investment-agent/投顾主策略.md` 阶段，再落到 `持仓执行卡.md` 价位与监控。

```text
投顾主策略（阶段 0/1/2 · 本周必做/禁止）
        ↓ 过滤 & 解读
工具层：选股 / 新版诊断 / 监控 / 战报 / MCP（均注入决策上下文）
        ↓ 交付
看板 home-hub · 微信战报 · investment-agent 对话
```

| 阶段 | 选股 Top5 | 新版诊断 / AI 简评 | 次日监控 | 执行卡试探买 |
|------|-----------|---------------|----------|--------------|
| **0 止血降仓** | 情报池（继续观察） | 新版诊断可用 / AI 简评跳过 | 不写 selection 规则 | 仅减仓提示 |
| **1 稳态组合** | 小仓试探 | 启用 | 启用 | B 档 P-买 |
| **2 进攻试探** | 可进攻 | 启用 | 启用 | 按档位 |

代码门控：`stock_ai/advisor_selection.py`（读 `投顾主策略.md` 阶段标记）。

**专业投顾能力**（2026-06-02）：

- 模块：`stock_ai/advisor_diagnosis.py` — 账户健康度、集中度、配置缺口、风险预算、投教
- 文档：`investment-agent/投顾专业技能.md` — 对齐中证协投顾六大职责
- 看板 `advisor.diagnosis` + 扩展 `delivery_template`（七段交付）
- 战报首段含 `【账户诊断】` 摘要

---

## 1. 架构一览

```text
数据层                策略 / 分析层              推送层
─────────            ─────────────            ────────
Tushare → MySQL      综合选股 Top5            wechat-acp
东财实时 / 盘中       新版诊断 + AI 简评       （wechat-cursor-acp）
                     战报 + AI 解读
                     MCP 盘中 / 做T 信号
                     持仓 + 选股池监控
```

### 数据分层四档（审计口径）

Agent 排查「是否漏接 DB/OpenCLI」时，先对号入座；**只有第一档是 17:30 生产主链路**。

| 档位 | 含义 | 典型入口 / 产物 | 为何如此 |
|------|------|-----------------|----------|
| **① 主链路** | 该进 DB 的进 DB，该用 OpenCLI 的用 OpenCLI | Tushare sync → `stock_daily`；综合选股 → `selection_daily_results`；执行卡 sync → `portfolio_positions` / `alert_rules`；战报/监控现价 → `fetch_eastmoney_quotes.py` | 生产自动化单一真相源 |
| **② 不进 DB，用 OpenCLI** | 实时/页面型，抓完即用 | 现价、7×24 快讯、战报指数/国际盘 | 变化快、结构杂，入库性价比低 |
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
| 1 | **投顾主策略**（阶段、回本路径、本周必做） | `investment-agent/投顾主策略.md` |
| 2 | 持仓执行卡（执行价位、监控） | `investment-agent/持仓执行卡.md` |
| 3 | 通用操盘策略 | `investment-agent/memory/trading-strategies.md` |
| 4 | 个股新版诊断 | `investment-agent/docs/skills/stock-strategy-selector/` |

注入方式：

- Python：`from scripts.tools.decision_context import inject_decision_context`
- 或：`load_full_decision_context()`（`scripts/tools/holdings_context.py`）
- MCP：`tushare_mcp.py` 内 `_maybe_inject_decision_context()`（`SKIP_DECISION_CONTEXT=1` 可跳过）

**投顾看板（home-hub）**

- API：`GET /api/dashboard/advisor`；`summary` 响应含 `advisor` 块（阶段、回本进度、本周必做）
- **周五周复盘**：`push_advisor_weekly_review.sh` → MySQL `advisor_weekly_reviews` → 看板 `advisor.weekly_review_latest`；API `GET /api/dashboard/advisor/weekly-reviews`
- 选股 Top5 经 `advisor_selection` 过滤；阶段 0 = 情报池，跳过 AI 简评与 `selection_watchlist --sync`
- 战报 `daily_briefing_report.py` 首行含投顾横幅

**Agent Skill 权威副本**（与 `~/.codex/skills/` 不一致时以 repo 为准）：

- 东财八维遗留资料：`investment-agent/docs/skills/eastmoney-browser-sop/`（人工审计；AI 禁止进入正文）
- 选股工作台：`investment-agent/docs/skills/stock-strategy-selector/SKILL.md`

---

## 2. 定时任务（统一调度）

> **权威文档**：[docs/SCHEDULING.md](SCHEDULING.md) — 设计原因、架构图、安装、日志、回滚。

**生产（2026-05-31 起）**：Docker `stock-ai-scheduler` 管 cron；OpenCLI/微信任务经本机 `host-jobs`（`:9876`）执行。

| 任务 | 调度 | 执行位置 | 入口 |
|------|------|----------|------|
| Tushare 日线同步 | 工作日 **17:30** | scheduler **容器内** | `run_sync_daily.sh` |
| 选股入库 | 工作日 **17:45** | 本机 host-jobs | `push_selection_wechat.sh` → `run_selection_daily.sh`（SOP/战报默认关） |
| 东财快讯 + AI 解读 | **每 15 分钟** | launchd | `sync_macro_news.sh` |
| 持仓 + 选股池监控 | 工作日 **每 5 分钟** | Docker → host-jobs | `push_holdings_monitor.sh`（勿装 `holdings-monitor` launchd） |
| 情绪周期 / 收盘龙头 | 工作日 **18:00 eod** 容器（盘前 pre_market 已下线） | `sync_emotion_cycle.sh eod` |
| **投顾周五周复盘** | **周五 20:30** | 本机 | `push_advisor_weekly_review.sh` → 看板 `/advisor` |
| 公众号草稿 | 每天 **19:00** | launchd | `wechat_mp_draft_scheduled.sh` |

**安装**：`./scripts/install-stock-ai-scheduler.sh`（移除旧 selection/briefing/holdings-monitor launchd，启动 scheduler）。

**已停用定时**：09/12/15/20 战报微信推送 → 改快讯 `com.user.stock-macro-news-sync`。详见 [SCHEDULING.md](SCHEDULING.md)。

**仍用 launchd**：`host-jobs`、`docker-stacks`、`wechat-mp-guba-scheduled` 等 — 见 SCHEDULING.md §7。

**微信公众号草稿**：工作日 **18:00 eod 成功后** + 周日 18:00 → host-jobs `wechat-mp-draft`（见 [WECHAT_MP_SCHEDULING.md](WECHAT_MP_SCHEDULING.md)）。

**旧 launchd 安装脚本**（仅回滚）：`install-daily-selection-launchd.sh`、`install-daily-briefing-launchd.sh`、`install-holdings-monitor-launchd.sh`。

**手动试跑**

```bash
cd stock-ai
./push_selection_wechat.sh                      # 完整 17:30
REPORT_ONLY=1 ./push_selection_wechat.sh        # 跳过选股，仅推送已有产物
./sync_macro_news.sh                            # 快讯 + AI 解读（与 15min launchd 相同）
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
       ├─ ensure_daily_bars --sync-if-stale --require-ready  # 期望日+条数门禁，未就绪 exit 1
       └─ daily_selection_report              # 综合选股 Top5；遗留东财 SOP 默认关闭
  └─ selection_watchlist --sync                # 既有审查结果 → MySQL selection_watch_picks + alert_rules
  └─ 微信推送选股报告（wechat-acp）
```

| 步骤 | 模块 | 输出 |
|------|------|------|
| 日线门禁 | `scripts/tools/ensure_daily_bars.py` | 期望交易日 + 当日≥3500 条；落后 by_date 补同步，仍不满足中止选股 |
| 综合选股 | `core_v2/stock_selection_combined.py` | MySQL `selection_daily_results` + CSV 导出 |
| 遗留 SOP 采集 | `scripts/tools/fetch_eastmoney_quotes.py` → `eastmoney_sop_extract.py` | 人工审计专用；AI 禁止调用 |
| 遗留 SOP + DeepSeek | `scripts/analysis/sop_review_top5_concurrent.py` | 历史兼容入口；AI 禁止调用 |
| 干净 AI 摘要 | `daily_selection_report.py` | `output/daily_selection_ai_latest.txt`（无 stderr 日志） |
| 次日监控 | `scripts/tools/selection_watchlist.py` | MySQL `selection_watch_picks` + `alert_rules`（source=selection） |

**盘中/全天快讯与 AI 解读**：`sync_macro_news.sh`（launchd 每 15 分钟），非 17:30 链路。

**环境变量**

- `DISABLE_SOP_TOP5=1`（**必须保持**）— 跳过 Top5 东财八维 SOP；AI 不得改为 `0`
- `DISABLE_SELECTION_REPORT=1`（**默认**）— 跳过 `daily_selection_report` 与 `daily_selection_full_latest.txt` 落盘
- `SOP_WORKERS` — 已弃用（OpenCLI 单会话）；`DEEPSEEK_WORKERS` — 并发数（默认 3）
- `REPORT_ONLY=1` — 不重跑选股，仅战报+推送

**SOP 监控规则**：仅 `DECISION=买入观察/观察买入/小仓埋伏` 且 **非持仓** 写入次日监控；解析以 **DECISION 优先**（`scripts/tools/sop_watch_parse.py`）。

---

## 4. 快讯与 AI 解读（定时：每 15 分钟）

| 模块 | 说明 |
|------|------|
| `sync_macro_news.sh` | **定时已停用**；需时手动 `./sync_macro_news.sh` |
| `scripts/tools/fetch_eastmoney_macro_news.py` | OpenCLI 抓东财 7×24 |
| `scripts/tools/news_ai_interpret.py` | 快讯 AI 解读落库 |
| `scripts/tools/daily_briefing_report.py` | **手动/看板**用；09/12/15/20 微信战报已停用 |

**AI 解读格式**（看板/快讯，微信友好）：

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
**做不做**以投顾主策略为准；**什么价位触发**以持仓执行卡为准。

---

## 6. 数据同步

| 能力 | 入口 | 说明 |
|------|------|------|
| Tushare 日线 → MySQL | `scripts/sync/sync_tushare_daily_to_mysql.py` | 主入口；`./run_sync_daily.sh` |
| 选股前日线门禁 | `ensure_daily_bars_at_selection_start()` | `run_selection_daily` / `run_parallel_selection` / `stock_selection_combined`；`SKIP_DAILY_BARS_CHECK=1` 跳过 |
| 执行卡 → 持仓/监控 | `scripts/tools/sync_portfolio_from_card.py` | `portfolio_positions` / `portfolio_account` / `alert_rules` |
| 实时行情 / SOP | `scripts/tools/fetch_eastmoney_quotes.py` | OpenCLI；东财 HTTP 入库脚本已移除 |
| 东财证券网页持仓 | `scripts/tools/fetch_jywg_positions_opencli.py` | OpenCLI；首次手动登录，在线时间最长 3h；`--wait-login` |
| Docker 统一调度 | `docker/scheduler/` | sync 17:30 + 选股 17:45 + 龙头 eod 18:00；见 [SCHEDULING.md](SCHEDULING.md) |
| 掘金仿真量化 | 独立子项目 [`../emquant-sim/`](../emquant-sim/README.md) | **2026-06-02 已下线**（`EMQUANT_ENABLED=0`）；情绪周期仍走 MySQL |

详见 [TUSHARE_SYNC_GUIDE.md](TUSHARE_SYNC_GUIDE.md)。

**注意**：本机运行时 `MYSQL_URL` 中 `host.docker.internal` 会在 sync 脚本内替换为 `127.0.0.1`。

---

## 7. LLM 调用（写稿 Cursor + SOP DeepSeek）

统一封装：`scripts/tools/deepseek_client.py`（Cursor 实现见 `cursor_agent_client.py`）

| 变量 | 默认 | 说明 | 前置 |
|------|------|------|------|
| `LLM_BACKEND` | `deepseek`（**.env.example 推荐 `cursor`**） | 公众号写稿、战报、AI 审查 | `cursor` → `agent login`；`deepseek` → `DEEPSEEK_API_KEY` |
| `SOP_LLM_BACKEND` | `deepseek` | 东财 SOP 并发终审（**不受** `LLM_BACKEND` 影响） | `DEEPSEEK_API_KEY` |

| 函数 | deepseek 模型 | cursor 模型 | 典型调用方 |
|------|---------------|-------------|------------|
| `call_deepseek(…)` | `DEEPSEEK_MODEL` | `CURSOR_AGENT_MODEL` | 写稿；SOP 传 `backend=sop_llm_backend()` |
| `call_deepseek_prompt(…)` | `DEEPSEEK_MCP_MODEL` | 同上 | MCP、持仓分析 |

Cursor 相关：`CURSOR_AGENT_WORKSPACE`（默认 `investment-agent`）、`CURSOR_AGENT_MODE=ask`（只读问答）、`CURSOR_AGENT_TIMEOUT_SECONDS`（默认 300）。

MCP 工具：`tushare_mcp.py` — `deepseek_trade_signal` 等。详见 [DEEPSEEK_USAGE.md](DEEPSEEK_USAGE.md)。

---

## 8. 选股策略（手动 / 研究）

| 策略 | 脚本 | 输出 |
|------|------|------|
| 买点优先 V1.3（正式入口，当前按晋级门禁决定 SHADOW/LIVE） | `../a-share-short-term-trading/scripts/select_short_term_candidates.py` | `正式候选 / 准备中观察 / 影子研究 / 拒绝统计` + V1.3 计划账本 |
| 综合选股（17:30 默认） | `core_v2/stock_selection_combined.py` | MySQL `selection_daily_results` + CSV 备份 |
| 五因子（v3） | `core_v3/stock_selection_five_factor_mysql.py` | MySQL `strategy=five_factor` + CSV 备份 |
| 量价突破 | `scripts/selection/stock_selection.py` | `stock_selection_*.csv` |
| MA5 回踩 | `scripts/selection/stock_selection_ma5.py` | `stock_selection_ma5_*.csv` |
| 筑底+放量突破 | `core_v2/stock_selection_bottom_breakout_eastmoney.py` | MySQL `strategy=bottom_breakout` + CSV |
| 底部启动（旧） | `scripts/selection/stock_selection_bottom_breakout.py` | `stock_selection_bottom_breakout_*.csv`（手动） |

筛选条件详解见 [SELECTION_STRATEGIES.md](SELECTION_STRATEGIES.md)。

买点优先规则版本为 `buy-point-selection-3.1.0`。它一次读取完整沪深主板面板，只识别平台临界突破、强趋势缩量回踩和首次启动后浅回踩；普通三连阳、旧四轨、涨停基因和事件池只能进入影子研究，不能升级正式资格。正式候选每天为 0—3 只，市场或点时数据不完整时允许为 0。入口仅手动运行，不安装定时任务：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/select_short_term_candidates.py --output text
```

点时行业、ST/停牌和重大公告风险默认由巨潮资讯 + BaoStock 手动同步。普通选股不刷新参考数据；只有显式执行下面的同步命令或传入 `--refresh-reference-data` 才会联网更新。同步按 provider、数据集和分区保存检查点，行业与日级覆盖率低于 98% 时失败关闭正式资格。该命令不会安装定时任务：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2024-01-02 --end latest
```

历史公告缺口可单独断点回补，不会同步行业或 ST 数据：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2023-12-26 --end 2026-08-04 \
  --provider cninfo-baostock --announcement-provider eastmoney \
  --datasets announcement
```

公告专用模式只写公告检查点、公告同步运行记录和标准化风险标记，已经完成的分区会跳过。Eastmoney 分页请求间隔 0.5 秒；遇到 HTTP 403、429 或 567 时每次冷却五分钟，三次重试耗尽后保存失败记录并停止整次运行。该命令仅手动执行，不安装调度，也不调用东财个股诊断或八维分析。

Tushare 仅作为显式回退；当前 token 缺少对应接口权限时预期返回失败，不会把不完整数据标成成功：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2024-01-02 --end latest --provider tushare
```

3.1.0 为每个历史计划保留 `NOT_TRIGGERED / TARGET_2R_FIRST / STOP_FIRST / EXPIRY_GAIN / EXPIRY_LOSS / EXPIRY_FLAT` 路径结果，以及五日 MFE、MAE 和扣费后净收益。运行时按形态、市场状态和板块共振逐级选择至少 30 笔已触发样本的校准组，先按净期望，再按 2R 成功率、止损率和滚动稳定性排序。报告中的 2R/止损概率是历史同类样本的 95% Wilson 区间，不是个股上涨保证。

验证产物必须使用 `buy-point-selection-validation-v2`。旧 v1 产物、净收益字段不完整的观察数据、空校准或规则哈希不一致都会失败关闭，不能取得正式资格。

完整历史流程先生成观察集和完整性清单，再冻结训练/验证校准，最后运行一次测试段。示例区间为 630 个已结算信号日，信号截止 2026-08-04，后续行情保留到 2026-08-13：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/generate_buy_point_observations.py \
  --start 2023-12-26 --end 2026-08-04 \
  --out stock-ai/output/buy-point-replay

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --research-train-validation --point-in-time-complete \
  --trading-dates stock-ai/output/buy-point-replay/trading-dates.json \
  --observations stock-ai/output/buy-point-replay/outcome-observations.json \
  --manifest stock-ai/output/buy-point-replay/replay-integrity.json

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --freeze-profile --point-in-time-complete \
  --trading-dates stock-ai/output/buy-point-replay/trading-dates.json \
  --observations stock-ai/output/buy-point-replay/outcome-observations.json \
  --manifest stock-ai/output/buy-point-replay/replay-integrity.json

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --run-test --write-artifact --point-in-time-complete \
  --trading-dates stock-ai/output/buy-point-replay/trading-dates.json \
  --observations stock-ai/output/buy-point-replay/outcome-observations.json \
  --manifest stock-ai/output/buy-point-replay/replay-integrity.json
```

观察集同时保存信号日、代码、结构 ID、实际入场日和风险距离，测试段排名不能读取候选结果。训练/验证共 80% 日期形成冻结校准；剩余 20% 日期只做一次组合级测试，并执行每日候选数、同板块和最多三笔并发持仓限制。完整性清单、观察集、冻结 profile 和验证产物均为本地运行文件，不提交 Git。

### 五日净收益四画像影子研究

该流程与旧 `TWO_R` 生产/验证链路完全隔离，只比较四个固定画像：

- `BREAKOUT_TRIGGER__FIXED_3_PERCENT`
- `BREAKOUT_TRIGGER__STRUCTURE_ATR`
- `PULLBACK_RECLAIM__FIXED_3_PERCENT`
- `PULLBACK_RECLAIM__STRUCTURE_ATR`

所有研究成交使用 1 万元目标名义金额和整手评估股数，但交易权限始终为 `CASE_ANALYSIS_ONLY / NO-TRADE`，`executable_shares` 固定为 0。至少 630 个完整信号交易日按 `378 / 126 / 126` 切成训练、验证和一次性测试段；测试结果不能参与校准。空研究、空冻结、空测试资格和空前向筛选均为合法结果，不补位。

五个阶段仅可手动执行，默认产物目录为 `output/research/buy_point_five_day_returns`：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/research_five_day_return_shadow.py research \
  --signal-start YYYY-MM-DD --signal-end YYYY-MM-DD

PYTHONPATH=. .venv/bin/python scripts/analysis/research_five_day_return_shadow.py freeze \
  --research-artifact <research JSON>
```

同一 freeze identity 的 test 只能执行一次。代码验收不得顺手运行真实测试段；只有用户明确确认开始冻结测试时才执行。

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/research_five_day_return_shadow.py test \
  --freeze-artifact <freeze JSON> --research-artifact <research JSON>
```

通过测试的画像只获得前向影子观察资格，不会进入正式选股。每个已完成信号日最多保留 3 个冻结排名候选；筛选文件不包含入场、退出或收益字段。后续结算另写新文件，不能改写原筛选：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/research_five_day_return_shadow.py forward-screen \
  --signal-date YYYY-MM-DD --freeze-artifact <freeze JSON> \
  --test-artifact <test JSON>

PYTHONPATH=. .venv/bin/python scripts/analysis/research_five_day_return_shadow.py forward-settlement \
  --screen-artifact <forward-screen JSON> --outcome-cutoff YYYY-MM-DD
```

该入口不提供调度、通知、可执行股数、持仓、订单、决策账本、个人投顾记忆或跳过门禁的参数，也不会修改旧 `TWO_R` 规则、校准和产物。

### 买点阈值影子研究

该流程只研究 48 组单一形态阈值放宽，不修改正式规则。所有候选固定为 `CASE_ANALYSIS_ONLY / NO-TRADE`、可执行股数为 0；仅手动运行，不安装调度、不发送通知、不写持仓、决策账本或订单。必须先生成两段研究产物，再冻结合格 profile，最后只运行一次独立测试窗：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_threshold_shadows.py research \
  --signal-start 2026-07-20 --signal-end 2026-07-24 \
  --outcome-cutoff 2026-07-31 \
  --v5-case output/research/buy_point_cases/20260720_20260724_cutoff-20260731_da99d57b7b78fc3e.json

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_threshold_shadows.py research \
  --signal-start 2026-07-27 --signal-end 2026-07-31 \
  --outcome-cutoff 2026-08-07 \
  --v5-case output/research/buy_point_cases/20260727_20260731_cutoff-20260807_38b1bdbe2cf95faa.json

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_threshold_shadows.py freeze \
  --research-artifact <第一段研究 JSON> \
  --research-artifact <第二段研究 JSON>

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_threshold_shadows.py test \
  --signal-start 2026-08-03 --signal-end 2026-08-07 \
  --outcome-cutoff 2026-08-14 \
  --v5-case output/research/buy_point_cases/20260803_20260807_cutoff-20260814_1476b69b11fda315.json \
  --freeze-artifact <冻结 JSON>
```

短窗口通过只允许进入扩大历史验证，不能晋级正式规则；空冻结集是有效研究结果，禁止为了凑候选而补位。

### 买点门禁影子研究与前向观察

该流程只隔离研究正式形态通过后被市场或板块门禁挡住的样本，不修改 `models.py`、`patterns.py`、`gates.py` 或 `planning.py`。六类 profile 中，两类市场弱势只做诊断；四类单一板块失败允许参加冻结。三段历史窗口都已经观察过，因此只是回顾性案例研究，不是独立样本外测试。

先手动生成三段研究产物，再聚合冻结：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_gate_shadows.py research \
  --signal-start 2026-07-20 --signal-end 2026-07-24 \
  --outcome-cutoff 2026-07-31 --v5-case <对应窗口的 v5 JSON>

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_gate_shadows.py research \
  --signal-start 2026-07-27 --signal-end 2026-07-31 \
  --outcome-cutoff 2026-08-07 --v5-case <对应窗口的 v5 JSON>

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_gate_shadows.py research \
  --signal-start 2026-08-03 --signal-end 2026-08-07 \
  --outcome-cutoff 2026-08-14 --v5-case <对应窗口的 v5 JSON>

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_gate_shadows.py freeze \
  --research-artifact <第一段研究 JSON> \
  --research-artifact <第二段研究 JSON> \
  --research-artifact <第三段研究 JSON>
```

冻结后，盘后手动生成零仓位前向筛选；恰好五个已完成交易日后再单独结算：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_gate_shadows.py screen \
  --signal-date YYYY-MM-DD --freeze-artifact <冻结 JSON>

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_gate_shadows.py settle \
  --screen-artifact <前向筛选 JSON> --outcome-cutoff YYYY-MM-DD
```

所有阶段固定为 `CASE_ANALYSIS_ONLY / NO-TRADE`，可执行股数为 0。筛选最多 5 只，空冻结和空筛选都是有效结果，不补位。筛选仅读取信号日及以前价格；结算产物另写新文件，不能改写原筛选。流程不包含定时任务、通知、持仓写入、个人/决策记忆写入或自动下单。至少积累 20 个不同前向信号日且 20 个计划完成结算后，才允许讨论扩大验证，仍不得自动晋级正式策略。

### 买点结构止损影子研究

该流程只研究一种单变量问题：正式形态和全部正式门禁已经通过、生产价格计划唯一失败原因为 `RISK_DISTANCE_OUT_OF_RANGE` 时，替换止损锚点能否在不降低 2R 目标和其他正式约束的前提下形成有效计划。固定比较 `RECENT_SETUP_LOW`、`DYNAMIC_SUPPORT` 和 `ATR_1_5` 三种画像。市场或板块门禁同时失败的样本只进入 `DIAGNOSTIC_ONLY_COMBINED_FAILURE` 诊断队列，永久排除于指标、冻结、排名和前向筛选。

研究日历由本地 MySQL 中截至 2026-08-14 的 80 个已确认交易日派生为八个连续区块；每个区块包含五个信号交易日和紧随其后的五个结果交易日。八个区块均已发生，因此只属于回顾性案例研究，不是独立样本外测试。对每个派生区块手动运行一次：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_structure_stops.py research \
  --signal-start YYYY-MM-DD --signal-end YYYY-MM-DD \
  --outcome-cutoff YYYY-MM-DD --v5-case <对应窗口的 v5 JSON>
```

八份不可变研究 JSON 全部验证后才能冻结；参数必须恰好出现八次：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_structure_stops.py freeze \
  --research-artifact <窗口1研究JSON> \
  --research-artifact <窗口2研究JSON> \
  --research-artifact <窗口3研究JSON> \
  --research-artifact <窗口4研究JSON> \
  --research-artifact <窗口5研究JSON> \
  --research-artifact <窗口6研究JSON> \
  --research-artifact <窗口7研究JSON> \
  --research-artifact <窗口8研究JSON>
```

冻结后可手动生成零仓位前向筛选。筛选只读取信号日及以前的价格，未来两个已确认交易日仅用于计划有效期，输出最多 5 只且不包含任何结果字段。恰好五个已完成交易日后，使用原筛选文件单独结算：

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_structure_stops.py screen \
  --signal-date YYYY-MM-DD --freeze-artifact <冻结JSON>

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_structure_stops.py settle \
  --screen-artifact <前向筛选JSON> --outcome-cutoff YYYY-MM-DD
```

研究、冻结、筛选和结算均固定为 `CASE_ANALYSIS_ONLY / NO-TRADE`，所有可执行股数为 0。空研究候选、空冻结和空前向筛选都是合法结果，不补位、不放宽门槛。结算另写新文件且不能改写原筛选。该流程不安装调度、不发送通知、不写持仓、个人记忆、决策账本或订单，也不会自动修改正式规则 `buy-point-selection-3.1.0`。

`LIVE` 不由 AI 或单次回测决定。必须先通过冻结历史门槛，再完成至少 20 个不同交易日的手动前向运行和至少 20 个已解决计划，且完整性违规为 0；否则统一输出 `SHADOW`。只有正式层显示最大股数，观察和影子层固定显示无交易资格。

盘后 DeepSeek 审查（非 17:30 自动化路径）：见 [pipelines/daily_stock_deepseek_pipeline.md](pipelines/daily_stock_deepseek_pipeline.md)。

---

## 9. 分析与工具

| 能力 | 模块 |
|------|------|
| 换仓 / 试探仓执行表 | `scripts/tools/position_sizing.py`（CLI：`uv run python -m scripts.tools.position_sizing`） |
| 持仓 + 策略上下文 | `scripts/tools/holdings_context.py`（读 MySQL + 执行卡计划/红线） |
| 执行卡同步 MySQL | `scripts/tools/sync_portfolio_from_card.py` |
| 决策 prompt 注入 | `scripts/tools/decision_context.py` |
| 东财八维遗留单股 | `investment-agent/docs/skills/eastmoney-browser-sop/`（人工审计遗留能力；AI 禁止读取正文或调用） |
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

**home-hub 看板读法（2026-06-01）**：

| 展示 | 数据源 | 何时更新 |
|------|--------|----------|
| 总览/持仓「当前」账户与持仓 | **`portfolio_account` + `portfolio_positions`** | 东方财富证券 `fetch_jywg_positions_opencli --sync-db` 或 `sync_portfolio_from_card` 后立即 |
| 资产/盈亏曲线、按日快照下拉 | **`portfolio_*_daily`**（`slot=eod/midday/sync`） | `snapshot-portfolio` / 战报·同步脚本 |

`export_dashboard_payload` 的 `positions_latest` **不再**用 eod 快照冒充当前；`snapshot_slot` 只影响历史序列。

**已删除遗留表**（2026-05-31）：`capital_flow`、`stock_intraday_snapshot`、`stock_orderbook_snapshot`（见 `006_drop_legacy_eastmoney_tables.sql`）。

---

## 13. 维护约定

- 新增自动化能力时：**先更新本文档**，再改 launchd / shell 入口。
- `output/`、`logs/`、`.env` 不入 git。
- 持仓/监控数据源为 MySQL；改执行卡后运行 `sync_portfolio_from_card`。
- 决策支持非投资建议；微信文案避免绝对买卖指令。
- 数据分层四档见 **§1 数据分层四档**；勿把 ④ 档旁路误判为「漏接 DB/OpenCLI」。

*最后更新：2026-05-30*
