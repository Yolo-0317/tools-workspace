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

## 策略五：底部突破（东财）

**脚本**：`scripts/selection/stock_selection_bottom_breakout.py`

---

## 盘后 AI 审查

选股 CSV 生成后，可选 DeepSeek / SOP，见 [pipelines/daily_stock_deepseek_pipeline.md](pipelines/daily_stock_deepseek_pipeline.md)。

*最后更新：2026-05-30*
