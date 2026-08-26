# 《望庐山瀑布》视频号发布内容 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成并归档一套可直接用于《望庐山瀑布》视频号发布的标题、正文、话题和置顶评论。

**Architecture:** 以成片对白“这座山在往下掉”作为悬念入口，按水雾突袭、循声抬头、瀑布揭示的顺序推进，最后用李白诗句和低门槛选择题承接互动。最终内容保存到庐山单集目录，避免发布时出现多个版本。

**Tech Stack:** Markdown、项目既有视频号发布格式、Git

## Global Constraints

- 标题采用“悬念开场、诗句揭晓”方向。
- 成片对白和诗句必须准确，不虚构创作史实。
- 不把“三千尺”解释为精确测量值。
- 不声称画面是现实庐山的精确复原。
- 保留“原创国风动画｜AI辅助制作”。
- 话题不超过六个。
- 不使用网络热梗、夸张营销词或表情符号。

---

### Task 1: 归档并交付视频号发布内容

**Files:**
- Create: `zhixia-feihualing/episodes/lushan/publishing-copy.md`
- Reference: `zhixia-feihualing/episodes/lushan/subtitle-plan.json`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-lushan-video-channel-publishing-design.md`

**Interfaces:**
- Consumes: 最终字幕台词、已确认的悬念方向和视频号发布边界。
- Produces: 一套可直接复制的标题、正文、六个话题和置顶评论。

- [ ] **Step 1: 创建发布内容文件**

写入以下完整内容：

```markdown
# 《望庐山瀑布》视频号发布内容

## 推荐标题

这座山怎么在往下掉？｜《望庐山瀑布》

## 发布正文

水雾突然扑来，阿砚吓了一跳：

“栀夏，这座山在往下掉！”

栀夏侧耳听了听：“不是山，你听。”

循着轰鸣抬头，答案藏在云上。

“飞流直下三千尺，疑是银河落九天。”

第一眼望过去，你觉得从云里落下的是山、银河，还是水？

《栀夏与阿砚·望庐山瀑布》
原创国风动画｜AI辅助制作

## 话题

#栀夏飞花令 #望庐山瀑布 #李白 #古诗词 #国风动画 #原创动画

## 置顶评论

第一眼看到云间瀑布，你脑海里闪过的答案是？

A｜山在往下落
B｜云从天上垂下来
C｜银河落进人间
D｜一场巨大的瀑布

选一个，也可以写下你想到的画面。
```

- [ ] **Step 2: 核对成片事实**

运行：

```bash
rg -n '栀夏，这座山在往下掉|不是山，你听|飞流直下三千尺，疑是银河落九天' \
  zhixia-feihualing/episodes/lushan/subtitle-plan.json \
  zhixia-feihualing/episodes/lushan/publishing-copy.md
```

预期：字幕清单和发布内容都命中对应对白与诗句。

- [ ] **Step 3: 核对格式与表达边界**

运行：

```bash
rg -n '原创国风动画｜AI辅助制作|^#栀夏飞花令 ' \
  zhixia-feihualing/episodes/lushan/publishing-copy.md
git diff --check -- zhixia-feihualing/episodes/lushan/publishing-copy.md
```

预期：内容说明和话题行各命中一次；话题恰好六个；文件没有空白错误。人工确认全文没有把“三千尺”写成精确测量值，没有声称画面精确复原现实庐山，也没有使用表情符号。

- [ ] **Step 4: 提交发布内容**

```bash
git add zhixia-feihualing/episodes/lushan/publishing-copy.md
git commit -m '文案：归档庐山视频号发布内容'
```

