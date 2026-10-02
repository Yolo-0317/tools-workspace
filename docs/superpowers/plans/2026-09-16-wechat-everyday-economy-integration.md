# 普通人的经济生活公众号流程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建手动研究 Skill，将近期经济生活热点的筛选、妙想研究、回源算账和散文式公众号写作接到现有手工交接流程。

**Architecture:** 独立 `wechat-mp-everyday-economy` 只编排选题、证据和家庭影响；`wechat-mp-writing` 负责文章声音与收稿改稿；`wechat-mp-drafts` 继续负责草稿与图片门禁。三个入口互相链接，不新建发布代码或槽位。

**Tech Stack:** Markdown Skill、现有妙想 Skills、官方原文与媒体研究、Skill frontmatter 校验、离线压力测试。

## Global Constraints

- 依据 [已确认设计](../specs/2026-09-16-everyday-economy-wechat-integration-design.md)，只接入手动选题、研究、写作与编辑；不新增定时任务、自动发表、草稿槽位、配图回退或 DeepSeek 自动调用。
- 执行时先查项目注册表或 `scripts/workspace_preflight.py`，读 `stock-ai/docs/PROJECT_LAYOUT.md`、`.cursor/rules/project-memory.mdc` 短索引，再用 `rg` 在命中的一个 Memory 定位公众号条目；先读 `.cursor/skills/wechat-mp-drafts/SKILL.md` 决策树。
- 当前 `.cursor/skills/wechat-mp-writing/` 与 `.cursor/skills/wechat-mp-drafts/` 均有用户未提交修改。以工作树为基线，逐段 `apply_patch`，不得回退或整文件覆盖；本计划实施不自动提交交织的旧改动。
- 先找过去 **72 小时**内的新事件，不足时扩至 **7 天**；更早事件仅有新数据、执行节点或进展时可入候选。热度没有可靠依据时称“近期议题”，同源转载合并。
- 默认最多 **三个候选**、推荐 **一个**。用户只要候选即停；要求直接写时选最佳一题继续，不增加选题确认关卡。
- 妙想只署名实际返回的指标；银行条款、地方政策、报价和关键数字回原始出处。数据冲突未解决不得任选一个支撑标题。
- 假设算账必须写输入、单位、公式、期间、遗漏成本和适用人群。不能算单一数值时说明缺少变量，不造家庭账本、采访、亲历或个人案例。
- 用户主动热点仍须展示完整手工提示词，用户自行取得 DeepSeek 初稿并贴回；未收到即停。收稿后先核事实和算账，再改稿；图片、来源、篇幅、两次确认和草稿安全仍走原稿型门禁。
- 教育题按现行教育地域真源，不在新 Skill 硬编码城市列表。财经内容不变成投资建议，不承诺收益或传播结果。

---

## File Map

| 文件 | 单一责任 |
| --- | --- |
| `.cursor/skills/wechat-mp-everyday-economy/SKILL.md` | 触发词、决策树、交付边界与其他 Skill 的路由 |
| `.cursor/skills/wechat-mp-everyday-economy/hotspot-selection.md` | 72 小时/7 天候选来源、硬筛、热度与家庭相关性排序 |
| `.cursor/skills/wechat-mp-everyday-economy/evidence-and-accounting.md` | 妙想按问题路由、原始来源核验、证据表与算账底稿 |
| `.cursor/skills/wechat-mp-everyday-economy/writer-handoff.md` | 研究包到手工 DeepSeek 提示词及收稿编辑的接口，不复制推稿命令 |
| `.cursor/skills/wechat-mp-writing/SKILL.md`、`essay-commentary-craft.md` | 经济生活入口与散文式评论的题材适配，不承担研究细则 |
| `.cursor/skills/wechat-mp-drafts/SKILL.md`、`INDEX.md` | 公众号任务的首读路由，写草稿流程保持原样 |
| `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md` | 在既有热点提示词路径接收经济生活研究包，不影响文学分支 |

### Task 1: 新 Skill 入口与选题规则

**Files:**
- Create: `.cursor/skills/wechat-mp-everyday-economy/SKILL.md`
- Create: `.cursor/skills/wechat-mp-everyday-economy/hotspot-selection.md`

**Interfaces:**
- Consumes: 已确认设计中的主题范围、72 小时/7 天窗口和最多三个候选。
- Produces: 候选记录字段 `event`, `event_date`, `place`, `source_url`, `affected_people`, `money_or_choice`, `discussion_signal`, `reader_to_share_with`, `comment_question`, `evidence_gap`；Task 2 用这些字段决定研究问题。

