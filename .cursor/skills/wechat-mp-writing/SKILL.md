---
name: wechat-mp-writing
description: 牛马也智能公众号用户主动热点写稿、散文式评论改稿、去 AI 味、参考文阅读提炼、典籍专栏、引流写法、eval 质检与人工审阅。用户说写公众号文章、润色、改稿、去 AI 味、读参考文、典籍里的中国、引流、完读、语气用词、推稿前质检时使用。工程流水线见 wechat-mp-drafts；增长决策见 wechat-mp-growth-ops。
---

# 公众号写稿与质检（wechat-mp-writing）

**账号**：牛马也智能。**分工**：本 skill = 改稿/质检；`wechat-mp-drafts` = 定时/推稿工程；`wechat-mp-growth-ops` = 何时发、发什么。

**共同写作视角**：公众号非虚构文章默认做读者的“嘴替”——先明确这篇主要替谁发问、他最想说什么，再用可核事实把话说到位。新闻、教育、经济生活和热点评论可以提出有依据的批评；影视、典籍回应读者感受与疑问，不强行愤怒；金融稿不把立场写成投资建议，原创小说不套用此规则。细则见 [account-role-card.md](account-role-card.md)，用户主动热点再读 [essay-commentary-craft.md](essay-commentary-craft.md)。事实核验、用户确认和推稿门禁均不因此放松。

## 何时用本 skill

| 用户说 | 读 |
|--------|-----|
| 起标题 / 改标题 / 标题太差 / 要悬念但不跑题 | 先读 [wechat-mp-title-writing/SKILL.md](../wechat-mp-title-writing/SKILL.md)；平台硬禁仍以 [sousou-content-rules.md](sousou-content-rules.md) 为准 |
| 返佣商品 / 单品推荐稿 / 需求切入带货 / 素人广告文 | 先读 [wechat-mp-native-ad-writing](../wechat-mp-native-ad-writing/SKILL.md) 写正文；选品、事实和草稿门禁读 [product-feature.md](product-feature.md)，仅手动独立槽位 |
| 普通人的经济生活 / 经济生活热点 / 家庭账单选题与研究 | 先读 [wechat-mp-everyday-economy/SKILL.md](../wechat-mp-everyday-economy/SKILL.md)；确认写稿后再走本页用户主动热点路线 |
| 润色 / 改稿 / 去 AI 味 | 用户主动热点先读 [essay-commentary-craft.md](essay-commentary-craft.md)；其他稿型读 [human-say-pass.md](human-say-pass.md) · [anti-ai-voice.md](anti-ai-voice.md) |
| 诙谐 / 相声式 / 抖包袱 / 消费热点写得太板 | 先读 [essay-commentary-craft.md](essay-commentary-craft.md)，再读 [humor-punchline-craft.md](humor-punchline-craft.md)；只为适合的低伤害题材选用，不覆盖事实与合规规则 |
| **DeepSeek 写标题+正文** | 用户主动热点先读 [essay-commentary-craft.md](essay-commentary-craft.md)，再读 **[deepseek-writer-sop.md](deepseek-writer-sop.md)**（Agent 给完整提示词；用户自行取稿并贴回）；文学稿只读后者 |
| DeepSeek 成稿后观察者改稿 | [deepseek-observer-polish.md](deepseek-observer-polish.md) |
| **读参考文 / 扩容语料库**（非每篇） | [reference-reading-sop.md](reference-reading-sop.md) |
| **典籍里的中国 · 一集一点** | [voice-corpus-dianji.md](voice-corpus-dianji.md) + [dianji-zhongguo-column.md](dianji-zhongguo-column.md) |
| **引流 / 完读 / 转发 / 语气用词 / 怎么让人看下去** | **[traffic-copy-craft.md](traffic-copy-craft.md)** |
| **社会热点 / 民生新闻 / 排版语气感情** | **[social-commentary-voice.md](social-commentary-voice.md)** |
| **热点深评 / hotspot 太水 / 仿写参考 / 标题很怪 / 推稿前事实核验** | 用户主动热点写稿读 [essay-commentary-craft.md](essay-commentary-craft.md)，流程读 **[hotspot-deep-review.md](hotspot-deep-review.md)**（初稿核实阶段再按其中路由读取 [editorial-evidence-gate.md](editorial-evidence-gate.md)） |
| **择校 / 学区 / 幼升小 / 小升初 / 高中选校** | **[hotspot-deep-review.md](hotspot-deep-review.md)**，再按其中路由读取 [school-choice-policy.md](school-choice-policy.md) |
| **原创小说 / 单元故事 / 连载 / 小说人物** | **[fiction-author-role-card.md](fiction-author-role-card.md)**（独立虚构人格，不读取公众号观察者角色卡） |
| **原创配图 / 小说插图 / 栀夏生图** | **[ChatGPT 网页原创配图 SOP](../wechat-mp-drafts/chatgpt-web-image-sop.md)**（失败即停，不自动回退） |
| 写深一点 / 立意 / 宏观见解 | **[depth-and-opinion.md](depth-and-opinion.md)** |
| 搜一搜 / 标题被截断 / 表意不完整 / **标题很怪** | **[sousou-content-rules.md](sousou-content-rules.md)**（含 §标题硬禁 2026-07-28） |
| eval / 质检 / 能不能推 | [eval-gates.md](eval-gates.md) |
| evening 两篇审阅（news+hotspot） | [revision-workflow.md](revision-workflow.md) §evening |
| 标题/开篇/搜一搜数据复盘 | `wechat-mp-drafts/sousou-analytics-sop.md` · `writing-guide.md` |

