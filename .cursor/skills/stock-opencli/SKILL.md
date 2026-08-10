---
name: stock-opencli
description: >-
  OpenCLI browser automation for stock-ai: Eastmoney quotes/SOP, WeChat MP backend
  analytics, JYWG positions, hot sectors. Use when user says OpenCLI, 东财浏览器,
  公众号后台抓取, fetch_*_opencli, or browser eval fails. Do NOT use Playwright for
  these paths (project rule).
paths:
  - stock-ai/scripts/tools/fetch_eastmoney_quotes.py
  - stock-ai/scripts/tools/fetch_wechat_mp_analytics_opencli.py
  - stock-ai/scripts/tools/fetch_jywg_positions_opencli.py
  - stock-ai/scripts/tools/probe_wechat_mp_session_timeout.py
  - stock-ai/scripts/opencli_browser_cleanup.sh
---

# stock-opencli · 浏览器自动化（OpenCLI）

> **不必每次现查命令**。Agent 遇到下表场景时 **先读本 skill**，再调对应 Python 入口；东财 **十一维深度分析** 另读 [eastmoney-browser-sop](../../stock-ai/investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md)。

**上下文预算**：普通行情/后台抓取只用本页的场景路由和对应命令；仅在 SOP 深度分析或浏览器故障时再读取后续参考章节。

## 何时用 / 不用

| 用 OpenCLI | 不用（改走别的） |
|------------|------------------|
| 东财现价、SOP、快讯、行业榜、技术面摘要 | 历史日线批量 → MySQL / Tushare |
| 公众号 **内容分析**、登录态探测 | 公众号草稿 API → `wechat_mp_client`（官方） |
| 交易软件持仓页抓取（JYWG） | 搜一搜看板「搜索后阅读/关注」→ 常需 **人工/小程序**（插件页易「遇到问题」） |

**禁止**：用 Playwright 替代本仓库东财/公众号后台链路（`project-memory` · investment-agent）。

---

## 环境（一次性）

```bash
# 默认二进制（可覆盖）
export OPENCLI_BIN="${OPENCLI_BIN:-$HOME/.nvm/versions/node/v24.14.1/bin/opencli}"
export PATH="$(dirname "$OPENCLI_BIN"):$PATH"
opencli --version    # 推荐 1.8.x（须配套 Chrome 扩展 ≥ 1.0.18 才能 bind）
opencli doctor       # Extension connected；有更新时从 releases 装新扩展

# 脚本内会 NO_PROXY=*，避免代理劫持东财/微信后台
```

`.env` 可选：

| 变量 | 用途 |
|------|------|
| `OPENCLI_BIN` | opencli 路径 |
| `OPENCLI_BROWSER_SESSION` | 自动化会话（默认 **`stock`**，同一 Chrome 窗复用标签） |
| `OPENCLI_BROWSER_WINDOW` | `background`（默认）或 `foreground`；减少抢前台 |
| `OPENCLI_BROWSER_IF_EXISTS` | **`navigate`**（默认）：同标签 `open` 跳转，**不** `tab new`（避免 Chrome 标签分组爆炸） |
| `OPENCLI_BROWSER_CLOSE_TABS_ON_RELEASE` | `1`（默认）：`release_browser_session` 关光会话内 tab 再 `browser close` |
| `OPENCLI_BROWSER_IF_EXISTS=tab` | 仅显式需要时；易堆分组，勿日常开 |
| `OPENCLI_BROWSER_NEW_TAB` | `1` = 等同强制 `IF_EXISTS=tab` |
| `OPENCLI_BROWSER_CLEANUP_SESSIONS` | cleanup 脚本要 `close` 的会话，默认 `stock,default,mp` |
| `WECHAT_MP_ANALYTICS_URL` | 内容分析页完整 URL（含 `token`） |
| `WECHAT_MP_ADMIN_TOKEN` | 仅 token，脚本自动拼 URL |

**安全**：带 `token=` 的 URL **勿提交 git**；输出 JSON 在 `stock-ai/output/`。

---

## 核心模式（写新抓取脚本时复用）

真源：`fetch_eastmoney_quotes.py` 的 `_run_opencli` / `_open_page` / `_eval_js`（1.7 形 `browser open` → 1.8 的 `browser stock --window background open`）。

