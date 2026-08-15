# 朋友圈二次编辑热点深评 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成一篇关于“朋友圈不能二次编辑”的 2026 年 8 月 15 日公众号热点深评长图文，并通过事实、原创、正文和配图门禁。

**Architecture:** 先把当日热搜、微信公开回应和其他平台编辑机制分层核验，再以结构化 Codex JSON 作为唯一成稿真源。现有 `wechat_mp_draft` 链路负责正文清洗、原创报告、配图请求和草稿预演；本轮不调用微信草稿写入接口。

**Tech Stack:** Web 公开资料、JSON、`scripts.tools.wechat_mp_draft`、公众号原创增量门禁、ImageGen。

## Global Constraints

- 标题采用 `朋友圈不能改，是在保护真实吗？`，长度不超过 20 字。
- 正文去空白后控制在 2200—2800 字，硬门槛不低于 2000 字。
- 正文为纯段落，不使用小标题、编号、项目符号或问答模板。
- 至少使用 3 个相互独立的来源域，关键事实逐条可回溯。
- 不把 2026 年 8 月 15 日的热议写成微信当天发布的新公告。
- 不把热搜中的“永远不会”写成腾讯具有永久约束力的正式承诺。
- `original_thesis` 必须保留“有限编辑权 + 编辑标记 + 修改记录”的可反驳方案。
- 图片为 1 张封面和 3 张原创解释图，不使用媒体截图、真实聊天记录或仿造微信 UI。
- 正文底部不声明栀夏或作者是 AI；发布环节由平台声明处理。
- 本轮只运行 `--dry-run`，未经用户明确说“推送”不得写入微信草稿箱。

---

## File Structure

- Create: `stock-ai/output/hotspot_codex_20260815_moments_editing.json` — 标题、摘要、正文、原创判断、来源 URL 和槽位的唯一成稿真源。
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/codex-image-request.json` — 配图链路自动生成的槽位与安全约束。
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/manual-cover.jpg` — 原创封面。
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/manual-inline-01.jpg` — “删除重发的代价”解释图。
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/manual-inline-02.jpg` — “有痕编辑”解释图。
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/manual-inline-03.jpg` — 三种机制对比图。
- Read: `stock-ai/docs/superpowers/specs/2026-08-15-wechat-moments-editing-hotspot-design.md` — 已确认的事实边界、文章结构和验收标准。

### Task 1: 核验当日热点与产品事实

**Files:**
- Read: `stock-ai/docs/superpowers/specs/2026-08-15-wechat-moments-editing-hotspot-design.md`
- Create later in Task 2: `stock-ai/output/hotspot_codex_20260815_moments_editing.json`

**Interfaces:**
- Consumes: 2026 年 8 月 15 日热搜条目“朋友圈永远不会有二次编辑功能”。
- Produces: 至少 4 条可核验事实、至少 3 个独立来源域、事实与分析边界清单。

- [ ] **Step 1: 核验热搜是旧议题再讨论**

检索 2026 年 8 月 15 日热搜原始榜单与报道时间，记录热搜词、抓取时间和公开回应的原始日期。若找不到微信当天公告，成稿首段使用“这一话题今天再次进入讨论”，不得写“微信今天宣布”。

- [ ] **Step 2: 核验微信当前功能状态与公开理由**

优先查找微信派、微信帮助中心、腾讯客服或腾讯官方页面；再用可信媒体原始报道核对说话主体、回应时间和上下文。至少确认两点：当前朋友圈正文没有公开可用的二次编辑入口；删除后重发与修改原动态不是同一机制。

- [ ] **Step 3: 核验一个可比较的编辑机制**

查找一个社交平台官方帮助页，确认其编辑时限、编辑标记或历史记录中的至少两项。比较只用于说明“可编辑并不等于无痕改写”，不得据此推断微信内部计划。

- [ ] **Step 4: 建立事实边界清单**

把资料分为三类：`confirmed_fact`、`public_reason`、`article_inference`。正文中的“当前没有入口”“公开回应时间”“其他平台机制”进入前两类；“有痕编辑更合理”只进入 `article_inference`。

### Task 2: 写入结构化长文 JSON

**Files:**
- Create: `stock-ai/output/hotspot_codex_20260815_moments_editing.json`

**Interfaces:**
- Consumes: Task 1 的事实清单、来源 URL 和边界分类。
- Produces: `scripts.tools.wechat_mp_draft.load_codex_hotspot_draft()` 可读取的 UTF-8 JSON。

- [ ] **Step 1: 写入标题、摘要与原创判断**

JSON 写入固定标题 `朋友圈不能改，是在保护真实吗？`、固定主题 `朋友圈二次编辑`、固定槽位 `hotspot_morning` 和以下原创判断：`朋友圈需要的不是无痕改写，而是有限编辑权、醒目编辑标记和可查看的修改记录，让纠错权与社交可信度同时存在。` 摘要采用：`朋友圈不能修改，确实保护了原始互动语境，也把普通纠错逼成删除重发。比禁止修改更合理的答案，或许是有时限、有标记、可追溯的编辑机制。` `body` 写入 Step 2 完成的正文，`research_urls` 写入 Task 1 核验通过的原始页面 URL。

- [ ] **Step 2: 完成 2200—2800 字正文**

正文按“当日再讨论—三种修改行为—微信顾虑—删除重发的代价—有痕编辑方案—价值判断”推进。第一段直接进入当日事件；至少完整写出一个错字纠正场景、一个评论语境被改变的反方场景和一个包含时限、标记、版本记录、评论提示的机制落地场景。

- [ ] **Step 3: 进行反模板改写**

删除“今天想聊聊”“事情是这样的”“值得注意的是”“真正的问题是”等元叙述；合并连续短句，保证短段落与一至三句解释段交替；删除连续反问、万能鸡汤和不承担事实功能的金句。

- [ ] **Step 4: 验证 JSON 结构、字数与来源域**

Run:

```bash
cd stock-ai
jq -e '.title and .digest and .body and .topic and .original_thesis and (.research_urls | length >= 3) and .slot_key' output/hotspot_codex_20260815_moments_editing.json
PYTHONPATH=. .venv/bin/python -c 'import json,re,urllib.parse; p="output/hotspot_codex_20260815_moments_editing.json"; d=json.load(open(p)); print({"text_length":len(re.sub(r"\s+","",d["body"])),"domains":len({urllib.parse.urlparse(u).netloc for u in d["research_urls"]}),"title_length":len(d["title"])})'
```

Expected: `jq` 退出码为 0；`text_length` 在 2200—2800；`domains` 不少于 3；`title_length` 不超过 20。

### Task 3: 原创门禁与配图制作

**Files:**
- Read: `stock-ai/output/hotspot_codex_20260815_moments_editing.json`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/codex-image-request.json`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/manual-cover.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/manual-inline-01.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/manual-inline-02.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/manual-inline-03.jpg`

**Interfaces:**
- Consumes: Task 2 的成稿 JSON。
- Produces: `原创增量报告 [PASS]`、1 张封面、3 张正文图和完整热点草稿预演输出。

- [ ] **Step 1: 运行首次草稿预演**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft \
  --kind hotspot \
  --codex-draft output/hotspot_codex_20260815_moments_editing.json \
  --dry-run
```

