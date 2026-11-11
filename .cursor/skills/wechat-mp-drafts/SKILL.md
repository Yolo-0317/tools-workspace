---
name: wechat-mp-drafts
description: >-
  WeChat Official Account 「牛马也智能」(WECHAT_MP_*): hotspot, hot business,
  silver and film long-form drafts, writing/compliance and draft operations.
  Read INDEX.md first, then task-specific child docs.
---

## 共通写作规则

先读[中文写作基座](../../../docs/writing/中文写作基座.md)，统一执行叙述身份、材料整合、自然表达、分段回读和语义保护。本Skill只补充题材与交付要求；用户明确例外、证据来源及操作权限继续按本专题执行。共通更新只维护基座，不在此复制一份。

2026-10-23配图更新：默认封面用 huashu 方法设计与文章内容相关的艺术图，正文用相关真实评论截图，头像昵称统一打马赛克、不用纯色涂盖；执行[公众号公共 Skill 当前配图规则](../wechat-mp-article/SKILL.md#5-标题配图与手机排版)。原报道视频截帧改为用户指定或确需真实资料时的分支，不再默认截图兼封面。下文旧抖音卡片及douyin-search字段仅作旧工程说明，不能伪造记录。

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
├─ 普通人的经济生活选题 / 研究    → [wechat-mp-everyday-economy](../wechat-mp-everyday-economy/SKILL.md)（只读筛选与研究；确认后回到用户主动热点路线）
├─ 用户主动热点深评               → wechat-mp-article + hotspot-deep-review（通用写稿审稿；用户指定 DeepSeek 才手工交接）
├─ 妙想盘后公众号稿 / 手机排版      → [miaoxiang-market-review-article](../miaoxiang-market-review-article/SKILL.md)
├─ 改 market|news|sector|workspace → templates + writing-guide
├─ 栀夏贴图 / 电影分享 / 经典片单  → [wechat-mp-virtual-lifestyle](../wechat-mp-virtual-lifestyle/SKILL.md) + newspic-sop
├─ 长图文影视试跑 / tv_review      → [tv-review-template.md](tv-review-template.md)（v2·《铁拳教育》）
├─ 短剧列表选剧 / 单剧推广稿       → `short_drama_feature`（收益前三 + 双来源剧情核验）
├─ 返佣商品 / 单品推荐稿           → [wechat-mp-native-ad-writing](../wechat-mp-native-ad-writing/SKILL.md) 写作；[product-feature.md](../wechat-mp-writing/product-feature.md) 选品与草稿
├─ 通用知识 / AI / 工具 / 生活文章写作与重写 → [wechat-mp-article](../wechat-mp-article/SKILL.md)；命中专题时优先专题边界
├─ 近期健康话题 / 热点选题         → [wechat-mp-health-topic-discovery](../wechat-mp-health-topic-discovery/SKILL.md) 核关注度与可答性；不限年龄
├─ 中老年健康知识稿 / 配图 / 草稿   → [wechat-mp-senior-health](../wechat-mp-senior-health/SKILL.md)；近期先从丁香医生找问题，再独立核事实与写稿
├─ 健康生活 / 营养 / 保健品调研     → [wechat-mp-health-content](../wechat-mp-health-content/SKILL.md) 独立研究与写法；不走 product_feature 小商品流程
├─ 关注引流 / 星标 / 写作笔记 / 关注回复  → follow-growth-copy + account-packaging + operations-sop §二点六
├─ 运营增长 / 复盘 / 涨阅读 / 流量主  → [wechat-mp-growth-ops](../wechat-mp-growth-ops/SKILL.md)
├─ 起标题 / 改标题 / 标题太差      → [wechat-mp-title-writing](../wechat-mp-title-writing/SKILL.md)；阅读数据复盘再读 traffic-optimization + sousou-analytics-sop
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
| `product_feature` | **手动** | 返佣 Select 只在零食与日用小百货采样来源平台高销量候选，当前 Codex 试三种文案角度并写单品稿，独立草稿槽位 |
| `literary` | **手动** | 典籍节目与文学类共用；用户自行向 DeepSeek 取初稿，Agent 编辑后写独立槽位 |

`product_feature` 写入草稿时，必须把所选商品的返佣卡直接放进草稿正文 HTML：商品卡前是独立的「广告」标识，卡片为 `<mp-common-cpsad>`，`data-pid` 由已选商品的 `sku_id` 或仓库 ID 与商品 ID 计算。使用本稿型现有构建与写入链路，不让作者在纯正文里手写卡片，也不改用旧「简选小电」流程。预检要求恰好一张卡且商品身份匹配；写入后回读公众号草稿，再核对卡片和标识，失败则不得替换原 `product_feature` 槽位。操作步骤见 [product-feature.md](../wechat-mp-writing/product-feature.md)。

`--kind all` = `hotspot`·`sector`·`news`·`workspace`（**不含** `temp`）。slots：`data/wechat_mp_draft_slots.json`。

## 常用命令

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --topic "具体热点" --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind silver --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind silver --silver-lane relation --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind silver --silver-lane health --topic "退休后怎样改善睡眠习惯" --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind short_drama_feature --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind product_feature --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind short_drama_feature --codex-draft output/short_drama_feature_codex.json --dry-run
uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening --dry-run
bash scripts/wechat_mp_draft_scheduled.sh

uv run python -m scripts.tools.wechat_mp_eval --kind all
uv run python -m scripts.tools.wechat_mp_eval --kind sector --traffic
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening
uv run pytest tests/unit/test_wechat_mp_*.py -q
```

**自动稿质量建议**：总分 ≥75、AI 味 ≤20、无合规红线 → 可进草稿箱。用户主动热点稿不适用这套通用分数；先做文章级人工审稿与专用预检，再走其独立的草稿暂存流程。改稿流程见 [wechat-mp-writing](../wechat-mp-writing/SKILL.md)。

### 热点深评当前入口与可选手工交接

2026-10-12用户决定：公众号继续写热点深评，默认执行 [通用公众号写稿](../wechat-mp-article/SKILL.md) 与 [热点专题](../wechat-mp-writing/hotspot-deep-review.md)。先取证、起稿、逐句语法检查和上下文连读，再集中审稿；不要求用户另取初稿。真实图、事实与工程预检继续执行，推草稿须有明确授权，不自动发表。下文 DeepSeek 交接只适用于用户指定 DeepSeek 的热点稿，以及既有文学/典籍稿。

用户指定 DeepSeek 写热点深评，或按既有文学/典籍路线写稿时，采用两次确认：Agent 研究并展示完整提示词 → 用户确认 → 用户自行把提示词交给 DeepSeek，并把完整输出贴回当前任务 → Agent 核事实、编辑、高亮、配图 → 用户再次确认 → 推草稿。默认仍由用户贴回 DeepSeek 完整输出；如果完整正文已经在当前任务中完整展示，且用户明确要求按该正文发布，可登记为“当前任务已确认正文”，无需再次复制。审核结论、摘要、零散修改或 Agent 转述不能替代完整正文。Agent 禁止直接调用、打开、绑定、操作或检查 DeepSeek，不处理其登录状态、Cookie、会话或标签页；正文尚未完整出现时暂停，也不回退其他模型代写。`literary` 使用独立槽位，不覆盖 `tv_review`。

### Codex 长图文交接

#### 账号角色卡前置步骤

当前 Agent 编辑用户主动 `hotspot`，或 Codex 手写/改写 `hot_business`、`silver`、`tv_review` 时：

1. 先完整读取 [account-role-card.md](../wechat-mp-writing/account-role-card.md)。
2. 再按本 Skill 决策树读取唯一命中的稿型专题文档。
3. 角色卡只决定观察者、价值排序和语言边界；结构、长度、来源与专属禁区以稿型文档为准。
4. 角色卡缺失、为空或关键边界不完整时停止写稿，不沿用旧口吻继续。

`virtual_lifestyle` 继续使用其显性人物母版，不读取本角色卡。

用户主动热点的编辑终稿保存为本地 JSON。当前 Agent 起稿时保存本篇完整正文及用户确认记录；使用 DeepSeek 交接时保留用户贴回的完整输出；若当前任务已完整展示正文并获得明确发布确认，则保存该完整正文、确认原话和 Agent 核实编辑记录：

```json
{
  "title": "具体事件为什么引发争议？",
  "digest": "一到两句话说明文章回答的问题。",
  "body": "目标 900—1100 字的纯段落正文；信息复杂时允许超过 1100 字，但应优先精简。",
  "topic": "事件检索词",
  "research_urls": ["https://a.example/report", "https://b.example/report", "https://c.example/report"],
  "original_thesis": "不少于20字、可被反驳和检验的原创核心判断。",
  "slot_key": "hotspot_afternoon"
}
```

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write stage \
  <workflow-id> \
  --article output/hotspot_codex.json \
  --handoff output/editorial_handoff.json \
  --edit-note "核对关键事实、日期和引语" \
  --edit-note "删除无法回源的判断"
```

当前任务已经完整展示正文并获明确确认时，使用：

```bash
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write record-confirmed-body \
  <workflow-id> \
  --response-file <full-body-file> \
  --confirmation-text "就按照刚刚的正文发布"
```

直接运行 `wechat_mp_draft --kind hotspot --codex-draft ...` 会被拒绝。用户主动热点深评正文目标 900—1100 字，去空白后少于 850 字拒绝；信息复杂时允许超过 1100 字，但应优先精简，不为凑字重复观点。至少 3 个不同来源域，`original_thesis` 不少于 20 字。`output/` 中的成稿 JSON 不提交。新建用户主动热点工作流的 `stage` 还须提交 `editorial_handoff.json`；历史工作流不强制补造。当前任务已有完整正文并获明确发布确认时，可从研究状态直接登记正文，无须伪造提示词确认。

`hot_business` 只允许手动触发，不进入定时批次。省略 `--topic` 时从每日热点池按热点强度、商业空间、可验证性和读者相关性评分，低于 70 分不成稿；指定 `--topic` 会跳过候选评分，但仍要求至少 3 个不同来源域。`--dry-run` 只预览并打印候选评分、来源域和事实条数；移除后仅更新独立的 `hot_business` 草稿槽位。

`silver` 同样只允许手动触发，不进入 `all` 或任何定时批次。省略 `--topic` 时从关系生活、健康习惯、钱财防骗三个常青题库中按最久未用方向轮换，并排除近 30 天选题；可用 `--silver-lane relation|health|money` 限定方向，或用 `--topic` 指定具体题目。健康稿必须含权威健康来源且禁止诊断、用药和治疗建议；钱财稿必须含政务或监管来源且禁止产品推荐和收益承诺。普通银发稿及其他公众号长文不再自动插入短剧返佣组件；`--dry-run` 不上传图片、不写草稿、不记录选题使用。

自 2026-08-18 起，公众号普通长文统一禁用自动短剧返佣插入。`short_drama_feature` 仅保留为用户明确要求时使用的手动独立稿型，不得作为普通热点、影视、银发或财经稿的默认变现组件。

### 图片协议

新用户主动热点工作流的入选图，除下述来源资料外，还须在 `figure_sources.json` 记录 `visual_description`、`visual_checked_at`、`evidence_role`。打开实际图片核对内容，价格截图写清图上可读价格与地点；实景照不得标成价格证据。入选图及封面要与 `editorial_handoff.json` 对应，字段见 [operations-sop.md](operations-sop.md)。

用户主动 `hotspot` 必须先从已登录抖音搜索政务号、央媒、地方广电和正规新闻机构的同题内容。**只读取搜索结果卡片与封面图，禁止点击、打开或播放视频。** 每次检索必须保存 `douyin-search.json`；选中封面须记录媒体账号、结果页显示时间、原视频链接和封面地址。没有合格候选时也必须记录检索词、完成时间和失败原因，之后才可补政府官网、官方媒体或法条页面的证据图。

合格素材必须在 `figure_sources.json` 记录原页面、图片地址、来源名、发布时间、来源类型、图注和核验状态。选中的抖音封面必须与其中一条 `douyin_cover` 来源完全对应。正文真实图最多 3 张；合格真实图总数为 1—3 张时全部进入正文，并从中选 1 张同时作为封面。至少需要 1 张可追溯真实图，零图直接停止。合格图超过 3 张时，正文仍只取 3 张；如需让封面占用其中一个正文名额，在该选题的 `cover_source.json` 中显式写入 `"reuse_in_body": true`。该流程禁止 ChatGPT、ImageGen、DeepSeek 或任何其他模型生成图片，禁止创建或消费 `codex-image-request.json`，也禁止为凑数联网自动补图。

下面的原创配图协议只适用于原创小说、栀夏生活分享等明确需要原创视觉的稿型，**不适用于用户主动热点深评**。

需要原创配图时：

1. 如已有 `codex-image-request.json`，读取全部 `slots` 与 `safety_rules`。
2. 先设计分镜与提示词；封面先生成，人物连续图引用封面或角色母版。
3. 默认使用当前环境的内置 ImageGen，按图片生成 Skill 执行；不再要求用户额外指定 Codex，也不默认打开 ChatGPT 网页。用户明确指定其他渠道时按其要求执行。
4. 检查图片格式、尺寸、比例、人物脸型/发型/服装、道具、场景、意外文字和组图连续性；通过后保存到对应 `output_path`。
5. 生成或质检失败时保留已有合格图片，仅重试未完成槽位；确实无法继续时说明阻碍，不把存在缺陷的图插入草稿。
6. 若由原命令发起补图，补齐后重跑原命令，确认不再缺图才进入已获授权的草稿上传。

渠道选择与网页版可选流程见 [原创配图 SOP](chatgpt-web-image-sop.md)。

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
| **LLM** | 人工热点深评默认通用 Skill 由当前 Agent 写稿审稿；指定 DeepSeek 时手工交接，文学/典籍保留既有交接；不因文档更新恢复或修改定时任务 |

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
| OpenCLI 后台数据 | [公众号内容分析](../wechat-mp-drafts/content-analytics-sop.md) |
