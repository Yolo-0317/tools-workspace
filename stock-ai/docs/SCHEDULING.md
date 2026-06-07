# stock-ai 统一调度

> **当前生产方案**（2026-05-31 起）：Docker `stock-ai-scheduler` 管 cron + 本机 `host-jobs` 执行 OpenCLI/微信任务。  
> 能力总览见 [CAPABILITIES.md](CAPABILITIES.md)；安装细节见 [docker/scheduler/README.md](../docker/scheduler/README.md)。

---

## 1. 为什么这样设计

投资相关任务分两类，**不能**简单「全 Docker」或「全 launchd」：

| 类型 | 例子 | 运行环境 |
|------|------|----------|
| **纯数据** | Tushare 日线 → MySQL | 容器内 Python + 网络即可 |
| **要「动手」** | 选股 SOP、战报、持仓监控推微信 | 需 **OpenCLI 浏览器**、**wechat-cursor-acp**、本机 `.env` 与持仓路径 |

第二类在容器里成本高：要挂浏览器、微信桥、大量宿主机目录，且与 Cursor CLI 工具链绑定在本机 Mac。

### 旧方案的问题（2026-05 前）

```
launchd 17:45 选股（经 host-jobs）
launchd 09/12/15/20 简报
launchd 每 5 分钟 监控
Docker scheduler 17:30 同步 · 18:00 龙头 eod
```

- **调度分散**：4 处看 cron/plist，排查困难
- **launchd 环境不完整**：无 `uv`、PATH 不全 → 监控曾 exit 127
- **职责重复**：daily-sync 与 launchd 各管一半

### 现方案原则

- **「几点跑」** → 集中到一个 Docker crontab（`stock-ai-scheduler`）
- **「OpenCLI/微信怎么跑」** → 本机单一 HTTP 入口（`host-jobs`），由 launchd KeepAlive 保活

---

## 2. 架构

```text
┌──────────────────── stock-ai-scheduler (Docker / supercronic) ────────────────────┐
│  17:30  sync      → run_sync_daily.sh（容器内）                                    │
│  17:45  selection → run-host-job.sh selection                                      │
│  18:00  emotion eod → sync_emotion_cycle.sh eod（容器内，MySQL）                   │
│  */5 工作日       → run-host-job.sh monitor（勿再开 holdings-monitor launchd）      │
│  周五 20:30       → run-host-job.sh advisor-weekly                                 │
└───────────────────────────────┬───────────────────────────────────────────────────┘
                                │ HTTP POST host.docker.internal:9876/run/{job}
                                ▼
┌──────────────────── 本机 host-jobs (launchd com.user.stock-ai-host-jobs) ─────────┐
│  push_selection_wechat.sh · push_holdings_monitor.sh · push_advisor_weekly_review │
└───────────────────────────────────────────────────────────────────────────────────┘

launchd（与 Docker 分工，勿重复监控）
  com.user.stock-macro-news-sync     每 15min  快讯 + AI 解读落库
  com.user.stock-emotion-intraday    （默认停用）盘中情绪；晚间稿用 eod
  com.user.wechat-mp-draft-scheduled 每天 18:20 公众号草稿
  com.user.docker-stacks             每 15min   保活 Docker 栈
```

### 组件职责（一句话）

| 组件 | 角色 |
|------|------|
| `stock-ai-scheduler` | 统一闹钟；容器内跑 Tushare sync |
| `host-jobs` | 本机任务执行 API（`:9876`），不负责定时 |
| `docker-stacks` | 登录后保活 Docker 栈（含 scheduler） |
| `home-hub` / `wechat-cursor-acp` | 看板、微信桥；独立常驻，不参与 cron |

---

## 3. 定时任务一览

| 任务 | 调度 | 执行位置 | 入口脚本 / 模块 |
|------|------|----------|-----------------|
| Tushare 日线同步 | 工作日 **17:30** | **容器内** | `run_sync_daily.sh` |
| 选股 + SOP + 战报落盘 | 工作日 **17:45** | 本机（经 host-jobs） | `push_selection_wechat.sh` → `run_selection_daily.sh`（**先** `ensure_daily_bars --require-ready`） |
| 东财快讯 + AI 解读 | **每 15 分钟** | 本机 launchd | `sync_macro_news.sh` → `com.user.stock-macro-news-sync` |
| 持仓 + 选股池监控 | 工作日 **每 5 分钟** | **仅** Docker → host-jobs | `push_holdings_monitor.sh`（**勿**再装 `holdings-monitor` launchd） |
| **投顾周五周复盘** | **周五 20:30** | 本机 | `push_advisor_weekly_review.sh` → MySQL + home-hub `/advisor` |
| 情绪周期 / 收盘龙头 | **18:00 eod** 容器 | `sync_emotion_cycle.sh eod` → MySQL `emotion_cycle_*` |
| 公众号草稿 | 每天 **18:20** | 本机 launchd | `wechat_mp_draft_scheduled.sh`（见 [WECHAT_MP_SCHEDULING.md](WECHAT_MP_SCHEDULING.md)） |

