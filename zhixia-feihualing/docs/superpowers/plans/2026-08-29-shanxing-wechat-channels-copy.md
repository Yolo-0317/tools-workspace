# 《山行》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 编写并保存一套可直接发布的《山行》视频号标题、正文、话题标签、置顶评论和发布提醒。

**Architecture:** 单一 Markdown 文件承载全部发布文字，按标题、正文、话题标签、置顶评论和发布提醒分区。交付前用人工编辑检查诗文准确性、关键词自然度、原创角色说明和平台边界；人类可读文案不增加脆弱的逐字自动化测试。

**Tech Stack:** Markdown、人工编辑检查

## Global Constraints

- 标题固定为“栀夏一抬手，满山霜叶都红了”。
- 正文准确引用“霜叶红于二月花”，并点明杜牧《山行》。
- 正文自然使用“AI美女舞蹈”和“中国古典舞”各一次，不在同一句堆叠。
- 明确栀夏与阿砚均为原创虚拟角色，不写成真人或专业舞者。
- 话题恰好六个：`#栀夏飞花令`、`#杜牧`、`#山行`、`#AI美女舞蹈`、`#中国古典舞`、`#古诗词`。
- 发布提醒包含选择视频号要求的 AI 内容声明。

---

### Task 1: 编写并验收视频号发布文案

**Files:**
- Create: `episodes/shanxing-15s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: 已确认的《山行》15 秒成片、封面与发布文案设计规格。
- Produces: 可直接复制到视频号的完整发布文字。

- [ ] **Step 1: 写入标题与三段正文**

标题使用固定版本。正文第一段承接霜林显红和寒山起舞；第二段自然分别写入“AI美女舞蹈”与“中国古典舞”；第三段引用诗句、说明原创虚拟角色并发出下一首诗的邀请。

- [ ] **Step 2: 写入话题、置顶评论和发布提醒**

话题使用全局约束中的六个固定标签。置顶评论写成“下一首想看栀夏跳哪句诗？也可以直接留下诗名。”发布提醒要求使用正式字幕版、正式封面并选择平台 AI 内容声明。

- [ ] **Step 3: 执行人工编辑检查**

逐项确认：标题与视频画面一致；“霜叶红于二月花”无错字；杜牧和《山行》署名正确；两个搜索关键词各出现一次且不相邻；原创虚拟角色说明明确；正文不包含真人、专业资历、关注点赞命令或无关热词；话题数量为六个。

- [ ] **Step 4: 检查格式并提交**

Run: `git diff --check -- zhixia-feihualing/episodes/shanxing-15s/wechat-channels-copy.md`

Expected: 无输出，退出码为零。

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-29-shanxing-wechat-channels-copy.md \
  zhixia-feihualing/episodes/shanxing-15s/wechat-channels-copy.md
git commit -m "编写山行视频号发布文案"
```