### A. 自动化窗（单会话 `stock`，默认后台 + 复用标签）

```text
opencli browser stock --window background open <url>   # 默认同标签 navigate（IF_EXISTS=navigate）
# 勿日常 tab new — 易堆 Chrome「标签分组」；用完由脚本 release_browser_session 关 tab
opencli browser stock wait time <秒>
opencli browser stock eval <JSON.stringify(...)>
opencli browser stock close    # 任务结束释放 lease；批次中勿频繁 close
```

`_open_page` 默认：无窗 `open`；有窗 `tab new`（可选关上一标签）。批量扫股可设 `OPENCLI_BROWSER_IF_EXISTS=navigate`。

### B. 复用你已打开的 Chrome 标签（搜一搜看板等）

**前提**：页面在 **装了 OpenCLI 扩展的 Chrome** 里（不是 Cursor 内置浏览器）；扩展 **≥ 1.0.18**（`doctor` 若仍显示 v1.0.0，`bind` 会报 `Unknown action: bind`）。

```text
# 1) 在 Chrome 里点开目标页，并保持该 tab 为当前前台
#    例如：广告与服务 → 微信搜一搜 → 数据看板

# 2) 绑定当前前台 tab 到会话 mp（不新开 automation 窗）
opencli browser mp bind

# 3) 在同一 tab 上执行 JS / 读 state
opencli browser mp state
opencli browser mp eval "JSON.stringify({url:location.href, text:(document.body.innerText||'').slice(0,500)})"

# 4) 用完解绑（不关你的 tab）
opencli browser mp unbind
```

可选：`opencli browser mp tab list` / `tab select <targetId>` 在已 bind 的窗口里切换标签。

**为何推荐 bind**：`browser stock open` 打开搜一搜插件页常出现 **「遇到问题」**；你手动已进入看板时，bind 直接读当前 DOM，避免重复登录/插件初始化失败。bind 用会话 **`mp`**，与东财自动化 **`stock`** 分离。

Python 封装：

```python
from scripts.tools.fetch_eastmoney_quotes import (
    _open_page,
    _run_opencli,
    _eval_js,
    force_close_opencli_browser,
)
```

长任务后：`bash stock-ai/scripts/opencli_browser_cleanup.sh`（必要时 `--stop-daemon`）。

---

## 场景路由表（Agent 查这张表即可）

工作目录：`cd stock-ai` · 统一 `uv run python -m scripts.tools.<模块>`。

### A. 东方财富（主入口 `fetch_eastmoney_quotes`）

| 用户需求 | 调用 | 备注 |
|----------|------|------|
| 单股现价 | `fetch_quotes_opencli(['600995'])` | 或 CLI 同模块 `main` |
| 指数快照 | `fetch_index_snapshots()` | 上证/深证等 |
| SOP 多维快照 | `fetch_sop_snapshots(codes)` | 战报/Top5 审查 |
| 批量 SOP | `fetch_full_sop_batch(codes)` | 并发宜控制数量 |
| 7×24 快讯 | `fetch_macro_news_opencli` | `sync_macro_news.sh` |
| 快讯+评论数 | `fetch_kuaixun_engagement_opencli` | 要闻排序用 |
| **行业涨幅榜** | `fetch_hot_industry_sectors_opencli` / `fetch_hot_industry_board_rows_opencli`（含领涨股 JSONP） | `sector` 代表股样本 |
| **A 股人气榜** | `fetch_hot_stocks_opencli` | 公众号 `top5` 默认 `WECHAT_MP_TOP5_POOL=hot` |
| 龙头情绪池 | `fetch_emotion_topic_pools_opencli` | 情绪周期 |
| 技术面摘要 | `fetch_technical_summary_opencli` / `batch` | dragons/top5 注入 |
| K 线 JSONP | `fetch_kline_rows_opencli` | 浏览器内 JSONP，非 HTTP 直连 |

深度分析流程：[eastmoney-browser-sop](../../stock-ai/investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md)。

### B. 微信公众号「牛马也智能」后台

