---
name: wechat-mp-drafts
description: >-
  WeChat Official Account 「牛马也智能」(WECHAT_MP_*): hotspot, hot business,
  silver and film long-form drafts, writing/compliance and draft operations.
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
---

# 牛马也智能 · 微信公众号

**导航真源**：[INDEX.md](INDEX.md)（按任务选读，避免扫 12 个文件）

## 命名

| 用户说法 | 指 |
|----------|-----|
| 公众号、牛马也智能 | **本 skill** |
| 简选、旧商品垂直稿 | 已退役，不再提供生成入口 |

## Agent 决策树

```
用户意图？
├─ 推草稿 / 定时 / env / 报错     → INDEX「工程」→ operations-sop + reference
├─ 改 market|news|sector|workspace → templates + writing-guide
├─ 栀夏贴图 / 电影分享 / 经典片单  → [wechat-mp-virtual-lifestyle](../wechat-mp-virtual-lifestyle/SKILL.md) + newspic-sop
├─ 长图文影视试跑 / tv_review      → [tv-review-template.md](tv-review-template.md)（v2·《铁拳教育》）
├─ 短剧列表选剧 / 单剧推广稿       → `short_drama_feature`（收益前三 + 双来源剧情核验）
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
| `market` `news` `workspace` `temp` | **手动** | 见 [INDEX.md](INDEX.md) |
| `hot_business` | **手动** | 每日热点商业筛选与深稿，独立槽位 |
| `silver` | **手动** | 50—65 岁退休生活：关系、健康、钱财，独立槽位 |
| `short_drama_feature` | **手动** | Python 给收益候选，当前 Codex 研究并写稿，Python 双来源校验后写独立槽位 |
| `literary` | **手动** | 典籍节目与文学类共用；固定 DeepSeek Chrome 会话写稿，Agent 编辑后写独立槽位 |

`--kind all` = `hotspot`·`sector`·`news`·`workspace`（**不含** `temp`）。slots：`data/wechat_mp_draft_slots.json`。

## 常用命令

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind hotspot --codex-draft output/hotspot_codex.json --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --topic "具体热点" --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind silver --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind silver --silver-lane relation --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind silver --silver-lane health --topic "退休后怎样改善睡眠习惯" --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind short_drama_feature --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind short_drama_feature --codex-draft output/short_drama_feature_codex.json --dry-run
uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening --dry-run
bash scripts/wechat_mp_draft_scheduled.sh

uv run python -m scripts.tools.wechat_mp_eval --kind all
uv run python -m scripts.tools.wechat_mp_eval --kind sector --traffic
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening
uv run pytest tests/unit/test_wechat_mp_*.py -q
```

**质量建议**：总分 ≥75、AI 味 ≤20、无合规红线 → 可进草稿箱。改稿流程见 [wechat-mp-writing](../wechat-mp-writing/SKILL.md)。

### DeepSeek 浏览器写稿（用户主动稿）