Expected: 正文与原创门禁通过；如配图不足，链路生成 `codex-image-request.json`，且不调用微信写入接口。

- [ ] **Step 2: 按四个槽位分别生成原创图片**

先完整读取 `codex-image-request.json` 的 `slots`、尺寸和 `safety_rules`。每个槽位单独调用一次 ImageGen：封面表现发布与修改的犹豫；正文图一表现删除导致互动链断裂；正文图二表现带标记与版本记录的透明编辑；正文图三比较不可编辑、无痕编辑和有痕编辑。提示词明确禁止微信商标、真实 UI、媒体截图、人物肖像和伪造聊天记录。

- [ ] **Step 3: 检查图片内容与重复**

使用图像查看工具逐张检查构图、文字伪影、错误商标和不真实 UI；用 `shasum -a 256` 验证四张图片哈希不同。任何一张承担的信息作用不清楚或出现伪 UI，就只重生成该槽位。

- [ ] **Step 4: 重跑完整预演**

重复 Task 3 Step 1 的命令，直到退出码为 0、原创增量报告 PASS、封面和 3 张正文图全部满足门禁。

### Task 4: 完成前验证与交付

**Files:**
- Read: `stock-ai/output/hotspot_codex_20260815_moments_editing.json`
- Read: `stock-ai/assets/wechat_mp/inline-discussion/朋友圈二次编辑/figure_sources.json`

**Interfaces:**
- Consumes: Task 3 的最终预演结果。
- Produces: 用户可审阅的标题、正文、字数、来源域、原创门禁和配图状态。

- [ ] **Step 1: 运行新鲜的最终预演**

使用 Task 3 Step 1 的同一命令重新运行，不复用先前输出；记录完整退出码、正文长度、独立来源域数量和原创增量报告。

- [ ] **Step 2: 确认没有发生微信写入**

检查执行命令包含 `--dry-run`，并确认输出不存在 `media_id=`、`已新建草稿`、`已更新草稿` 或微信草稿 ID。

- [ ] **Step 3: 向用户交付**

提供标题、完整正文、正文去空白字数、独立来源域数量、原创报告和配图结果，并链接 `output/hotspot_codex_20260815_moments_editing.json`。只有用户明确说“推送”后，才允许去掉 `--dry-run`。
