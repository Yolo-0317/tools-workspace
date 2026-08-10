# 微信公众号草稿 · 定时调度

> 写作与合规见 `.cursor/skills/wechat-mp-drafts/`；批次配置：`scripts/tools/wechat_mp_draft_batch.py` → `SCHEDULE_BATCHES`。
> 公司电脑独立写稿（不装定时、不接 MySQL）见 [WECHAT_MP_COMPANY_SETUP.md](WECHAT_MP_COMPANY_SETUP.md)。

## 公众号写稿定时（2026-08-06 起暂停）

| 时刻 | 触发 | batch | 篇数 | kinds | edition | 说明 |
|------|------|-------|------|-------|---------|------|
| 暂停 | Docker scheduler → host-jobs `wechat-mp-hotspot-early` | `hotspot_early` | 1 | `hotspot` | `pre` | 恢复前不会自动写草稿 |
| 暂停 | `wechat-mp-hotspot-morning` | `hotspot_morning` | 1 | `hotspot` | `pre` | 同上 |
| 暂停 | `wechat-mp-hotspot-afternoon` | `hotspot_afternoon` | 1 | `hotspot` | `midday` | 同上 |
| 暂停 | `wechat-mp-hotspot-evening` | `hotspot_evening` | 1 | `hotspot` | `close` | 同上 |

四篇分槽任务已从生产 crontab 注释；仍可手动运行对应命令写草稿。恢复时取消 `docker/scheduler/crontab` 的四行注释并重建 scheduler 容器。

**已移出定时**（仍可手动）：

- `tv_trial` / 11:00 话题讨论稿 → `bash scripts/wechat_mp_tv_draft_scheduled.sh` 或 `wechat_mp_draft_batch --batch tv_trial`
- 18:00 `evening` / `weekend` 财经三篇
- 15:15 股吧 guba

## 命令

```bash
cd stock-ai
bash scripts/wechat_mp_hotspot_draft_scheduled.sh hotspot_early --dry-run
bash scripts/wechat_mp_hotspot_draft_scheduled.sh hotspot_morning --dry-run
bash scripts/wechat_mp_hotspot_draft_scheduled.sh hotspot_afternoon --dry-run
bash scripts/wechat_mp_hotspot_draft_scheduled.sh hotspot_evening --dry-run

# host-jobs 手动触发
curl -s -X POST http://127.0.0.1:9876/run/wechat-mp-hotspot-early -H 'Content-Type: application/json' -d '{}'
curl -s -X POST http://127.0.0.1:9876/run/wechat-mp-hotspot-morning -H 'Content-Type: application/json' -d '{}'
curl -s -X POST http://127.0.0.1:9876/run/wechat-mp-hotspot-afternoon -H 'Content-Type: application/json' -d '{}'
curl -s -X POST http://127.0.0.1:9876/run/wechat-mp-hotspot-evening -H 'Content-Type: application/json' -d '{}'
```

| 项 | 说明 |
|----|------|
| 交易日 | **不限制**；休市日同样推 4 篇 |
| 选题 | `WECHAT_MP_HOTSPOT_SOURCE=trends`（微博+百度热搜） |
| 跳过 | `data/wechat_mp_skip_scheduled.date` 内容为 `YYYY-MM-DD` 则**四时段全跳过**；单槽跳过：`data/wechat_mp_skip_hotspot_morning.date` 等（仅跳过对应 batch） |
| 日志 | `logs/host-job-wechat-mp-hotspot-*.log` · 容器 `logs/wechat_mp_hotspot_*.log` |

## 按日跳过定时写稿

```bash
echo "$(TZ=Asia/Shanghai date +%Y-%m-%d)" > stock-ai/data/wechat_mp_skip_scheduled.date
# 恢复：rm stock-ai/data/wechat_mp_skip_scheduled.date
```

## 安装与 host-jobs

```bash
cd stock-ai
bash scripts/install-wechat-mp-launchd.sh
bash scripts/install-stock-ai-scheduler.sh  # host-jobs + Docker scheduler
```

重建 scheduler 容器后 crontab 生效：`docker compose -f docker/scheduler/docker-compose.yml up -d --build`

## 流水线（每篇）

1. `build_article(kind=hotspot, edition=…)` → 合规 `audit_recommendation_safety`
2. `upsert_draft_article`（分槽 `hotspot_early` / `morning` / `afternoon` / `evening`）
3. 批次末 `prune_obsolete_drafts`
4. 至少 1 篇成功 → `wechat_mp_draft_notify`（微信 + 飞书）

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `WECHAT_MP_HOTSPOT_SOURCE` | `trends` | 四时段默认热搜选题 |
| `WECHAT_MP_HOTSPOT_TOPIC` | — | 手动指定选题（调试用） |

## 发布提醒

个人号每天仅 **1 次通知**；多篇须**同批群发**。API 无法代勾原创与 `#`；审阅草稿箱后人工发布。

*修订：2026-08-05（新增 09:00 hotspot_early；11/15/18 不变）*
