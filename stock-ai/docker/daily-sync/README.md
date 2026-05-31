# 日线同步定时任务（已合并）

> **已废弃独立部署**。Tushare 17:00 同步现由 **`docker/scheduler`** 统一调度。  
> 请改用：[../scheduler/README.md](../scheduler/README.md) 或 `./scripts/install-stock-ai-scheduler.sh`。

---

## 迁移说明

| 旧 | 新 |
|----|-----|
| `stock-daily-sync` 容器 | `stock-ai-scheduler` 容器内 17:00 cron |
| `docker/daily-sync/docker compose up` | `docker/scheduler/docker compose up` |
| 仅 sync | sync + 选股/战报/监控触发 |

本目录 Dockerfile / compose **保留兼容**，新环境勿再引用。

---

## 历史：独立 daily-sync 用法

工作日 **17:00（Asia/Shanghai）** 执行 `run_sync_daily.sh`。

```bash
# 不推荐 — 仅回滚或对照
cd stock-ai/docker/daily-sync
docker compose up -d --build
docker compose logs -f stock-daily-sync
tail -f ../../logs/sync_daily.log
```

*最后更新：2026-05-31*