**已停用**：每日战报 **09 / 12 / 15 / 20** 微信推送（`install-daily-briefing-launchd.sh` 会提示废弃）；`daily_briefing_report.py` 仍可供手动/看板，定时改走快讯同步。

**监控时段**：脚本内仅 **9:30–11:30、13:00–15:00** 真正检查；非交易时段返回「跳过」exit 0。

**工作日 17:30–18:20 时序**：

```text
17:30  scheduler 容器内 sync → MySQL stock_daily 更新
17:45  scheduler curl /run/selection
         → host-jobs 执行 push_selection_wechat.sh
         → **日线门禁** `ensure_daily_bars`（期望交易日 + 当日条数≥3500；落后 Tushare by_date 补同步，仍不满足则 exit 1）
         → 四轨选股 **ProcessPool 并行**（`run_parallel_selection` 入口再次门禁；combined+watch / ma5 / 五因子 / 筑底）
         → Top5 enrich + 监控规则 sync → `output/daily_selection_full_latest.txt`（微信需 `PUSH_WECHAT=1`）
18:00  scheduler 容器内 sync_emotion_cycle.sh eod → MySQL 龙头池（依赖当日 stock_daily）
18:20  launchd 公众号 evening（sector + dragons(eod) + top5）
```

---

## 4. 安装与验证

### 安装（推荐）

```bash
cd stock-ai
# 可选：.env 增加 HOST_JOB_TOKEN=随机串（容器与 host-jobs 共用）
./scripts/install-stock-ai-scheduler.sh
```

脚本会：

1. 安装 `com.user.stock-ai-host-jobs`（KeepAlive）
2. **移除**旧 launchd plist：`daily-selection` / `daily-briefing` / `holdings-monitor` / 一次性 `watch-reminder`
3. 移除旧 `stock-daily-sync` 容器，启动 `stock-ai-scheduler`

### 验证

```bash
curl -s http://127.0.0.1:9876/health
curl -s -X POST http://127.0.0.1:9876/run/monitor -H 'Content-Type: application/json' -d '{}'
docker ps --filter name=stock-ai-scheduler
docker exec stock-ai-scheduler cat /etc/cron.d/stock-ai-scheduler
docker exec stock-ai-scheduler /bin/sh /app/docker/scheduler/run-host-job.sh monitor
```

### 回滚（恢复旧 launchd + daily-sync）

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.user.stock-ai-host-jobs.plist
docker compose -f stock-ai/docker/scheduler/docker-compose.yml down

cd stock-ai
./scripts/install-daily-selection-launchd.sh
./scripts/install-daily-briefing-launchd.sh
./scripts/install-holdings-monitor-launchd.sh
cd docker/daily-sync && docker compose up -d --build
```

---

## 5. 日志

| 日志 | 路径 |
|------|------|
| 容器 sync | `stock-ai/logs/sync_daily.log` |
| 容器触发选股/监控 | `stock-ai/logs/selection.log`、`monitor.log`、`emotion_cycle.log` |
| 本机 host-jobs 执行详情 | `stock-ai/logs/host-job-{selection\|monitor\|advisor-weekly}.log` |
| 快讯 launchd | `stock-ai/logs/launchd-macro-news-sync.{out,err}.log` |
| host-jobs launchd | `stock-ai/logs/launchd-host-jobs.{out,err}.log` |
| Docker 保活 | `tools-workspace/logs/docker-autostart.{out,err}.log` |

---

## 6. 手动试跑（不等 cron）

```bash
cd stock-ai

# 同步
./run_sync_daily.sh
docker exec stock-ai-scheduler ./run_sync_daily.sh

# 选股 / 监控（经 host-jobs，与生产一致）
curl -s -X POST http://127.0.0.1:9876/run/selection -H 'Content-Type: application/json' -d '{}'
curl -s -X POST http://127.0.0.1:9876/run/monitor -H 'Content-Type: application/json' -d '{}'

# 或直接跑脚本（调试）
./push_selection_wechat.sh
REPORT_ONLY=1 ./push_selection_wechat.sh
./sync_macro_news.sh
uv run python -m scripts.monitor.monitor_holdings_alerts --force --push

