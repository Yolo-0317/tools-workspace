# emquant-sim — Agent 指南

东财掘金 **仿真量化** 专用子项目，与 `stock-ai` **解耦**。

> **2026-06-02 已下线**（专业投资者 / 约 300w 门槛）：默认 `EMQUANT_ENABLED=0`。勿主动 deploy/push；情绪周期 MySQL 与 home-hub 继续由 stock-ai 维护。见 [OFFLINE.md](OFFLINE.md)。

## 禁止

- 不要在 `stock-ai` 下新增/修改掘金策略、`scripts/win/`、`.env.emquant`
- 不要改 `stock-ai` 的 scheduler、选股入库、监控脚本来服务仿真下单

## 允许只读使用 stock-ai

- 读 `stock-ai/investment-agent/持仓执行卡.md` → `export_emquant_rules`（主轨 `main_combined` 可选）
- 读 MySQL `emotion_cycle_*` + **`龙头执行卡.md`** → `export_emotion_dragons`（**龙头轨，当前默认**）
- （可选）读 MySQL `portfolio_positions` → `export_emquant_targets`（旧桥接，默认不用）

## 双执行卡（勿混）

| 卡 | 用途 |
|----|------|
| `持仓执行卡.md` | 实盘纪律；stock-ai 微信监控 / `alert_rules` |
| `龙头执行卡.md` | **仅本仓库仿真**；`dragon_main` + `dragons.json` |

## 工作流

1. 改 **实盘** 卡 → stock-ai `sync_portfolio_from_card` + 可选 `export_emquant_rules`
2. 改 **龙头** 纪律或等 emotion 入库 → `export_emotion_dragons` + `deploy_emquant_strategy.sh`
3. Win11 终端运行（`strategy_entry.json` 选 `dragon` | `combined`）

## 路径

根目录：`tools-workspace/emquant-sim`

## 文档（优先）

1. **`docs/PLAYBOOK.md`** — 架构、日常命令、排障、股数、Mac 读 Win11 日志  
2. `docs/emquant-sim-bridge.md` — 策略逻辑  
3. `docs/emquant-strategy-not-running.md` — 未运行 checklist  
4. `.cursor/rules/memory-emquant.mdc` — Hermes 专项记忆
