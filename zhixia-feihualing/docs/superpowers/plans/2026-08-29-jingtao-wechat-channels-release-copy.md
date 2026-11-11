# 《惊涛》视频号发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成并归档一套可直接复制到视频号的《惊涛》标题、正文、话题标签和置顶评论。

**Architecture:** 单集发布内容独立保存在 `episodes/jingtao/wechat-channels-copy.md`，不修改全局发布母版。成稿以角色钩子开场，经舞蹈与诗景描述落到苏轼原句，再用具体问题引导评论，并附原创虚构与 AI 辅助制作说明。

**Tech Stack:** Markdown、人工语言质检

## Global Constraints

- 平台为视频号，不使用抖音式关键词堆叠。
- 标题固定为“栀夏一转身，江水都成雪了”。
- 正文为三至四段，准确包含“乱石穿空，惊涛拍岸，卷起千堆雪”。
- 发布正文中“AI美女舞蹈”与“中国古典舞”各自然出现一次。
- 固定说明为“原创虚构角色｜AI辅助制作”。
- 标签不超过六个；发布时选择平台要求的 AI 内容声明。

---

### Task 1: 写作并归档视频号发布文案

**Files:**
- Create: `episodes/jingtao/wechat-channels-copy.md`

**Interfaces:**
- Consumes: 已确认的《惊涛》成片内容和发布文案设计。
- Produces: 可复制使用的标题、正文、话题标签、置顶评论和发布提醒。

- [x] **Step 1: 写入标题与正文**

标题写为“栀夏一转身，江水都成雪了”。正文第一段描写栀夏旋转、长袖与浪沫如雪；第二段自然写入“AI美女舞蹈”和“中国古典舞”，并引用完整准确诗句；第三段询问观众下一首想看栀夏跳进哪首诗；末尾单列“原创虚构角色｜AI辅助制作”。

- [x] **Step 2: 写入话题与置顶评论**

话题使用 `#栀夏飞花令 #苏轼 #古诗词 #国风舞蹈 #中国古典舞 #AI影像`。置顶评论不复述标题，询问观众最想让栀夏用舞蹈演绎哪一句诗，并邀请直接留下诗句。

- [x] **Step 3: 完成人工语言质检**

逐项确认：标题主体为栀夏；正文准确包含苏轼诗句；正文中的“AI美女舞蹈”和“中国古典舞”各一次；没有真人舞者暗示、专业资历、夸张最高级或擦边表达；含原创虚构说明；标签恰好六个。

- [x] **Step 4: 运行差异检查并提交**

Run:

```bash
git diff --check
git add zhixia-feihualing/docs/superpowers/specs/2026-08-29-jingtao-wechat-channels-release-copy-design.md \
  zhixia-feihualing/docs/superpowers/plans/2026-08-29-jingtao-wechat-channels-release-copy.md \
  zhixia-feihualing/episodes/jingtao/wechat-channels-copy.md
git commit -m "编写惊涛视频号发布文案"
```

Expected: 差异检查无输出，只提交《惊涛》视频号文案相关文件。
