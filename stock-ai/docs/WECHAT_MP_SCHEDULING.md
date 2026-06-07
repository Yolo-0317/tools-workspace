# 微信公众号草稿 · 定时调度

> 写作与合规见 `.cursor/skills/wechat-mp-drafts/`；**晚间三篇模板**见 `evening-trilogy-templates.md`。批次配置：`scripts/tools/wechat_mp_draft_batch.py` → `SCHEDULE_BATCHES`。

## 每日 18:20（launchd `com.user.wechat-mp-draft-scheduled`）

| 日历 | batch | 篇数 | 推送 kinds | 备注 |
|------|-------|------|------------|------|
| **A 股交易日** | `evening` | 3 | `sector` + `dragons` + `top5` | 行业→龙头→选股；`edition=close`；龙头 `eod` |
| **休市日（周日/法定节假日）** | `weekend` | 1 | `news` | 近 **72h** 快讯 **12 条**，**个股/公司优先**；标题/摘要偏周末要闻 |
| **周六休市** | `weekend_skip` | 0 | — | 不推草稿（周日再发长窗口要闻） |

交易日判定：周末恒休市；工作日查 `data/a_share_trade_cal.json`（无 token 时工作日暂按开市，避免定时任务误跳过）。

**不在定时里的槽**：`market`、`news`、`workspace`、`temp` — 手动 `wechat_mp_draft --kind market|news|…`。

## 按日跳过定时写稿

草稿已手写、仅需后台定时发表时，避免 18:20 launchd 覆盖草稿：

```bash
# 跳过「今天」（Asia/Shanghai 日历日）
echo "$(TZ=Asia/Shanghai date +%Y-%m-%d)" > stock-ai/data/wechat_mp_skip_scheduled.date
# 恢复：rm stock-ai/data/wechat_mp_skip_scheduled.date
```

`wechat_mp_draft_scheduled.sh` 读到日期与当天一致则 exit 0，**不卸** launchd，次日自动恢复。

## 安装与日志

```bash
cd stock-ai
bash scripts/install-wechat-mp-launchd.sh   # 安装 18:20 任务 + 白名单监控；卸载旧 morning/noon/evening
bash scripts/wechat_mp_draft_scheduled.sh              # 按今天日历自动选 batch
bash scripts/wechat_mp_draft_scheduled.sh --dry-run
uv run python -m scripts.tools.wechat_mp_draft_batch --batch weekend --dry-run
```

| 日志 | 路径 |
|------|------|
| 定时 | `logs/launchd-wechat-mp-draft-scheduled.{out,err}.log` |

plist 源文件：`tools-workspace/launchd/com.user.wechat-mp-draft-scheduled.plist`。

## 流水线（每篇）

1. `build_article` → 合规 `check_public_compliance`（默认 `WECHAT_MP_STRICT_COMPLIANCE=1` 不过则不推）
2. `upsert_draft_article`（日更五槽 JSON：`data/wechat_mp_draft_slots.json`）
3. 批次末 `prune_obsolete_drafts`
4. 至少 1 篇成功 → `wechat_mp_draft_notify`（微信 wechat-acp + 飞书）

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `WECHAT_MP_APPID` / `SECRET` | — | 草稿 API 必填 |
| `WECHAT_MP_STRICT_COMPLIANCE` | `1` | 合规未过跳过推送 |
| `WECHAT_MP_NOTIFY` | `1` | 批次通知总开关 |
| `WECHAT_MP_NOTIFY_WECHAT` | `1` | 需 `WECHAT_ACP_INSTANCE`、`WECHAT_TARGET` |
| `WECHAT_MP_NOTIFY_FEISHU` | `1` | `FEISHU_BOT_URL` |
| `WECHAT_MP_DRAGON_SLOT` | 由批次设置 | 工作日 `evening` → `eod` |

## 发布提醒

API 无法代勾 **原创** 与 **话题 `#`**；审阅在 mp.weixin.qq.com 草稿箱后人工发布。

*确立：2026-06-02 · 修订：2026-06-07（18:20；休市日 news）*

预热交易日历（可选）：

```bash
cd stock-ai
uv run python -c "from stock_ai.trading_calendar import refresh_trade_cal_cache; print(refresh_trade_cal_cache())"
```