**上下文预算**：先按上表选命中的主文档；用户主动热点以散文式评论为底，日常消费等适合轻诙谐的题材才加读包袱写法。严肃伤害事件保持平实，不为口吻统一加笑点。收稿前不加载事实审校页；除路由要求外，不同时读取所有写作规范和历史案例。

用户主动热点初稿贴回或当前任务已有完整确认正文后，再读 [editorial-evidence-gate.md](editorial-evidence-gate.md)，生成关键主张与时间口径记录；该记录交给 `wechat-mp-drafts` 校验，不把内部标签写入正文。经济生活题由研究 Skill 提供事实底稿，写作层负责将它们逐条对应到成稿。

## 推稿前必跑（路线 A 已接入 batch）

本节的通用分数用于自动构建稿。用户主动热点不要运行 `--kind hotspot` 来替代审稿；先人工否决散乱主线，再按 [eval-gates.md](eval-gates.md) 使用 `--user-hotspot-article` 只读预检，最后进入专用 `stage` 和双确认流程。

```bash
cd stock-ai

# 整批门禁（evening 默认门槛：总分≥75、AI味≤20）
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening

# 单篇细查
uv run python -m scripts.tools.wechat_mp_eval --kind news --traffic
uv run python -m scripts.tools.wechat_mp_eval --kind sector --traffic
uv run python -m scripts.tools.wechat_mp_eval --kind dragons --traffic
```

`wechat_mp_draft_batch --batch evening` **推稿前自动跑门禁**；未过且 `WECHAT_MP_QUALITY_GATE_STRICT=1`（默认）则 **不 upsert**。

## 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `WECHAT_MP_PUSH_QUALITY_GATE` | evening=1 | 0 关闭门禁 |
| `WECHAT_MP_QUALITY_MIN_SCORE` | 75 | 总分下限 |
| `WECHAT_MP_QUALITY_MAX_AI_FLAVOR` | 20 | AI 味上限 |
| `WECHAT_MP_QUALITY_GATE_STRICT` | 1 | 未过则阻断推稿 |
| `WECHAT_MP_QUALITY_TRAFFIC_BLOCK` | 0 | 1 时 traffic 自动项失败也算硬失败 |

## Agent 工作流（简）

### 账号角色卡前置步骤

写/改 `hotspot`、`hot_business`、`silver`、`tv_review`、`discussion` 时：

1. 成稿后 **全文跑** [human-say-pass.md](human-say-pass.md)（剧评腔→正常人，禁止只改用户点名的一句）。
2. 再读 [voice-corpus.md](voice-corpus.md) 核对用词表。
3. 典籍专栏再读 [voice-corpus-dianji.md](voice-corpus-dianji.md)。
4. 再读 [account-role-card.md](account-role-card.md)。

当前 Codex 手写或改写时，角色卡与语料库决定观察者边界；结构、长度以稿型文档为准。

`virtual_lifestyle` 继续使用其显性人物母版，不读取本角色卡。

原创小说使用 [fiction-author-role-card.md](fiction-author-role-card.md)，不读取 `account-role-card.md` 作为小说叙事规则；只有品牌命名和普通人价值视角可以显式继承。

### 质检步骤

1. `draft_batch --dry-run` 或 `push_quality_gate --batch evening` 看报告
2. 未过 → 先查 [sousou-content-rules.md](sousou-content-rules.md)（标题完整、单主题、开篇一致）→ [traffic-copy-craft.md](traffic-copy-craft.md)（开篇钩子、节奏、可转述颗粒）→ 再按 [revision-workflow.md](revision-workflow.md) 改开篇/合规词（勿大改数据段）
3. 重跑门禁或 `wechat_mp_draft --kind <k>` 单篇 upsert
4. 人工 mp 后台群发前再扫一眼 news 10 条去重、hotspot 与 news 勿重复深写同一题

## 交叉引用

- 模板与结构：`wechat-mp-drafts/evening-trilogy-templates.md`
- 研究员口吻：`wechat-mp-drafts/researcher-voice.md`
- 引流与完读：`traffic-copy-craft.md` · `wechat-mp-drafts/writing-guide.md`
- 规则与代码对照：`wechat-mp-drafts/rules-implemented.md`
- 增长推稿：`wechat-mp-growth-ops/draft-ops.md`
