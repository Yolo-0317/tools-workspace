# 《白雪歌》栀夏舞蹈版发布文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为《白雪歌》最终成片制作一套突出“栀夏会跳舞了”、并自然承接“AI美女舞蹈”搜索词的抖音发布文案。

**Architecture:** 单集发布内容独立保存在 `episodes/baixue/release-copy.md`，不改全局发布母版。文件只交付主标题、发布正文、话题标签、置顶评论和发布合规提醒，便于直接复制到抖音发布页。

**Tech Stack:** Markdown、人工文案质检、Git。

## Global Constraints

- 标题以栀夏为主体，第一眼突出“栀夏会跳舞了”或同义角色升级信息。
- “AI美女舞蹈”自然出现在正文和标签，不放进标题，不机械堆砌。
- 正文先写角色升级，再写中国古典舞表现，最后落回“忽如一夜春风来，千树万树梨花开”。
- 保留原创虚构角色和 AI 辅助制作说明；发布页选择平台要求的 AI 内容声明。
- 不使用擦边词、真人实拍暗示、专业舞者资历或 Seedance 教程表达。
- 标签数量保持精简，固定优先级为角色词、AI舞蹈词、中国古典舞、国风、古诗词。

---

### Task 1: 生成并质检单集发布文案

**Files:**
- Create: `zhixia-feihualing/episodes/baixue/release-copy.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-28-baixue-dance-release-copy-design.md` 和 `episodes/baixue/README.md`。
- Produces: 可直接复制到抖音的主标题、正文、标签和置顶评论。

- [ ] **Step 1: 写主标题**

标题只承担角色升级钩子，使用“栀夏这次真的会跳舞了”一类自然口语；不把“AI美女舞蹈”硬塞进标题，不超过一句。

- [ ] **Step 2: 写发布正文**

正文控制在两至四句：第一句承接标题，说明这次不是简单挥袖；第二句自然写入“AI美女舞蹈”和“中国古典舞身韵”；最后用“忽如一夜春风来，千树万树梨花开”完成诗境落点，并附“原创虚构角色｜AI辅助制作”。

- [ ] **Step 3: 写话题标签与置顶评论**

话题标签使用 `#栀夏飞花令 #AI美女舞蹈 #中国古典舞 #国风 #古诗词`。置顶评论以角色成长为话题，询问下一次想看栀夏跳进哪首诗，不重复正文，也不使用泛化的“你觉得怎么样”。

- [ ] **Step 4: 做人工质检**

逐项确认：标题主体是栀夏；正文恰好一次自然出现“AI美女舞蹈”；诗句准确；没有“真人美女”“专业舞者”“全网最美”“纯欲”等误导或擦边词；包含原创虚构和 AI 辅助说明；标签不超过五个。

- [ ] **Step 5: 提交**

```bash
git add zhixia-feihualing/episodes/baixue/release-copy.md
git commit -m "编写白雪歌舞蹈版发布文案"
```
