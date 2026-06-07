# 东财掘金量化 — 已下线（2026-06-02）

**原因**：东财量化终端面向**个人专业投资者**（一般需满足约 **300 万**资产等门槛），当前不再维护自动仿真下单链路。

## 仍可用

| 能力 | 位置 |
|------|------|
| 情绪周期 / 龙头池 | `stock-ai` → MySQL → home-hub `/emotion` |
| 实盘纪律 | `持仓执行卡.md`、微信监控、看板持仓 |
| 本目录代码 | 保留备查，**默认不部署、不推送** |

## 如何恢复（若以后满足门槛）

1. `emquant-sim/.env.emquant` 设 `EMQUANT_ENABLED=1`
2. Win11 打开掘金终端 → 仿真户 → 停止旧策略
3. `export_emotion_dragons` / `deploy_emquant_strategy.sh` 按需手动执行

## 开关

```bash
# .env.emquant
EMQUANT_ENABLED=0   # 0=下线（默认）  1=启用 deploy/push/自动同步
```

自动推送入口：`stock-ai/sync_emotion_cycle.sh`（入库成功后）；关闭 `EMQUANT_ENABLED` 后仅写 MySQL，不再推 Win11。
