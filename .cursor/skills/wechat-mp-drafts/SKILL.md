---
name: wechat-mp-drafts
description: >-
  WeChat Official Account 「牛马也智能」(WECHAT_MP_*): evening drafts sector+top5+dragons,
  writing/compliance, launchd 19:00. User says 公众号 = this account (not 简选 commerce).
  Read INDEX.md first, then task-specific child docs.
paths:
  - .cursor/skills/wechat-mp-drafts/INDEX.md
  - .cursor/skills/wechat-mp-drafts/content-analytics-sop.md
  - stock-ai/scripts/tools/fetch_wechat_mp_analytics_opencli.py
  - stock-ai/scripts/tools/wechat_mp_analytics_page.py
  - stock-ai/output/wechat_mp_recommend_daily_page*.json
  - stock-ai/scripts/tools/wechat_mp_product.py
  - stock-ai/tests/unit/test_wechat_mp_*.py
  - stock-ai/data/wechat_mp_draft_slots.json
  - stock-ai/docs/WECHAT_MP_SCHEDULING.md
  - .cursor/skills/wechat-mp-drafts/brand.md
  - .cursor/skills/wechat-mp-drafts/operations-sop.md
  - .cursor/skills/wechat-mp-drafts/evening-trilogy-templates.md
---

# 牛马也智能 · 微信公众号

**导航真源**：[INDEX.md](INDEX.md)（按任务选读，避免扫 12 个文件）

## 命名

| 用户说法 | 指 |
|----------|-----|
| 公众号、牛马也智能、晚间三篇 | **本 skill** |
| 简选、带货、小电 | [commerce](../wechat-mp-commerce-drafts/SKILL.md)（搁置） |

## Agent 决策树

```
用户意图？
├─ 推草稿 / 定时 / env / 报错     → INDEX「工程」→ operations-sop + reference
├─ 改 sector|top5|dragons 文案    → evening-trilogy-templates（先读）→ researcher-voice
├─ 改 market|news|workspace       → templates + writing-guide
├─ 影视试跑 / tv_review / 剧评稿   → [tv-review-template.md](tv-review-template.md)（v2·《铁拳教育》）
├─ 关注引流 / 星标 / 写作笔记 / 关注回复  → follow-growth-copy + account-packaging + operations-sop §二点六
├─ 运营增长 / 复盘 / 涨阅读 / 流量主  → [wechat-mp-growth-ops](../wechat-mp-growth-ops/SKILL.md)
├─ 阅读量 / 搜一搜 / 标题优化      → traffic-optimization + sousou-analytics-sop
├─ 内容分析 / 渠道占比 / 7日阅读    → content-analytics-sop + stock-opencli
└─ 改 Python 行为 / 合规          → rules-implemented → pytest
```

**上下文预算**：本文件只负责路由。一次任务只打开决策树命中的 1～2 个子文档；不要为一次草稿、标题或排障扫描全部索引文档。

**看稿**：默认 **mp 草稿箱**；禁止 `output/*preview*.html`（除非用户要 `--preview-html`）。

## 槽位

| kind | 定时 19:00 | 模块 |
|------|------------|------|
| `sector` | 交易日 | `wechat_mp_sector_article.py` |
| `news` | 周日/法定节假日休市（`weekend`） | `wechat_mp_news_article.py` |
| `top5` | 交易日 | `wechat_mp_top5_article.py` |
| `dragons` | 交易日（`eod`） | `wechat_mp_dragons_article.py` |
| `market` `news` `workspace` `temp` | **手动** | 见 [INDEX.md](INDEX.md) |

`--kind all` = `sector`·`top5`·`dragons`·`workspace`（**不含** `temp`）。slots：`data/wechat_mp_draft_slots.json`。

## 常用命令

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind top5
uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening --dry-run
bash scripts/wechat_mp_draft_scheduled.sh

uv run python -m scripts.tools.wechat_mp_eval --kind all
uv run python -m scripts.tools.wechat_mp_eval --kind sector --traffic
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening
uv run pytest tests/unit/test_wechat_mp_*.py -q
```

**质量建议**：总分 ≥75、AI 味 ≤20、无合规红线 → 可进草稿箱。改稿流程见 [wechat-mp-writing](../wechat-mp-writing/SKILL.md)。

## 流水线（摘要）

`build_article` → 各 kind 后处理（`humanize` / `finalize_*` / `sanitize`）→ `text_to_html` → 可选 `attach_footer_product`（CPS 正文约 2/3）→ `upsert_draft_article`。

细则：[reference.md](reference.md) · 晚间结构：[evening-trilogy-templates.md](evening-trilogy-templates.md) · 代码映射：[rules-implemented.md](rules-implemented.md)。

## 定时 vs 发表

| | 说明 |
|--|------|
| **19:00 launchd** | 自动**写/更新草稿**；跳过：`echo YYYY-MM-DD > data/wechat_mp_skip_scheduled.date` |
| **后台定时发表** | **人工**在 mp.weixin.qq.com；**每天仅 1 次通知**（个人号）→ 多篇**同批群发**，排好头条/次条顺序；**禁止**分时段错开发表 |
| **LLM** | 写稿 `LLM_BACKEND=cursor`；SOP 并发 `SOP_LLM_BACKEND=deepseek` |

详 [operations-sop.md](operations-sop.md) · `stock-ai/docs/WECHAT_MP_SCHEDULING.md`。

## 子文档索引

| 文档 | 用途 |
|------|------|
| [INDEX.md](INDEX.md) | **导航与读序** |
| [brand.md](brand.md) | 账号定位 |
| [account-packaging.md](account-packaging.md) | 后台介绍/菜单/自动回复 |
| [operations-sop.md](operations-sop.md) | 运营与发布清单 |
| [evening-trilogy-templates.md](evening-trilogy-templates.md) | 晚间三篇金标准 |
| [writing-guide.md](writing-guide.md) | 写法 + 发布总检 |
| [templates.md](templates.md) | 五槽模板（非晚间详述） |
| [researcher-voice.md](researcher-voice.md) | 研究员口吻 |
| [sector-discovery.md](sector-discovery.md) | 行业选题 |
| [reference.md](reference.md) | API · env · 模块 · 故障 |
| [rules-implemented.md](rules-implemented.md) | 规则 ↔ 代码 |
| [traffic-optimization.md](traffic-optimization.md) | 阅读量优化 |
| [content-analytics-sop.md](content-analytics-sop.md) | **内容分析** · 流量来源 · 日期范围 |
| [sousou-analytics-sop.md](sousou-analytics-sop.md) | 搜一搜看板 |

## 故障（速查）

| 现象 | 见 |
|------|-----|
| 小标题不居中 / 无图 / Top5 空 | [reference.md](reference.md) 文末表 |
| 行业题抓成「资金流」 | [sector-discovery.md](sector-discovery.md) + `wechat_mp_hot_theme.py` |
| 封面未更新 | `assets/wechat_mp/COVER_THUMBS.md` + 删 `data/wechat_mp_thumb_*.json` |
| OpenCLI 后台数据 | [stock-opencli](../stock-opencli/SKILL.md) |
