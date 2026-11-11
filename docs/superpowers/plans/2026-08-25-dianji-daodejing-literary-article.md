# 《典籍里的中国·道德经》公众号文章执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成「典籍里的中国·一集一点」第九篇《道德经》的 DeepSeek 初稿、事实编辑、公开配图和 `literary` 草稿箱交付。

**Architecture:** 沿用固定 DeepSeek 网页会话双确认流程。Agent 先准备可核验事实包和写作提示词，DeepSeek 只输出初稿；Agent 再完成原文核验、观点收束、高亮与官方配图，用户第二次确认后才写入微信 `literary` 独立槽位。

**Tech Stack:** 央视公开节目页、《史记》与《道德经》原文、Chrome 固定 DeepSeek 会话、OpenCLI、`wechat_mp_browser_write`、微信公众号草稿 API。

## Global Constraints

- 标题暂定为《天下已经乱了，老子为何还劝人“无为”？》，不得超过 32 字。
- 正文控制在 1800—2200 字，纯短段落，无小标题。
- “无为”只从克制强制性、违背事物规律的干预展开，不宣称这是唯一解释。
- 节目里的幼年、青年、老年老子观水属于艺术演绎，必须与史书记载区分。
- 不把“无为”写成躺平、逃避责任、现代放任主义或职场管理术。
- 只设置 3 处高亮；建议 3 张央视同一期公开图，找不到合格图片可以少配。
- 不插短剧、商品卡、旧品牌头图或通用免责声明。
- 用户第二次确认后才能写入 `literary` 草稿槽位，禁止自动发表。

---

### Task 1: 建立《道德经》事实包与 DeepSeek 提示词

**Files:**
- Create: `stock-ai/output/literary_daodejing_sources.json`
- Create: `stock-ai/output/literary_daodejing_prompt.txt`
- Reference: `docs/superpowers/specs/2026-08-25-dianji-daodejing-literary-article-design.md`

**Interfaces:**
- Consumes: 已确认的标题、核心判断、央视节目公开页、《史记·老子韩非列传》和《道德经》原文。
- Produces: 可直接发送到固定 DeepSeek 会话的完整提示词，以及至少 3 个不同来源域的来源清单。

- [ ] **Step 1: 核验节目设定**

确认央视节目以守藏室经历为核心，并用幼年、青年、老年老子观水呈现“上善若水”。记录完整节目页与央视预告文章页，不把节目对白当史实。

- [ ] **Step 2: 核验史书边界**

核对《史记·老子韩非列传》中“周守藏室之史”、孔子问礼、出关及“著书上下篇，言道德之意五千余言”的原文。若不同整理本用字不同，正文采用谨慎转述，不虚构确切年代或心理活动。

- [ ] **Step 3: 核验《道德经》原文**

至少核对以下三组文本及章节：

```text
第八章：上善若水，水善利万物而不争。
第三十七章：道常无为而无不为。
第五十七章：我无为而民自化。
```

正文只短引必要句子，不堆砌名句。

- [ ] **Step 4: 写出完整 DeepSeek 提示词**

提示词必须包含：标题、唯一钉子、开篇节目场景、两次判断升级、普通人处境、结尾站队题、事实边界、1800—2200 字和纯段落要求。禁止 DeepSeek输出写作说明、来源列表或小标题。

- [ ] **Step 5: 检查事实包与提示词**

运行：

```bash
cd stock-ai
jq -e '.research_urls | length >= 3' output/literary_daodejing_sources.json
rg -n '无为|上善若水|艺术演绎|1800—2200' output/literary_daodejing_prompt.txt
```

预期：JSON 校验成功，提示词同时包含核心概念、事实边界和字数要求。

### Task 2: 在固定 DeepSeek 会话取得初稿

**Files:**
- Create: `stock-ai/output/wechat_mp_browser_workflows/<workflow-id>.json`
- Create: `stock-ai/output/literary_daodejing_raw.txt`

**Interfaces:**
- Consumes: Task 1 的完整提示词与来源清单。
- Produces: 只包含本轮新增回复的 DeepSeek 初稿和状态为 `response_received` 的工作流记录。

- [ ] **Step 1: 创建并登记文学写稿工作流**

使用 `wechat_mp_browser_write prepare --kind literary` 创建工作流，主题写作“典籍里的中国·道德经”，钉子使用设计稿中的完整核心判断，并登记来源页。

- [ ] **Step 2: 用户确认后登记第一次确认**

运行：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write confirm-prompt <workflow-id>
```

预期：状态从 `researched` 变为 `prompt_confirmed`。

- [ ] **Step 3: 发送提示词并提取本轮回复**

绑定 Chrome 当前标签中的固定 DeepSeek 会话 `f0cc031d-233f-4648-807d-354275738e61`，发送 Task 1 提示词，只提取本轮新增回答，然后解除绑定。保持原浏览器标签，不关闭页面。

- [ ] **Step 4: 处理登录或页面错误**

若 DeepSeek 未登录或当前标签不是固定会话，立即停止并提示用户登录、切回固定会话；不得读取 Cookie、自动登录、另开会话或回退 API/其他模型。

- [ ] **Step 5: 检查工作流状态**

运行：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write show <workflow-id>
```