# 周五周复盘（落库 + output/advisor_weekly/）
curl -s -X POST http://127.0.0.1:9876/run/advisor-weekly -H 'Content-Type: application/json' -d '{}'
uv run python -m scripts.tools.advisor_weekly_review --save --no-ai
```

---

## 7. 仍用 launchd 的任务（非 stock-ai cron）

这些与统一调度无关，**继续由 launchd 常驻或定时**：

| Label | 作用 |
|-------|------|
| `com.user.stock-ai-host-jobs` | 本机任务 HTTP 服务 |
| `com.user.docker-stacks` | 每 15 分钟 `docker-autostart.sh` |
| `com.user.home-hub` | 投资看板 `:8780` |
| `com.user.wechat-cursor-acp` | 微信 ↔ Cursor CLI |
| `com.user.aliyun-ddns` / `sidestore-certs` / `sidestore-infra` | 基础设施 |
| `com.user.jellyfin-sd-staging-daily` | Jellyfin 导入 |
| `com.user.stock-macro-news-sync` | 每 15 分钟快讯 + AI 解读 |
| `com.user.stock-emotion-intraday` | **默认不安装**；盘中 OpenCLI（`INSTALL_EMOTION_INTRADAY=1` 启用） |
| `com.user.wechat-mp-draft-scheduled` | 每日 18:20 公众号草稿 |
| `com.user.wechat-mp-whitelist-check` | 公众号 IP 白名单（每小时） |

**勿安装**：`com.user.stock-holdings-monitor`（与 Docker `*/5 monitor` 重复）；`com.user.stock-ai-daily-selection`（改由 scheduler 17:45）。

Plist 源文件：`tools-workspace/launchd/`。快讯安装：`cp launchd/com.user.stock-macro-news-sync.plist ~/Library/LaunchAgents/ && launchctl bootstrap …`

---

## 8. 配置项

| 变量 | 说明 | 默认 |
|------|------|------|
| `HOST_JOB_PORT` | host-jobs 监听端口 | `9876` |
| `HOST_JOB_BIND` | 绑定地址 | `127.0.0.1`（容器访问需 `host.docker.internal`） |
| `HOST_JOB_TOKEN` | 可选鉴权头 `X-Job-Token` | 空（不校验） |
| `HOST_JOB_HOST` | 容器内 curl 目标 | `host.docker.internal` |

详见 `stock-ai/.env.example`。

---

## 9. 已知坑与修复记录

| 问题 | 原因 | 处理 |
|------|------|------|
| 监控 exit 127 | launchd 环境无 `uv` | `push_holdings_monitor.sh`、`start-host-jobs.sh` 增加 `~/.local/bin` 到 PATH |
| 容器 cron 触发失败 | `run-host-job.sh` 用了 bash 数组，cron 用 `/bin/sh` | 改为 POSIX sh 写法 |
| Docker 构建 403 | 镜像源偶发失败 | 先 `docker pull python:3.12-slim-bookworm` 再 build |
| 17:45 选股 exit 1、无新 Top5 | `ensure_daily_bars` 日线未就绪 | `uv run python -m scripts.tools.ensure_daily_bars`；补 sync：`--sync-if-stale --require-ready`；或等 17:30 容器 sync 完成；调试 `SKIP_DAILY_BARS_CHECK=1` |
| 18:00 龙头 eod 无数据 | 容器 `uv` 路径或日线未入库 | 查 `logs/emotion_cycle.log`；本机 `./sync_emotion_cycle.sh eod`；重建 scheduler 镜像 |
| 选股/推送 exit 1 但数据已入库 | `微信 API ret=-2` context_token 过期 | 给 wechat-acp 机器人发一条消息后重试；查 `~/.wechat-acp/instances/tools-workspace/token.json` |
| 快讯/情绪 OpenCLI 超时 | 监控+快讯+intraday 并发占浏览器 | 勿恢复 `holdings-monitor` launchd；错开高峰或重跑 `./sync_macro_news.sh` |
| `selection.log` curl 500 | host-jobs 并发或脚本 exit≠0 | 看 `logs/host-job-selection.log` 末尾；避免同时手动+ cron 触发 |

---

## 10. 与 Home Hub 任务页

Home Hub `/jobs` 当前仍扫描 **launchd plist**（`load_launchd_jobs`），展示 host-jobs、home-hub、wechat 等常驻项；**Docker scheduler 内 crontab 尚未在 Hub 展示**。排查 scheduler 请用本文 §5 日志与 `docker logs stock-ai-scheduler`。

---

## 11. 相关路径

| 路径 | 说明 |
|------|------|
| `docker/scheduler/` | Dockerfile、crontab、compose |
| `scripts/scheduler/host_job_server.py` | host-jobs 实现 |
| `scripts/install-stock-ai-scheduler.sh` | 一键安装 |
| `launchd/com.user.stock-ai-host-jobs.plist` | host-jobs launchd |
| `scripts/docker-autostart.sh` | 登录后拉起 scheduler 栈 |
| `docker/daily-sync/` | **已合并**，仅保留兼容说明 |
| `launchd/com.user.wechat-mp-draft-scheduled.plist` | 公众号草稿：每日 18:20 |
| `scripts/wechat_mp_draft_scheduled.sh` | 每日 18:20 批次入口（自动交易日/休市日） |
| `scripts/tools/wechat_mp_draft_batch.py` | 工作日 `evening` · 周末 `weekend`(news) |

安装：`cd stock-ai && bash scripts/install-wechat-mp-launchd.sh`（仅 `com.user.wechat-mp-draft-scheduled` + 白名单监控）。

*最后更新：2026-06-03*