用户主动要求热点深评或文学/典籍稿时，采用两次确认：Agent 研究并展示提示词 → 用户确认 → OpenCLI `bind` 当前 Chrome 中固定的“公众号爆文秘诀”会话 → 提取本轮新回复 → Agent 核事实、编辑、高亮、配图 → 用户再次确认 → 推草稿。统一入口：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write --help
```

固定会话 ID：`f0cc031d-233f-4648-807d-354275738e61`。DeepSeek 未登录时只提示用户登录并保持该会话为当前标签；禁止自动登录、读取 Cookie、切换其他会话或回退其他模型。`literary` 使用独立槽位，不覆盖 `tv_review`。

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
  "body": "1800—2200 字的纯段落正文，信息完整后不为凑字重复观点。",
  "topic": "事件检索词",
  "research_urls": ["https://a.example/report", "https://b.example/report", "https://c.example/report"],
  "original_thesis": "不少于20字、可被反驳和检验的原创核心判断。",
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

`--codex-draft` 支持单篇 `hotspot`、`hot_business`、`silver` 或 `short_drama_feature`。该路径跳过自动选题和模板兜底，但仍执行正文清洗、原创增量报告、质量门禁、封面、合规检查与草稿槽位更新。热点深评为完读优先，正文去空白后不少于 1800 字，建议控制在 1800—2200 字；热点商业仍不少于 1920 字；银发稿要求 1600—2600 字。前三者均要求至少 3 个不同来源域、`original_thesis` 不少于 20 字，任一失败即在微信 API 前拒绝。`output/` 中的成稿 JSON 不提交。

`hot_business` 只允许手动触发，不进入定时批次。省略 `--topic` 时从每日热点池按热点强度、商业空间、可验证性和读者相关性评分，低于 70 分不成稿；指定 `--topic` 会跳过候选评分，但仍要求至少 3 个不同来源域。`--dry-run` 只预览并打印候选评分、来源域和事实条数；移除后仅更新独立的 `hot_business` 草稿槽位。

`silver` 同样只允许手动触发，不进入 `all` 或任何定时批次。省略 `--topic` 时从关系生活、健康习惯、钱财防骗三个常青题库中按最久未用方向轮换，并排除近 30 天选题；可用 `--silver-lane relation|health|money` 限定方向，或用 `--topic` 指定具体题目。健康稿必须含权威健康来源且禁止诊断、用药和治疗建议；钱财稿必须含政务或监管来源且禁止产品推荐和收益承诺。普通银发稿及其他公众号长文不再自动插入短剧返佣组件；`--dry-run` 不上传图片、不写草稿、不记录选题使用。

自 2026-08-18 起，公众号普通长文统一禁用自动短剧返佣插入。`short_drama_feature` 仅保留为用户明确要求时使用的手动独立稿型，不得作为普通热点、影视、银发或财经稿的默认变现组件。

### ChatGPT 网页原创配图续跑协议

长图文与贴图都先找同题公开报道图。`hotspot`、`hot_business` 等热门稿件优先从已登录抖音搜索政务号、央媒、地方广电和正规新闻机构的同题视频，再补 `research_urls`、可追溯微博媒体/政务原帖、百度新闻和其他同题媒体。抖音、微博、百度只作为发现入口：抖音截图必须记录媒体账号、原视频链接、发布时间和截图画面含义；普通网友搬运、二创账号、无原视频链接、与事件无关的演播室或泛素材不得进入正式草稿。无法核对原页、事件或来源的图片，以及页面明确写有禁止转载限制的图片，也不得使用。合格素材在 `figure_sources.json` 记录原页面、图片地址、来源名、发布时间、来源类型和核验状态，图注优先显示具体媒体名。

抖音候选先建报道池再选图，不按用户随口点名的平台逐个补洞：优先级为政务原始发布 → 央媒 → 地方广电/党媒 → 全国性新闻机构。先去重同一段现场视频，再按“现场事实、官方处置、当事人回应、公共讨论”选择有不同信息增量的画面；找不到足够合格图片时允许少图，不得为凑固定数量自动生成图片。热点稿只有用户明确要求原创配图时，才进入下述网页补图协议；原创小说、栀夏生活分享等本来就需要原创视觉的稿型可直接进入。

需要原创配图，且命令提示补图或抛出包含 `codex-image-request.json` 的错误时：

1. 读取请求 JSON 的全部 `slots` 与 `safety_rules`。
2. Codex 先给每个槽位设计分镜和提示词；封面先生成，人物连续图引用封面或角色母版。
3. 使用 OpenCLI 操作当前 Chrome 中已登录的 ChatGPT 网页逐图生成，点击页面“保存”下载；不调用图片 API，不读取 Cookie、密码或浏览器存储。
4. Codex 检查图片格式、尺寸、比例、人物脸型/发型/服装、道具、场景、意外文字和组图连续性；通过后才保存到该 slot 的绝对 `output_path`。
5. ChatGPT 未登录、当前标签不对、生成失败、超时、下载失败或质检失败时立即停止并提示用户处理；禁止自动回退到 Codex ImageGen、DeepSeek 或其他平台。下次从第一个未完成槽位继续，已有合格图片不重做。
6. 重跑原命令，直到不再返回缺图请求；随后才允许进入草稿上传。

用户明确说“用 Codex 生成图片”时，仅当前任务临时使用内置 ImageGen，不改变默认渠道。详细步骤见 [chatgpt-web-image-sop.md](chatgpt-web-image-sop.md)。

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

`build_article` → 各 kind 后处理（`humanize` / `finalize_*` / `sanitize`）→ `text_to_html` → `upsert_draft_article`。普通长文默认不插返佣商品或短剧卡。

细则：[reference.md](reference.md) · 代码映射：[rules-implemented.md](rules-implemented.md)。

## 定时 vs 发表

| | 说明 |
|--|------|
| **19:00 launchd** | 自动**写/更新草稿**；跳过：`echo YYYY-MM-DD > data/wechat_mp_skip_scheduled.date` |
| **后台定时发表** | **人工**在 mp.weixin.qq.com；**每天仅 1 次通知**（个人号）→ 多篇**同批群发**，排好头条/次条顺序；**禁止**分时段错开发表 |
| **LLM** | 定时稿只用 Codex CLI；用户主动的热点深评与文学/典籍稿可走固定 DeepSeek Chrome 会话，均失败关闭；东财 SOP 并发仍用 `SOP_LLM_BACKEND=deepseek` |

详 [operations-sop.md](operations-sop.md) · `stock-ai/docs/WECHAT_MP_SCHEDULING.md`。

## 子文档索引

| 文档 | 用途 |
|------|------|
| [INDEX.md](INDEX.md) | **导航与读序** |
| [brand.md](brand.md) | 账号定位 |
| [account-packaging.md](account-packaging.md) | 后台介绍/菜单/自动回复 |
| [operations-sop.md](operations-sop.md) | 运营与发布清单 |
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
