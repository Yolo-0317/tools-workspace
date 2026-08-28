# Denggao WeChat Channels Copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出《登高》视频号可直接发布的标题、正文、话题和置顶评论。

**Architecture:** 单集文案保存在 `episodes/denggao-10s/publishing-copy.md`，沿用项目现有视频号文案结构。发布正文采用“落叶领镜—人物回身—大江展开—原诗落点—评论问题”的单一叙事链，并保留原创虚构动画与 AI 辅助制作说明。

**Tech Stack:** Markdown、人工逐字校对。

## Global Constraints

- 文案方向固定为“诗境抓眼”。
- 原诗固定为 `无边落木萧萧下，不尽长江滚滚来。`
- 栏目名固定为 `《栀夏飞花令·登高》`。
- 身份说明固定包含 `原创虚构动画｜AI辅助制作`。
- 话题不超过六个，不使用 emoji。
- 不写模型、提示词、生成次数、运镜编号、制作成本或工具教学内容。

---

### Task 1: 编写并交付视频号发布文案

**Files:**
- Create: `zhixia-feihualing/episodes/denggao-10s/publishing-copy.md`

**Interfaces:**
- Consumes: 已确认的《登高》成片、封面和发布文案设计。
- Produces: 一条推荐标题、一份发布正文、六个以内话题和一条置顶评论。

- [ ] **Step 1: 编写推荐标题**

标题同时包含可感知的画面钩子与 `杜甫《登高》`，不使用制作术语和夸张标题党。

- [ ] **Step 2: 编写发布正文**

正文先写落叶、阿砚和栀夏，再写长江展开与两句原诗；末尾提出一个观众无需诗词知识即可回答的画面感受问题，并加入栏目名与制作说明。

- [ ] **Step 3: 编写话题和置顶评论**

话题覆盖栏目、篇名、作者、古诗词、国风动画和东方美学；置顶评论聚焦“落木”与“长江”两种画面力量，让观众直接选择或自由描述。

- [ ] **Step 4: 人工校对**

逐字确认诗句、篇名、作者、栏目名、AI说明和话题数量；检查没有 emoji、工具术语和强制关注转发文案。

- [ ] **Step 5: 提交**

```bash
git add zhixia-feihualing/episodes/denggao-10s/publishing-copy.md
git commit -m "完成登高视频号发布文案"
```
