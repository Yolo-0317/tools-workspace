# 《鼓催柘枝》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一套突出《栀夏·敦煌十六舞》第一支定位、可直接复制发布的《鼓催柘枝》视频号标题、正文、标签、置顶评论与发布提醒。

**Architecture:** 一个 Markdown 文件保存正式发布文案，沿用项目现有视频号文案五区块结构；发布前人工逐项校验标题、四句诗、系列定位、六个标签、置顶评论、发布资产路径和禁止表述。纯文案不建立逐字匹配测试，避免正常润色触发无意义失败。

**Tech Stack:** Markdown、ripgrep、Git。

## Global Constraints

- 主标题固定为“敦煌十六舞第一支，栀夏踏着画鼓声来了”。
- 正文明确这是《栀夏·敦煌十六舞》第一支，以原创柘枝舞意象演绎白居易《柘枝妓》前四句。
- 完整引用“平铺一合锦筵开，连击三声画鼓催。红蜡烛移桃叶起，紫罗衫动柘枝来。”，不得改字或换序。
- 不声称历史复原、非遗传承、真人舞者或专业舞团，不使用夸张最高级、擦边表达和 emoji。
- 标签严格为六个：`#栀夏飞花令 #敦煌舞 #白居易 #柘枝妓 #中国古典舞 #古诗词`。
- 置顶评论只征集敦煌十六舞第二支的舞种、诗名或诗句。
- 视频路径为 `exports/gucuizhezhi-15s-subtitled-v01.mp4`，封面路径为 `exports/gucuizhezhi-dance-cover-v01.png`。

---

### Task 1: 写入正式视频号发布文案

**Files:**
- Create: `zhixia-feihualing/episodes/gucuizhezhi-15s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: 已确认的文案设计规范。
- Produces: 可直接复制的标题、发布正文、六标签、置顶评论和发布提醒。

- [x] **Step 1: 写标题和正文**

使用五个 Markdown 区块：`标题`、`发布正文`、`话题标签`、`置顶评论`、`发布提醒`。正文依次写画鼓与扬沙钩子、敦煌十六舞首支定位、完整四句诗、唯一互动问题和“原创虚拟角色｜AI辅助制作”。

- [x] **Step 2: 写标签和发布提醒**

标签区只写批准的六个标签；发布提醒记录最终字幕视频、正式封面和视频号 AI 内容声明。

### Task 2: 校验发布文案

**Files:**
- Verify: `zhixia-feihualing/episodes/gucuizhezhi-15s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: Task 1 的正式发布文案。
- Produces: 逐项校验记录。

- [x] **Step 1: 校验固定内容**

逐一确认正式标题、系列名、四句诗、“原创虚拟角色｜AI辅助制作”、置顶评论、视频路径和封面路径。

- [x] **Step 2: 校验标签和风险表述**

确认标签区恰好六个标签，并确认发布内容没有“历史复原、非遗传承、真人舞者、专业舞团、全网第一、最美、Seedance、提示词、模型参数”。

### Task 3: 终检与提交

**Files:**
- Modify: `zhixia-feihualing/docs/superpowers/plans/2026-08-30-gucuizhezhi-wechat-channels-copy.md`

- [x] **Step 1: 检查可复制性**

人工确认标题、正文、标签与置顶评论可以脱离项目上下文直接使用，正文没有内部路径、技术参数、提示词或测试措辞。

- [x] **Step 2: 运行最终验证**

运行 `git diff --check`，确认只暂存本次文案与计划。

- [x] **Step 3: 提交文案**

```bash
git commit -m '制作鼓催柘枝视频号发布文案'
```