预期：`kind: literary`、`status: response_received`，回复字符数大于 1400。

### Task 3: 核验并编辑公众号终稿

**Files:**
- Create: `stock-ai/output/literary_daodejing.json`
- Create: `stock-ai/data/wechat_mp_literary_body_cache/dianji-daodejing.json`

**Interfaces:**
- Consumes: Task 2 的 DeepSeek 初稿和 Task 1 的来源包。
- Produces: 通过 `LiteraryDraft` 门禁的结构化终稿，供配图和草稿写入使用。

- [ ] **Step 1: 删除初稿中的错误框架**

删掉或改写以下内容：把“无为”解释成什么都不做；把先秦政治思想直接等同于现代企业管理；把节目艺术对白写成史实；声称本文解释是《道德经》的唯一正确答案；虚构老子看到具体乱世场景后的心理活动。

- [ ] **Step 2: 完成两次判断升级**

正文必须依次完成：

```text
无为不是不行动，而是不以主观意志强行替代事物自身规律。
真正被“无为”考验的，是确信自己正确且拥有干预能力的人。
```

- [ ] **Step 3: 收束普通人连接**

父母替成年孩子决定、管理者不断加流程、帮助者未经询问便替对方作主，三类情境最多各用一个短段。明确这些是假设结构，不冒充真实个案。

- [ ] **Step 4: 加入 3 处高亮控制符**

只在下列判断原句外包 `[[hl:...]]`：

```text
无为不是拒绝行动，而是拒绝用强制替代规律。
真正的克制，不是没有能力，而是有能力仍不把自己的意志强加给一切。
善意、能力和正确判断，并不自动赋予一个人替别人作主的权利。
```

- [ ] **Step 5: 写成结构化 JSON 并验证**

字段必须包含 `title`、`digest`、`body`、`topic`、`research_urls`、`original_thesis`、`slot_key: literary`、`topic_slug: dianji-daodejing`。

运行：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -c 'from pathlib import Path; from scripts.tools.wechat_mp_literary import load_literary_draft; d=load_literary_draft(Path("output/literary_daodejing.json")); print(len("".join(d.body.split())), len(d.research_urls))'
```

预期：正文字数为 1800—2200，来源不少于 3 个不同域，槽位为 `literary`。

### Task 4: 公开配图、排版与草稿箱交付

**Files:**
- Create: `stock-ai/assets/wechat_mp/inline-discussion/dianji-daodejing/cover.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/dianji-daodejing/still-01.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/dianji-daodejing/still-02.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/dianji-daodejing/still-03.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/dianji-daodejing/figure_sources.json`
- Modify: `stock-ai/output/literary_daodejing.json`

**Interfaces:**
- Consumes: Task 3 的结构化终稿和央视同一期公开节目图。
- Produces: 图片来源可追溯、控制符可正常转换、无推广组件的微信 `literary` 草稿。

- [ ] **Step 1: 建立央视同题图片候选池**

从央视《道德经》完整节目页、官方预告文章和同一期精彩片段选图。优先覆盖：观水悟道、守藏室或孔子问礼、老年老子。普通网友截图和无原页图片不得使用。

- [ ] **Step 2: 记录图片来源并检查画面**

`figure_sources.json` 每张图必须记录 `page_url`、`image_url`、`source_name`、`published_at`、`source_type`、`verified` 和 `page_title`。人工检查人物、场景、画质、台标和是否与正文段落匹配。

- [ ] **Step 3: 插入图片控制符**

在观水、守藏室或问礼、老年出关或后世流传三个信息节点插入 `[[fig:...]]`。图注统一说明“节目艺术呈现”并标注“图源：央视网”，不得把节目画面描述成历史照片。

- [ ] **Step 4: 暂存终稿并展示推送前报告**

运行：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write stage <workflow-id> --article output/literary_daodejing.json
```

向用户展示标题、摘要、正文字符数、来源数、图片数、高亮数以及无短剧/商品卡检查结果，等待第二次确认。

- [ ] **Step 5: 第二次确认后登记推送许可**

运行：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write confirm-push <workflow-id>
```

预期：状态变为 `push_confirmed`。

- [ ] **Step 6: 写入公众号草稿箱**

运行：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_browser_write push <workflow-id>
```

预期：只更新 `literary` 独立槽位，返回微信草稿 `media_id`；不得发表正文。

- [ ] **Step 7: 草稿回读与最终核验**

确认标题、封面、3 张正文图、3 处高亮、星标引导和《周易》预告正常；正文不得残留 `[[hl:`、`[[fig:`、`data-adtype="short-play"`、`data-pid` 或旧牛马品牌头图。
