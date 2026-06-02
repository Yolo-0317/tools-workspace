# emquant-sim — 东财掘金仿真量化（独立子项目）

与 **`stock-ai`** 隔离：不改选股调度、MySQL 同步、微信监控等现有能力。

## 边界

| 项目 | 职责 |
|------|------|
| **stock-ai** | 执行卡、MySQL、综合选股脚本、盘中微信监控、Tushare |
| **emquant-sim** | Win11 掘金终端策略、`gm.api` 仿真下单、规则导出与部署 |

只读依赖：`export_emquant_rules` 读取 `../stock-ai/investment-agent/持仓执行卡.md`（解析逻辑在 stock-ai，本仓库不复制）。

## 快速开始

```bash
cd emquant-sim
cp config/emquant.env.example .env.emquant   # 填 Token / 策略 ID

# 在 emquant-sim 目录执行（会只读加载 ../stock-ai 的执行卡解析器）
PYTHONPATH=. python3 -m scripts.tools.export_emquant_rules
./scripts/win/deploy_emquant_strategy.sh <策略UUID>

PYTHONPATH=. python3 -m scripts.tools.probe_emquant   # Mac 仅测端口/配置
```

`.env.emquant` 已从 `stock-ai/` 迁到本目录；勿再放回 stock-ai。

终端：**仿真** → 关联仿真户 → **运行**。

## 目录

| 路径 | 说明 |
|------|------|
| `scripts/win/stock_ai_sim_bridge/` | 策略源码（综合选股 + 60s 执行卡规则；**dragon_main 龙头战法**） |
| `scripts/win/deploy_emquant_strategy.sh` | 部署到 Parallels Win11 |
| `output/emquant/rules.json` | 由执行卡导出 |
| `docs/emquant-sim-bridge.md` | 策略说明 |

## 文档

| 文档 | 用途 |
|------|------|
| **[docs/PLAYBOOK.md](docs/PLAYBOOK.md)** | **运维手册**：边界、日常流程、排障、股数配置、API 读日志 |
| [docs/emquant-dragon-strategy.md](docs/emquant-dragon-strategy.md) | **龙头战法**仿真（dragons.json ← MySQL 龙头池） |
| [docs/emquant-strategy-not-running.md](docs/emquant-strategy-not-running.md) | 终端未运行 / 无控制台输出 |
| [AGENTS.md](AGENTS.md) | Agent 禁止项与路径 |

与 **stock-ai** 关系：只读 `持仓执行卡.md` → `rules.json`；仿真仓、下单、持仓判断均在 Win11，不经过 stock-ai scheduler。