- [ ] **Step 1: 读 Skill 创建规范与当前路由。** 主 Agent 完整读取 `/Users/huan.yu/.codex/skills/.system/skill-creator/SKILL.md`、既有 `wechat-mp-writing/SKILL.md` 和 `wechat-mp-drafts/SKILL.md`；检查新目录不存在，确认工作树旧改动。
- [ ] **Step 2: 写入口。** `apply_patch` 创建带 `name: wechat-mp-everyday-economy` 与明确中文 `description` 的 frontmatter；正文列出“选一组经济生活热点”“查这一题背后的普通人账单”“写普通人的经济生活”的路由：候选读 `hotspot-selection.md`，选中题再读 `evidence-and-accounting.md`，交稿读 `writer-handoff.md`。注明只手动运行、研究不等于发表、未收到 DeepSeek 稿即停。
- [ ] **Step 3: 写选题页。** 写入三个来源入口（政府/统计原文，正规媒体民生报道，妙想市场与定向检索），72 小时不足扩 7 天、旧闻只收新进展、转载合并、热度信号不足的命名；硬筛事件日期/原始来源/受影响人群/可解释价值，再按讨论信号、生活相关性、证据完整度、解释增量排序，不给伪精确分数。候选交付按上面九字段逐项说明，最多三题、推荐一题。
- [ ] **Step 4: 初次验证。** 用 Skill 校验器运行 `quick_validate.py .cursor/skills/wechat-mp-everyday-economy`；Task 2/3 子页尚未创建时只核对入口链接拼写与计划路径一致，完整链接检查留给 Task 3，并人工核对仅选题请求不会触发写草稿。

### Task 2: 妙想研究、回源与算账底稿

**Files:**
- Create: `.cursor/skills/wechat-mp-everyday-economy/evidence-and-accounting.md`

**Interfaces:**
- Consumes: Task 1 的一个选中候选及其 `event`, `affected_people`, `money_or_choice`, `source_url`, `evidence_gap`。
- Produces: `research_pack`：已核事实、当事方或机构说法、缺项、来源链接、发布时间/事件日/数据期/地区/人群/单位、妙想返回口径、示例算账输入与遗漏成本、可被反驳的核心判断；Task 3 只从此包生成提示词。

- [ ] **Step 1: 写数据路由。** 在新页明确：物价/就业/利率/汇率用 `mx-macro-data`；公司收入/成本/利润用 `mx-finance-data`；明确事件、公司、政策线索用 `mx-finance-search`；股票和板块深研才按妙想股票工作台路由；财报与行业专项只在触发条件满足时用。不把 `mx-finance-search` 当社会热点发现工具，也不调用旧股票链路。
- [ ] **Step 2: 写证据表样式与停机条件。** 每条主张至少记录 `claim | claim_type | original_url | publish_date | event_date | data_period | region | people | unit | verification`；同一公告被多媒体转载只算一份原始证据。写明建议/正式公布/生效/地方执行四种政策状态；妙想未返回、原文与新闻数字冲突或来源独立性不足时缩小论点、换题或列研究缺口，不补造数字。
- [ ] **Step 3: 写算账样式。** 明确 `inputs | units | formula | period | result | missing_costs | applicable_people`；加入两个**显著标为假设而非当前报价**的压力例：10 万元本金年利率从 1.50% 到 1.25%，年息差 `100000×(0.015-0.0125)=250 元`（税费、提前支取与具体银行条款未计）；单杯 9.9 元购买次数由 10 次到 20 次，月支出 `9.9×10=99 元` 到 `9.9×20=198 元`（不是物价上涨证据）。展示“价格/利率变化不自动等于所有家庭同额变化”的适用边界。
- [ ] **Step 4: 离线验证。** 用上述两个假设题各产一份 `research_pack` 草样，检查输入、公式、遗漏成本与主张归属齐全；不调用微信 API，不把假设写成真实家庭采访。再次运行 Skill 校验器与 `git diff --check`。

### Task 3: 写法、手工交接与公众号入口集成

