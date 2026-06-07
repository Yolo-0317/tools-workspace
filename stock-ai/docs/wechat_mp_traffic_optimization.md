# 牛马也智能 · 阅读 × 完读 × 垂直词（持续优化）

代码真源：`wechat_mp_monetization.py`、`wechat_mp_traffic_checklist.py`、`wechat_mp_seo.py`。  
Skill 速查：`.cursor/skills/wechat-mp-drafts/traffic-optimization.md`。

## 三指标分工

| 指标 | 拉什么 | 主要手段 |
|------|--------|----------|
| **阅读** | 点开 | 标题/摘要/搜一搜前 15 字、`wechat_mp_seo` |
| **完读** | 读到底、流量主广告曝光 | 开篇数字、分节、400–3200 字、悬念结尾 |
| **垂直词** | 财经标签、eCPM、搜一搜停留 | 正文自然出现稿型词表 ≥2 个 |

## 推稿前（每篇）

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_eval --kind sector --traffic
uv run python -m scripts.tools.wechat_mp_eval --kind top5 --traffic
uv run python -m scripts.tools.wechat_mp_eval --kind dragons --traffic
```

自动项应覆盖：标题 SEO、摘要 SEO、开篇数字、垂直词 ≥2、长度、分节、文末问句、推荐 ♡。

## 每周复盘（约 20 分钟）

1. **内容分析**（`fetch_wechat_mp_analytics_opencli`）  
   - 流量来源：搜一搜 / 朋友圈 / 推荐  
   - 单篇 **完读率**、阅读后关注（目标完读 >60%，优秀 >70%）

2. **搜一搜看板**（`fetch_wechat_mp_sousou_opencli`，Chrome 看板 tab 前台）  
   - 搜索后阅读/关注、点击 Top 文章 → 只改 **一类** evening 标题句式

3. **只调一类**（见 `sousou-analytics-sop.md` §四）  
   - dragons 搜索高 → 保持「怎么玩/还在榜」  
   - top5 搜索高 → 保持「领衔/收盘信号/明日盯啥」  
   - sector → 「产业链怎么拆/怎么跟」

4. **流量主概览**（bind 流量主页）  
   - 程序化广告 vs 带货；CPS 勿用概览「热门返佣」照搬

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `WECHAT_MP_MONETIZE` | 1 | 0=关闭 LLM 流量块与文末问句 |
| `WECHAT_MP_VERTICAL_WORDS_MIN` | 2 | traffic 清单垂直词最少命中数 |
| `WECHAT_MP_ENGAGEMENT_HOOK` | 1 | 文末留言问句 |
| `WECHAT_MP_RECOMMEND_HOOK` | 1 | 文末「推荐 ♡」引导 |
| `WECHAT_MP_FOOTER_PRODUCT_KINDS` | （空=全部） | **完读优先**建议 `market,top5`，少在 dragons/sector 插 CPS |

## 稿型金标准

晚间三篇结构见 `.cursor/skills/wechat-mp-drafts/evening-trilogy-templates.md`（彩色开篇、CPS 约 2/3、单免责）。

## 修订

| 日期 | 说明 |
|------|------|
| 2026-06-04 | 强化 monetization prompt、traffic 清单垂直词≥2、开篇数字检查 |