| 用户需求 | 命令 | 输出 |
|----------|------|------|
| **内容分析**（流量来源、文章排行、Top3 详情） | 见 [reference.md](reference.md) §公众号 · [content-analytics-sop](../wechat-mp-drafts/content-analytics-sop.md) | `output/wechat_mp_analytics_*.json` |
| 登录是否过期 | `uv run python -m scripts.tools.probe_wechat_mp_session_timeout` | 轮询 home |
| **搜一搜看板**（`pluginloginpage?pluginuin=10071`） | `fetch_wechat_mp_sousou_opencli`（**bind**，不 `open`） | Chrome 看板 tab 前台 → 脚本 bind+eval+unbind；解读 [sousou-analytics-sop](../wechat-mp-drafts/sousou-analytics-sop.md) |

内容分析可得到：**朋友圈/搜一搜/推荐等占比**、阅读人数 Top 文章、单篇「阅读后关注」——**不等于**搜一搜看板的「搜索后阅读/关注」口径。

### C. 其它

| 场景 | 模块 |
|------|------|
| 交易软件持仓页 | `fetch_jywg_positions_opencli` |
| 盘中情绪 OpenCLI | `stock_ai/emotion_intraday_fetch.py` |
| 公众号快采 | `wechat_mp_sop_fast.py` |

---

## 公众号内容分析 · 标准命令

**解读 SOP**：[content-analytics-sop.md](../wechat-mp-drafts/content-analytics-sop.md)（**页面柱图真源** · picker=单日 · 弃 API）。

```bash
cd stock-ai
uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --token YOUR_TOKEN \
  --begin-date 2026-06-15 --end-date 2026-06-15 \
  -o output/wechat_mp_analytics_latest.json

uv run python -m scripts.tools.fetch_wechat_mp_analytics_opencli \
  --token YOUR_TOKEN \
  --daily-series --series-begin 2026-06-02 --series-end 2026-06-16 \
  -o output/wechat_mp_recommend_daily_page.json
```

未登录：`--wait-login 120`。

**局限（2026-06 实测）**：

- **数据概况 tag ≠ 流量 picker**；点「昨日」柱图仍可能是 30 天累计（如 推荐 7.3%）。
- **单日占比**须 picker **D–D** 再读 highcharts（6/15 推荐 **3.9%**，非 7.3%）。
- 日历 picker：点 **「MM月」** 选月（头栏常无右箭头）。
- 搜一搜 plugin 看板 ≠ 内容分析页「搜一搜渠道%」。

---

## 故障速查

| 现象 | 处理 |
|------|------|
| `未找到 opencli` | 安装 Node + `OPENCLI_BIN` 指向 nvm 下二进制 |
| `请重新登录` | 带 token URL 或 `--wait-login`；wechat-acp 发一条消息刷新会话 |
| `stale page` / `detached` | `_open_page` 会 close 重试；再跑 `opencli_browser_cleanup.sh` |
| 东财页面空 | `browser wait time 5` 加长；禁 HTTP 直连东财 |
| 抓取 JSON 空 | 看 stderr；页面改版 → 改 `EXTRACT_*_JS` |
| 多个任务抢浏览器 | 持仓监控默认关；情绪 intraday launchd 与 19:00 草稿错峰 |
| 多个空白 Chrome 窗 | 确认 `OPENCLI_BROWSER_REUSE_TAB=1`；cleanup 关 `stock,default,mp` |

---

## 与其它文档

| 文档 | 关系 |
|------|------|
| [reference.md](reference.md) | CLI 参数、URL 模板、扩展抓取 |
| [wechat-mp-drafts/content-analytics-sop.md](../wechat-mp-drafts/content-analytics-sop.md) | 内容分析页 **日期 + 渠道占比** 解读 |
| [wechat-mp-drafts/sousou-analytics-sop.md](../wechat-mp-drafts/sousou-analytics-sop.md) | 搜一搜数据 **怎么运营解读** |
| [wechat-mp-drafts/operations-sop.md](../wechat-mp-drafts/operations-sop.md) | 牛马也智能发布节奏 |
| `stock-ai/docs/CAPABILITIES.md` | 数据四档 · OpenCLI 不落库 |
| `memory-python.mdc` | 弃用 HTTP 东财、OpenCLI 主链路 |

## 扩展本 skill

新增 OpenCLI 场景时：在 `stock-ai/scripts/tools/` 增加 `*_opencli.py` → 本表 **场景路由** 加一行 → 复杂流程写 `reference.md` 一节。
