# 热门行业/主题 · 自动挖掘（非写死科技股）

> 代码真源：`stock-ai/scripts/tools/wechat_mp_hot_theme.py`  
> 科技股、半导体、CPO 等仅为**词表示例**；真正出稿主线由当日数据投票决定。

## 原则

- **不同交易日、不同热点**：电力、煤炭、油价、黄金、地产等都会出现，与情绪周期、快讯、选股、板块涨幅一致时才上浮。
- **行业研究稿（未来 `sector` 槽）** 与 **龙头/选股** 共用同一 `primary` 主题，便于搜一搜长尾与账号垂直标签。
- 勿在 skill 或 prompt 里写死「每天写科技」。

## 信号来源（`sector` 专用）

| 优先级 | 来源 | 说明 |
|--------|------|------|
| **1** | **东财行业板块涨幅榜** | OpenCLI `fetch_hot_industry_sectors_opencli`；写草稿时默认必拉；榜一/榜二 → 正文 1～2 行业 |
| 2（仅榜失败） | 快讯 + 选股行业 | **不**读情绪周期、**不**读龙头池 `main_theme` |

**top5 候选（流量优先，2026-06-05）**：默认 **东财 A 股人气榜** Top10 → 过滤 ST/禁码 → 取 5 → 快采 SOP 成稿（`WECHAT_MP_TOP5_POOL=hot`）；失败回退多策略选股。搜一搜用户常搜票名，标题领衔股与榜一一致。

**sector 代表股（搜一搜长尾，2026-06-05）**：`wechat_mp_sector_stocks` 合并 **行业 JSONP 领涨股** + **人气榜同行业** + 龙头池/选股观察 → 喂给「盘面里谁在用价格说话」（默认最多 4 只、每主题 ≤2）。

**sector 标题（2026-06-07 周报）**：有代表股时优先 `A股{主线}｜{领涨股}领涨：产业链怎么拆？`（对齐搜一搜真实搜词：新安股份、合锻智能等）；`dragons`/`top5` 句式本周勿动。

| 环境变量 | 默认 | 含义 |
|----------|------|------|
| `WECHAT_MP_SECTOR_THEME_SOURCE` | `opencli` | 行业主线来源 |
| `WECHAT_MP_HOT_INDUSTRY_TOP_N` | `8` | 东财榜抓取条数 |
| `WECHAT_MP_HOT_THEME_EMOTION` | `1` | 仅旧版 `discover_hot_themes`（如手动 `market` 标题），**不影响 sector** |

## 命令

```bash
cd stock-ai
# 行业稿口径（东财榜，推荐）
uv run python -m scripts.tools.wechat_mp_hot_theme --sector

# 旧版多源打分（含情绪主线，勿用于 sector）
uv run python -m scripts.tools.wechat_mp_hot_theme
```

## 数据日表述（勿用「今日」）

- 正文彩色开篇、五节、摘要统一写 **`{M}月{D}日收盘`**（与 `report.trade_date` / 选股库一致）。
- 6/4 早上成稿、数据仍为 6/3 收盘时，应写 **6月3日收盘**，不写「今日」。

## 与成稿流水线

| 环节 | 行为 |
|------|------|
| **`sector` 槽（定时）** | `build_sector_article` → `generate_sector_research_body`；`pick_focus_themes` 取 1～2 个主题 |
| 交易日 19:00 | `evening` 批次：`sector` + `top5` + `dragons`（无 `market`/`news`） |
| 休市日 19:00 | 周日/节假日 `weekend` → `news`；周六跳过 |
| 手动旧槽 | `market` / `news` 仍 `wechat_mp_draft --kind market|news` |
| `market` 标题 `{tags}` | `_compress_market_tags` 仍可走 `discover_hot_themes`（手动盘前/收盘稿） |

## 晚间三篇对齐（已定）

代码：`wechat_mp_evening_align.py` → `sector_alignment_prompt_block()` 注入 top5/dragons prompt。

1. **sector**：写排序前 1～2 个主题产业链（全文 80% 主线 + 快讯催化）  
2. **top5**：标题领衔股名；`逻辑归属` 写清与主线「同属/分化/独立」；750～1200 字  
3. **dragons**：标题优先 `情绪{阶段}怎么玩？{名}{n}板还在榜`；深度写 ≤2 只（`WECHAT_MP_DRAGON_WRITE_MAX`）；650～1100 字；开篇含炸板率等数字
