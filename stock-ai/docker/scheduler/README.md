# stock-ai 统一调度（Docker）

将 **Tushare 同步** 与 **投资定时任务** 收到一个 Docker 容器（supercronic），替代多个 launchd plist + 独立 `stock-daily-sync` 容器。

**完整设计说明**：[docs/SCHEDULING.md](../../docs/SCHEDULING.md)（架构原因、时序、日志、回滚）。

---

## 架构（简图）

```text
stock-ai-scheduler (Docker)
  ├─ 17:30 sync · 18:00 emotion eod（容器内）
  └─ 17:45 selection · 周五 advisor-weekly → host-jobs :9876
launchd（勿与 monitor 重复）
  ├─ macro-news-sync（15min）
  └─ wechat-mp-draft-scheduled（19:00）
```

---

## 安装

```bash
cd stock-ai
# 可选：.env 增加 HOST_JOB_TOKEN=你的随机串
./scripts/install-stock-ai-scheduler.sh
```

会：

1. 安装 `com.user.stock-ai-host-jobs`（KeepAlive）
2. **移除**旧 plist：`daily-selection` / `daily-briefing` / `holdings-monitor`（监控仅走 Docker）
3. 移除旧 `stock-daily-sync` 容器，启动 `stock-ai-scheduler`

---

## 手动启停

```bash
cd stock-ai/docker/scheduler
docker compose up -d --build    # 启动 / 重建
docker compose logs -f          # 日志
docker compose down             # 停止
```

登录后 `com.user.docker-stacks` 也会幂等 `compose up` 本目录。

---

## 验证

```bash
curl -s http://127.0.0.1:9876/health
curl -s -X POST http://127.0.0.1:9876/run/monitor -H 'Content-Type: application/json' -d '{}'
curl -s -X POST http://127.0.0.1:9876/run/emotion-intraday -H 'Content-Type: application/json' -d '{}'
launchctl print gui/$(id -u)/com.user.stock-emotion-intraday
```

---

## crontab 摘要

| 时间 | 任务 |
|------|------|
| 工作日 17:30 | Tushare → MySQL |
| 工作日 17:45 | 选股 + SOP + 战报 |
| 工作日 18:00 | 收盘龙头 eod → MySQL |
| 每天 09/12/15/20 | 战报 |
| 工作日 */5 | 持仓监控（交易时段内脚本才生效） |

完整表达式见 `crontab`。

---

## 回滚

见 [docs/SCHEDULING.md §4](../../docs/SCHEDULING.md#4-安装与验证)。

---

## 与 daily-sync 关系

`docker/daily-sync/` 已合并进本目录；`scripts/docker-autostart.sh` 改为拉起 `docker/scheduler`。勿再单独起 `stock-daily-sync`。
