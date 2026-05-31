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
launchd 17:30 选股
launchd 09/12/15/20 简报
launchd 每 5 分钟 监控
Docker stock-daily-sync 17:00 同步
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
│  17:00  sync      → run_sync_daily.sh（容器内，MySQL via host.docker.internal）    │
│  17:30  selection → run-host-job.sh                                               │
│  09/12/15/20      → run-host-job.sh briefing                                       │
│  */5 工作日       → run-host-job.sh monitor                                        │
└───────────────────────────────┬───────────────────────────────────────────────────┘
                                │ HTTP POST host.docker.internal:9876/run/{job}
                                ▼
┌──────────────────── 本机 host-jobs (launchd com.user.stock-ai-host-jobs) ─────────┐
│  host_job_server.py → push_selection_wechat.sh                                     │
│                    → push_daily_briefing_wechat.sh                                 │
│                    → push_holdings_monitor.sh                                      │
└────────────────────────────────────────────────────────────────────────────────────┘

launchd com.user.docker-stacks（每 15 分钟）
  └─ scripts/docker-autostart.sh → compose up scheduler / mysql / …
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
| Tushare 日线同步 | 工作日 **17:00** | **容器内** | `run_sync_daily.sh` |
| 选股 + SOP + 战报 | 工作日 **17:30** | 本机（经 host-jobs） | `push_selection_wechat.sh` |
| 每日战报 | 每天 **09 / 12 / 15 / 20:00** | 本机 | `push_daily_briefing_wechat.sh` |
| 持仓 + 选股池监控 | 工作日 **每 5 分钟** | 本机 | `push_holdings_monitor.sh` → `monitor_holdings_alerts` |

**监控时段**：脚本内仅 **9:30–11:30、13:00–15:00** 真正检查；非交易时段返回「跳过」exit 0。

**周一 17:00–17:30 时序**：

```text
17:00  scheduler 容器内 sync → MySQL stock_daily 更新
17:30  scheduler curl /run/selection
         → host-jobs 执行 push_selection_wechat.sh
         → 选股 + SOP + 监控规则 sync + 收盘战报 → 微信
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
2. **停用**旧 launchd：`daily-selection` / `daily-briefing` / `holdings-monitor`
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
| 容器触发选股/简报/监控 | `stock-ai/logs/selection.log`、`briefing.log`、`monitor.log` |
| 本机 host-jobs 执行详情 | `stock-ai/logs/host-job-{selection\|briefing\|monitor}.log` |
| host-jobs launchd | `stock-ai/logs/launchd-host-jobs.{out,err}.log` |
| Docker 保活 | `tools-workspace/logs/docker-autostart.{out,err}.log` |

---

## 6. 手动试跑（不等 cron）

```bash
cd stock-ai

# 同步
./run_sync_daily.sh
docker exec stock-ai-scheduler ./run_sync_daily.sh

# 选股 / 战报 / 监控（经 host-jobs，与生产一致）
curl -s -X POST http://127.0.0.1:9876/run/selection -H 'Content-Type: application/json' -d '{}'
curl -s -X POST http://127.0.0.1:9876/run/briefing -H 'Content-Type: application/json' -d '{"slot":"15:00"}'
curl -s -X POST http://127.0.0.1:9876/run/monitor -H 'Content-Type: application/json' -d '{}'

# 或直接跑脚本（调试）
./push_selection_wechat.sh
REPORT_ONLY=1 ./push_selection_wechat.sh
FETCH_ONLY=1 ./push_daily_briefing_wechat.sh 15:00
uv run python -m scripts.monitor.monitor_holdings_alerts --force --push
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
| `com.user.stock-watch-reminder-*` | 一次性提醒（按需） |

Plist 源文件：`tools-workspace/launchd/`。

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

*最后更新：2026-05-31*
