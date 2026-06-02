# 龙头战法仿真策略（dragon_main.py）

独立 **游资轨** 验证：读 Mac 导出的 `dragons.json`（MySQL `emotion_cycle_dragon_watch`），在东财掘金 **仿真户** 按情绪阶段 gate 买卖。

与 `main_combined.py`（原综合选股+执行卡）**并存**；终端仍运行 **`main.py`**，由 `strategy_entry.json` 切换。

## 入口切换（无需改策略 ID / 终端运行文件）

| `strategy_entry.json` | 实际逻辑 |
|------------------------|----------|
| `"entry": "dragon"` | `dragon_main.py`（**默认**） |
| `"entry": "combined"` | `main_combined.py` |

策略 ID 不变（`.env.emquant` → `5aa6af16-…`），部署时一并推送 `strategy_entry.json`。

## 数据流

```text
stock-ai sync_emotion_cycle → MySQL emotion_cycle_*
        ↓ Mac 导出
export_emotion_dragons → output/emquant/dragons.json
        ↓ deploy
Win11 策略目录 dragons.json → dragon_main.py 09:31 加载
```

## 买卖逻辑（增强试探版 v2，对齐 情绪周期日检卡.md）

| 项 | 规则 |
|----|------|
| **数据源** | `dragons.json` 最多 3 只龙头 + `header.phase` 等 |
| **龙位** | 启动只做 #1；发酵 #1+#2；高潮三只 |
| **允许买** | 阶段 ∈ 启动/发酵/高潮；`allow_new_open`；溢价≥1%；炸板率<40% |
| **结构买点** | **re-seal**（触板→回落≥2%→再转强）；**pullback**（分时回踩）；**weak2strong**（10:00 后弱转强） |
| **禁止买** | 09:30–09:45 开盘接力；≥3 板且已涨≥7%；一字板；冰点/退潮/分歧 |
| **仓位** | #1 40% / #2 25% / #3 15% × `position_cap_pct` × NAV，整手 |
| **卖** | 破板（曾触板现<5%）；+7% 减半；+10% 清仓；≤-5% 止损；退潮清仓；≥5 日时间止损 |

> 仿真用 60s K 线近似「回封/分歧转一致」，**不等于** 真实打板排队；v2 在试探版上加了 **结构触发 + 分档仓位 + 止盈**。

### 日志关键字（v2）

- `[dragon] mode=v2 enhanced-probe` — 启动确认版本  
- `[dragon] BUY/re-seal` / `BUY/pullback` / `BUY/weak2strong` — 结构买点  
- `[dragon] EXIT_HALF take_profit_half` — 浮盈 7% 减半  
- `[dragon] EXIT broken_board` — 破板清仓  

## 日常流程

### 1. Mac：情绪日检入库后导出龙头池

```bash
cd /Users/yolo/dev/yolo/tools-workspace/emquant-sim

# 可选：确认 stock-ai 已 sync（scheduler 17:10 或手动 ./sync_emotion_cycle.sh eod）
PYTHONPATH=. python3 -m scripts.tools.export_emotion_dragons
# 盘前验证用：--slot pre_market
```

### 2. 部署到 Win11

```bash
./scripts/win/deploy_emquant_strategy.sh <策略UUID>
```

### 3. 掘金终端

1. **仿真** → 关联仿真户  
2. 策略 **仍运行 `main.py`**（已改为路由；`strategy_entry.json` 当前为 `dragon`）  
3. **停止 → 再运行**

每个交易日 **09:31 前** 完成 export+deploy；策略 **每 5 分钟** 重读 `dragons.json`（与 Mac intraday 同步）。

## 文件

| 文件 | 作用 |
|------|------|
| `dragon_main.py` | 掘金入口：订阅龙头、on_bar 买卖 |
| `dragon_head_gm.py` | 阶段 gate、进出场判定 |
| `dragons.json` | MySQL 龙头池 + 情绪 header（部署产物） |
| `scripts/tools/export_emotion_dragons.py` | Mac 导出 |

## 与主轨关系

- **不替代** `main.py` 综合选股 + 执行卡  
- **冲突时**仍以 `持仓执行卡.md` 为准（主账户纪律）  
- 仿真户单独验证游资轨；当前若 `phase=退潮`，策略 **只卖不买**（与看板一致）

## 日志关键字

- `[dragon] reload (updated)` — 5min 重载且池/阶段有变化  
- `[dragon] BUY` / `EXIT` / `SESSION_EXIT` — 仿真成交意图  
- `open=False phase=退潮` — 正常 gate，非 bug
