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
├─ 栀夏贴图 / 电影分享 / 经典片单  → [wechat-mp-virtual-lifestyle](../wechat-mp-virtual-lifestyle/SKILL.md) + newspic-sop
├─ 长图文影视试跑 / tv_review      → [tv-review-template.md](tv-review-template.md)（v2·《铁拳教育》）
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
uv run python -m scripts.tools.wechat_mp_draft --kind hotspot --codex-draft output/hotspot_codex.json --dry-run
uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening --dry-run
bash scripts/wechat_mp_draft_scheduled.sh

uv run python -m scripts.tools.wechat_mp_eval --kind all
uv run python -m scripts.tools.wechat_mp_eval --kind sector --traffic
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening
uv run pytest tests/unit/test_wechat_mp_*.py -q
```

**质量建议**：总分 ≥75、AI 味 ≤20、无合规红线 → 可进草稿箱。改稿流程见 [wechat-mp-writing](../wechat-mp-writing/SKILL.md)。

### Codex 长图文交接

#### 账号角色卡前置步骤

当前 Codex 手写或改写 `hotspot`、`hot_business`、`silver`、`tv_review` 时：

1. 先完整读取 [account-role-card.md](../wechat-mp-writing/account-role-card.md)。
2. 再按本 Skill 决策树读取唯一命中的稿型专题文档。
3. 角色卡只决定观察者、价值排序和语言边界；结构、长度、来源与专属禁区以稿型文档为准。
4. 角色卡缺失、为空或关键边界不完整时停止写稿，不沿用旧口吻继续。

`virtual_lifestyle` 继续使用其显性人物母版，不读取本角色卡。

手动热点长图文优先由 Codex 完成取材与成稿，再保存为本地 JSON：

```json
{
  "title": "具体事件为什么引发争议？",
  "digest": "一到两句话说明文章回答的问题。",
  "body": "不少于 2000 字的纯段落正文。",
  "topic": "事件检索词",
  "research_urls": ["https://example.com/report"],
  "slot_key": "hotspot_afternoon"
}
```

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft \
  --kind hotspot \
  --codex-draft output/hotspot_codex.json \
  --dry-run

# 人工确认后去掉 --dry-run，写入草稿箱
```

`--codex-draft` 只支持单篇 `hotspot`。该路径跳过 Composer、自动选题和模板兜底，但仍执行正文清洗、质量门禁、事件配图、封面、合规检查与草稿槽位更新。`output/` 中的成稿 JSON 不提交。

### Codex 图片续跑协议

长图文与贴图都先由 Python 自动抓同题公开报道图。热点深评默认按 `research_urls` → 可追溯微博媒体/政务原帖 → 百度新闻 → 其他同题媒体的顺序找真实现场图；微博、百度只作为发现入口。无法核对原页、事件或来源的搬运图，以及页面明确写有禁止转载限制的图片，不自动进入正式草稿。合格素材在 `figure_sources.json` 记录原页面、图片地址、来源名、发布时间、来源类型和核验状态，图注优先显示具体媒体名。

现场图不足时才使用已有原创解释图；若命令提示 `需要 Codex 原创补图`，或抛出包含 `codex-image-request.json` 的错误：

1. 读取请求 JSON 的全部 `slots` 与 `safety_rules`。
2. 每个 slot 单独调用一次内置 ImageGen，不使用额外 API 或 Composer。
3. 从 `$CODEX_HOME/generated_images/` 选取结果，复制到该 slot 的绝对 `output_path`；不得覆盖请求未列出的图片。
4. 重跑原命令，直到不再返回缺图请求；随后才允许进入草稿上传。

已有 Codex 补图完成标记时，普通续跑不重复联网。需要重新寻找真实现场图时使用 `--force-figures` 或 `WECHAT_MP_DISCUSSION_FIGURES_FORCE=1`；强制刷新会绕过 ready 标记，但应保留 `manual-*` 和可用原创封面作为失败兜底。

贴图路由：未限定类型的“贴图”默认是栀夏生活分享，先读 `wechat-mp-virtual-lifestyle/SKILL.md`，使用 `virtual_lifestyle` 槽位和角色母版生成图片；明确要求“热点深评贴图 / 新闻图集”时才使用下面的自动报道图入口。不得把社会热点报道图直接写入栀夏槽位。

热点深评贴图自动入口：

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_newspic_draft \
  --slot newspic_hotspot \
  --title "具体事件为什么引发争议？" \
  --content output/newspic_copy.txt \
  --topic "具体事件检索词" \
  --dry-run
```

自动模式默认 6 图，支持 `--image-count 6..9` 与可重复的 `--research-url`。先用 `--dry-run` 完成素材与来源校验，确认后去掉该参数才写草稿。完整细则见 `newspic-sop.md`。

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
