# 《典籍里的中国·徐霞客游记》执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成《腿已经走不动了，徐霞客为何还不回家？》的 DeepSeek 网页成稿、事实编辑、公开配图与公众号文学槽位草稿写入。

**Architecture:** 采用现有文学稿双确认流程。Agent 先固定事实、判断与提示词，DeepSeek 固定网页会话只负责生成正文；Agent 收稿后重新核验文献、压缩口号化表达、完成高亮和公开配图，用户第二次确认后才写入 `literary` 草稿槽位。

**Tech Stack:** DeepSeek Chrome 固定会话、公众号文学稿 JSON、`wechat_mp_browser_write` 双门禁、央视节目与权威文献公开来源、微信草稿 API。

## Global Constraints

- 标题固定为《腿已经走不动了，徐霞客为何还不回家？》。
- 正文 1800—2200 字，短段落，不设小标题，不使用正文列表。
- 不写旅行鸡汤，不鼓励无视身体风险的冒险主义。
- 节目艺术呈现、墓志铭记载、《徐霞客游记》原文必须明确区分。
- 不把“朝碧海而暮苍梧”误写成《徐霞客游记》原句。
- 不使用缺少直接权威出处的“领先西方一两百年”等夸张结论。
- 正文配图优先央视节目公开页和权威媒体节目报道图；找不到足量图片时允许少配，不生成新闻图。
- 普通文学长文不插入短剧或返佣商品。
- 只写公众号草稿箱，不自动发表。

---

### Task 1: 核验事实卡与来源

**Files:**
- Reference: `docs/superpowers/specs/2026-08-25-xu-xiake-literary-article-design.md`
- Create: `stock-ai/output/literary_xu_xiake_sources.json`

**Interfaces:**
- Consumes: 已确认的标题、核心判断和事实边界。
- Produces: 至少 3 个可访问来源域，以及每条可写事实的来源、原文和属性标签 `history|text|program`。

- [ ] **Step 1: 核验节目开场画面**

从央视节目页或央视节目报道确认“徐霞客脚已带伤仍登山”是否为节目画面；若无法直接核实，提示词改成节目中可核验的具体画面，不沿用二手概述。

- [ ] **Step 2: 核验文献出处**

分别核对陈函辉《徐霞客墓志铭》中的“丈夫当朝碧海而暮苍梧”和“游必有方”相关叙述，核对《徐霞客游记》《溯江纪源》涉及长江源流的原文语境。

- [ ] **Step 3: 核验生平数字**

确认生卒年、开始远游年龄、旅行年限、晚年身体状况及归乡过程；正文只保留来源一致或能解释口径差异的数据。

- [ ] **Step 4: 检查来源覆盖**

来源必须同时覆盖节目呈现、历史文献和现代研究解读，禁止只用自媒体转载页互相佐证。

### Task 2: 生成并确认 DeepSeek 提示词

**Files:**
- Create: `stock-ai/output/literary_xu_xiake_prompt.txt`
- State: `stock-ai/data/wechat_mp_browser_workflows/`

**Interfaces:**
- Consumes: Task 1 的核验事实卡。
- Produces: 一份可直接发送到固定 DeepSeek 会话的完整提示词，以及 `prompt_confirmed` 工作流状态。

- [ ] **Step 1: 写提示词**

提示词必须包含标题、核心判断、八段推进、可用事实、禁写内容、结尾站队问题、栏目尾注和《道德经》预告。

- [ ] **Step 2: 展示提示词**

向用户完整展示提示词，不在确认前发送网页。

- [ ] **Step 3: 记录第一次确认**

用户明确回复确认后，将工作流推进到 `prompt_confirmed`；未确认时停止。

### Task 3: DeepSeek 网页成稿与编辑返修

**Files:**
- Create: `stock-ai/output/literary_xu_xiake.json`

**Interfaces:**
- Consumes: Task 2 的已确认提示词。
- Produces: 标题、摘要、正文、主题、来源 URL、栏目篇次和下一篇预告齐全的文学稿 JSON。

- [ ] **Step 1: 固定会话写稿**

只使用 DeepSeek 固定会话 `f0cc031d-233f-4648-807d-354275738e61`；若未登录或当前会话不符，停止并提示用户，不调用 API 或其他模型替代。

- [ ] **Step 2: 核验成稿**

逐句检查节目演绎是否被写成史实、墓志铭是否被写成游记原文、长江源流结论是否过度简化、晚年身体代价是否被励志化。

- [ ] **Step 3: 编辑移动端正文**

正文控制在 1800—2200 字；删除“世界那么大”等旅行鸡汤、重复观点和成功学口号，保留两次判断升级与一个可站队问题。

- [ ] **Step 4: 加入栏目收尾**

写明「典籍里的中国·一集一点」第八篇、星标“栀夏未完成”和下一篇《道德经》预告。

### Task 4: 公开配图与排版检查

**Files:**
- Create: `stock-ai/assets/wechat_mp/inline-discussion/dianji-xuxiake/figure_sources.json`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/dianji-xuxiake/cover.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/dianji-xuxiake/still-*.jpg`

**Interfaces:**
- Consumes: Task 3 的终稿和 Task 1 的节目来源。
- Produces: 1 张封面、最多 3 张正文公开图、2—3 处高亮和推送前检查报告。

- [ ] **Step 1: 建立节目图来源池**

优先央视节目页、央视网、央视频及权威媒体对本期节目的报道；每张图记录原页面、图片地址、来源名、发布时间和核验状态。

- [ ] **Step 2: 筛选有信息增量的画面**

优先选择晚年登山或行走、母子关系、游记或地理考察三个不同信息点；不使用泛山水图、影视剧照或无出处人物画像凑数。

- [ ] **Step 3: 完成排版检查**

检查标题、摘要、正文字符数、图片数、高亮数、无原始标记、无短剧和无商品组件。

- [ ] **Step 4: 获取第二次确认**

展示推送前检查报告；只有用户明确回复确认后才能进入 Task 5。

### Task 5: 写入草稿并回读

**Files:**
- Modify: `stock-ai/data/wechat_mp_draft_slots.json`
- State: `stock-ai/data/wechat_mp_browser_workflows/`

**Interfaces:**
- Consumes: 第二次确认和通过检查的文学稿。
- Produces: `literary` 槽位 media_id、草稿回读结果和工作流 `drafted` 状态。

- [ ] **Step 1: 核验微信 API 出口**

强刷 access_token，要求微信 API 出口为 `61.169.224.226`；普通网页出口 `43.128.99.190` 不替代接口门禁。

- [ ] **Step 2: 写入 literary 槽位**

使用 `wechat_mp_browser_write push <workflow_id>` 更新文学草稿槽位，不发表文章。

- [ ] **Step 3: 回读草稿**

按 media_id 拉取草稿，核对标题、摘要、正文图片、高亮、栏目尾注、无 `short-play`、无商品 CPS、无 `[[hl:]]` 或 `[[fig:]]` 残留。

- [ ] **Step 4: 汇报结果**

只有回读全部一致后报告成功；若白名单、图片上传或草稿回读失败，报告真实阻塞点，不声称完成。