**Files:**
- Create: `.cursor/skills/wechat-mp-everyday-economy/writer-handoff.md`
- Modify: `.cursor/skills/wechat-mp-writing/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-writing/essay-commentary-craft.md`
- Modify: `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md`
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/INDEX.md`

**Interfaces:**
- Consumes: Task 2 的 `research_pack`。
- Produces: 一份用户可手工复制的热点 DeepSeek 提示词，包含主题、核心判断、已核事实、算账前提、来源和待核信息；收到用户贴回稿后才进入既有审校、配图、二次确认路径。

- [ ] **Step 1: 写交接页。** `writer-handoff.md` 规定：提示词事实包只放正向可核事实和显著标记的假设算账，不把“不能把……写成……”等审校指令放进事实包。复制模板须有 `主题 / 核心判断 / 已核事实与来源 / 算账输入、公式和未计成本 / 当事方说法与待核信息` 五栏，并要求“从已核实的新变化写到普通人的收入、支出或选择；可以表达有依据的作者判断，不虚构亲历，不写成逐段问答；只输出32字内标题与900—1100字纯段落正文”。标题不承诺未证实收益、收入或减免；读者可讨论真实取舍。只展示来源包和完整提示词，等用户第一次确认并自行贴回 DeepSeek 稿。页末注明人工试做六篇（家庭账单、消费现象、热点解释各两篇）；发布后只记录后台实际给出的 24 小时和 7 天完读、分享、收藏、有效评论与流量渠道，少量样本不宣称规律。
- [ ] **Step 2: 小补丁接写作路由。** 在 `wechat-mp-writing/SKILL.md` 添加“普通人的经济生活”指向新 Skill；在 `essay-commentary-craft.md` 加一小段：经济题可用一项费用、收入、时间或选择的真实变化承载作者判断，全国均值不当个人账单，不固定算账模板；在 `deepseek-writer-sop.md` 的热点提示词前加研究包字段解释，而不改文学段和现有 900—1100 字、32 字、来源与图片规则。
- [ ] **Step 3: 小补丁接公众号首读路由。** 在 `wechat-mp-drafts/SKILL.md` 决策树加“普通人的经济生活候选/研究 → 新 Skill；写草稿仍回本 Skill 原路由”。在 `INDEX.md` 相应导航只加一个指针。不得修改槽位、发布命令、真实图数量、两次确认或现有定时说明。
- [ ] **Step 4: 交叉验证。** 从“找一组经济生活热点”与“写这篇经济生活稿”两种用户请求分别手动追踪路径，确认前者停在候选、后者先研究包与提示词、收稿前不进入草稿；验证所有新增相对链接存在，执行 Skill 校验器和 `git diff --check`。

### Task 4: 首次压力测试与交付

**Files:**
- Read only: Task 1–3 的新 Skill、原热点门禁与当期公开来源。
- No writes: 微信草稿、公众号后台、`.env`、个人账单或假采访资料。

**Interfaces:**
- Consumes: 完整路由与 `research_pack` 模板。
- Produces: 两份离线样题检查记录；用户要求启动主题选题时最多三条真实近期候选及一条推荐，不自动发表。

- [ ] **Step 1: 离线样题压力测。** 用 Task 2 的存款与咖啡假设，分别检查候选能否识别“当前事件尚未给出”而不冒充本周热点、研究包能否说明官方/银行/平台需回源的变量、写作提示词能否避免 AI 问答与收益暗示。
- [ ] **Step 2: 当前热点只读试运行。** 记录北京时间；浏览过去 72 小时的政策/统计/正规媒体经济生活话题，不足时扩至 7 天；按新规则筛出最多三题、推荐一题。只写候选、时间和来源，不在没有用户当次选题意图或确认时发送提示词给 DeepSeek，也不写草稿。
- [ ] **Step 3: 最终验证。** 运行 `python3 /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .cursor/skills/wechat-mp-everyday-economy`（若系统 Python 缺 PyYAML，改用已有隔离环境或申请在临时环境安装）；运行 `git diff --check`；检查新增链接、稿型限制、当前工作树其他未提交改动仍在。只有实际修改 Python 行为时，才先加失败测试并运行最相关的 `stock-ai/tests/unit` 测试。
- [ ] **Step 4: 报告。** 汇报新入口、验证结果、首次候选和证据缺口；明确未动公众号草稿、未自动发表、未代用户操作 DeepSeek。若用户接着选题，再进入既有第一次确认与手工交接。

## Execution Boundary

当前环境若无 `superpowers:executing-plans` 可用，用户选择当前任务实施时按任务顺序内联执行并逐项验证。只有用户明确要求委派时才使用子代理。由于命中的既有文件当前有用户未提交改动，实施阶段不自动提交交织修改；用户要求 Git 提交时再审阅、精确暂存。
