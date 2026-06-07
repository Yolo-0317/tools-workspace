# 阅读 · 完读 · 垂直词（牛马也智能）

> 完整 SOP：`stock-ai/docs/wechat_mp_traffic_optimization.md`  
> 搜一搜数据：`sousou-analytics-sop.md`

## 推稿必跑

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_eval --kind {sector|top5|dragons} --traffic
```

## 三句话

| 指标 | 做法 |
|------|------|
| **阅读** | 标题前 15 字 + 搜一搜句式（dragons/top5 见 `wechat_mp_seo.py`） |
| **完读** | 开篇有数字；400–3200 字；≤180 字/段；末句悬念；dragons ≤2 只深写 |
| **垂直词** | 正文命中稿型词 ≥2（`WECHAT_MP_VERTICAL_WORDS_MIN`） |

## 每周

1. `output/wechat_mp_analytics_latest.json` → 完读率、来源占比  
2. `output/wechat_mp_sousou_latest.json` → 搜索点击 Top → 改 **一类** 标题  
3. 流量主概览 → 广告收入；CPS 用 `--search` 勿照搬「热门返佣」

## 代码入口

- Prompt：`wechat_mp_monetization.monetization_prompt_block`
- 清单：`wechat_mp_traffic_checklist.run_traffic_checklist`
- SEO：`wechat_mp_seo.enrich_title_for_search` / `enrich_digest`
