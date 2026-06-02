# 选股策略说明（精简）

> 17:30 自动化默认使用 **综合选股**（`core_v2/stock_selection_combined.py`）。  
> 以下为单策略脚本的核心逻辑，供手动研究对比。

---

## 策略一：量价齐升突破

**脚本**：`scripts/selection/stock_selection.py`  
**输出**：`output/stock_selection_YYYYMMDD.csv`

| 类别 | 条件 |
|------|------|
| 基础 | 沪深 A 股；5～30 元；成交额 > 5000 万；≥65 日历史 |
| 涨幅 | 当日 3%～9% |
| 量能 | 量比 > 1.5（相对近 5 日均量） |
| 趋势 | 收盘 > MA5 > MA20 > MA60 |
| 防追高 | 近 5 日累计涨幅 < 20% |
| 排序 | 量比降序 |

**适用**：放量突破、短中线波段；偏启动点。

```bash
uv run python scripts/selection/stock_selection.py
uv run python scripts/selection/stock_selection.py --date 20260529
```

---

## 策略二：沿 MA5 回踩买入

**脚本**：`scripts/selection/stock_selection_ma5.py`  
**输出**：`output/stock_selection_ma5_YYYYMMDD.csv`

| 类别 | 条件 |
|------|------|
| 基础 | 同策略一 |
| 乖离 | 收盘相对 MA5：-2%～+1%（贴近 MA5） |
| K 线 | 当日收阳 |
| 强势 | 近 5 日至少 3 日收在 MA5 上方 |
| 趋势 | MA5 向上 |
| 排序 | 乖离率升序（越贴近 MA5 越靠前） |

**适用**：趋势中低吸；止损参考 MA5。

```bash
uv run python scripts/selection/stock_selection_ma5.py
```

---

## 策略三：综合选股（生产默认）

**脚本**：`core_v2/stock_selection_combined.py`  
**输出**：`output/stock_selection_combined_YYYYMMDD.csv`

多标签合并（如大底突破、早埋伏等），按总分 / 标签数 / 成交额排序。17:30 流程取 Top5 做 SOP + DeepSeek。

**数据单位（2026-06-01）**：MySQL `amount` 为 Tushare **千元**；过滤门槛 `50000` 千元 = **5000 万**；CSV 列 `成交额(万)` 为万元。Top5 默认仅 `强势关注/观察买入/小仓埋伏`（不足时回退）。

**阶段 E（2026-06-02）**：大盘 `weak/neutral/strong` 动态门槛；突破过滤长上影；非持仓单日 >5% 强制继续观察。

**买入档位（2026-06-01，对齐 `持仓执行卡.md` 买入决策 2.0）**：

| 总仓位 | 非持仓 `建议动作` |
|--------|-------------------|
| >75% | 买入类 → **继续观察** |
| 60～75% | **强势关注/观察买入** → **小仓埋伏**；执行卡 P-买1/买2（000543、603697）在池内同步标「小仓埋伏」 |
| ≤60% | 按评分保留买入类（仍禁单日 >5% 追高） |

**双轨 + 并行（2026-06-02）**：

| strategy | 脚本 | 用途 |
|----------|------|------|
| `combined` | `core_v2/stock_selection_combined.py` | **A轨** → Top5 + SOP |
| `watch` | `core_v2/selection_watch_track.py` | **B轨** 观察池（≤30），不推 Top5 |
| `ma5` | `scripts/selection/stock_selection_ma5.py` | MA5 回踩，辅助池 |
| `five_factor` | `core_v3/stock_selection_five_factor_mysql.py` | 五因子，辅助池 |
| `bottom_breakout` | `core_v2/stock_selection_bottom_breakout_eastmoney.py` | **筑底+放量突破**，辅助池 |

17:30 入口：`run_selection_daily.sh` → `run_parallel_selection` → `daily_selection_report --skip-selection`。

详见 `docs/specs/2026-06-01-selection-da-design.md`。

```bash
uv run python core_v2/stock_selection_combined.py
# 或
./run_selection_daily.sh
```

---

## 策略四：五因子（v3）

**脚本**：`core_v3/stock_selection_five_factor_mysql.py`  
细则见 [pipelines/strategy.md](pipelines/strategy.md)。

---

## 策略五：筑底 + 放量突破（17:30 并行第 ④ 轨）

**脚本**：`core_v2/stock_selection_bottom_breakout_eastmoney.py`  
**MySQL**：`selection_daily_results` · `strategy=bottom_breakout`  
**输出**：`output/stock_selection_bottom_breakout_eastmoney_YYYYMMDD.csv`

| 阶段 | 条件 |
|------|------|
| 筑底 | 股价贴近 MA60（0.95～1.05）、MA60 斜率 > -1%、近 20 日量 / 前 60 日量 < 0.7、近 10 日振幅 < 15% |
| 放量突破 | 今日量 / 5 日量 ≥ **1.5**、今收 / 昨收 ≥ **1.03**；且突破 **MA60** 或 **20 日高点** 或 **平台** |

```bash
uv run python -m scripts.selection.run_parallel_selection   # 含本策略
# 或单独
uv run python core_v2/stock_selection_bottom_breakout_eastmoney.py 20260602
```

---

## 策略五（旧）：底部启动（月线+日线，手动研究）

**脚本**：`scripts/selection/stock_selection_bottom_breakout.py`（**未**接入 17:30 并行）

---

## 盘后 AI 审查

选股 CSV 生成后，可选 DeepSeek / SOP，见 [pipelines/daily_stock_deepseek_pipeline.md](pipelines/daily_stock_deepseek_pipeline.md)。

*最后更新：2026-06-02*
