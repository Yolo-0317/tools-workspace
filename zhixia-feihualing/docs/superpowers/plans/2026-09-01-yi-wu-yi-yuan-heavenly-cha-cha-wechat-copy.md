# 《一舞一愿·欢喜得意》天宫恰恰视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create one directly publishable WeChat Channels title, body, six hashtags, pinned comment, and publishing reminder for the confirmed heavenly cha-cha video.

**Architecture:** Store the complete publishing artifact in one episode-level Markdown file using the project’s five-section format. Human review checks cultural contrast, exact blessing and poem attribution, interaction quality, prohibited claims, and final media paths; no brittle word-for-word automated test is added for creative copy.

**Tech Stack:** Markdown, ripgrep, Git.

## Global Constraints

- The first sentence must establish an Eastern heavenly maiden dancing Latin cha-cha.
- The contrast must be respectful and aesthetic, not a joke or a hierarchy between cultures.
- The body must contain exactly `愿你心有欢喜，步步生风。` and may quote the confirmed Meng Jiao couplet once.
- Use exactly six hashtags: `#栀夏飞花令 #一舞一愿 #天宫仙女 #恰恰舞 #国风舞蹈 #古诗词`.
- The pinned comment must offer exactly three next-dance choices: 桑巴、伦巴、探戈.
- No request to like, repost, follow, mention a friend, or reply with a fixed phrase; no mystical promise or AI-technology boasting.

---

### Task 1: Write and verify the publishing copy

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/wechat-channels-copy.md`

**Interfaces:**
- Consumes: confirmed subtitled video, “步步生风” cover, narration text, and the approved copy design.
- Produces: a single Markdown artifact ready to copy into WeChat Channels.

- [ ] **Step 1: Write the five-section artifact**

Use this exact structure and approved content:

```markdown
# 《一舞一愿·欢喜得意》天宫恰恰视频号发布文案

## 标题

《一舞一愿》｜当天宫仙女跳起恰恰

## 发布正文

当东方仙女，踩上拉丁恰恰的节拍。

云海、飞檐与月白仙衣，是天宫的清雅；明快重拍、换重与转身，是恰恰的热烈。两种气质相遇，生出另一种东方浪漫。

这一舞，送给正在奔赴好日子的你。
愿你心有欢喜，步步生风。

“春风得意马蹄疾，一日看尽长安花。”
——唐·孟郊《登科后》

原创虚拟角色｜AI辅助制作

## 话题标签

#栀夏飞花令 #一舞一愿 #天宫仙女 #恰恰舞 #国风舞蹈 #古诗词

## 首评（置顶评论）

如果天宫今晚还有下一场舞会，你想看栀夏跳桑巴、伦巴，还是探戈？

## 发布提醒

- 视频使用 `exports/yiwu-yiyuan-huanxi-cha-cha-10s-subtitled-v01.mp4`。
- 封面使用 `exports/yiwu-yiyuan-huanxi-cha-cha-10s-cover-v01.png`。
- 发布时选择视频号要求的 AI 内容声明。
```

- [ ] **Step 2: Verify structure, facts, and prohibited phrasing**

Run:

```bash
copy=zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/wechat-channels-copy.md
for heading in '## 标题' '## 发布正文' '## 话题标签' '## 首评（置顶评论）' '## 发布提醒'; do rg -q -F "$heading" "$copy"; done
rg -q -F '愿你心有欢喜，步步生风。' "$copy"
rg -q -F '——唐·孟郊《登科后》' "$copy"
rg -q -F '桑巴、伦巴，还是探戈' "$copy"
! rg -n '点赞|转发|关注|@|接住好运|必定|天宫开拉丁班|没想到|竟然|震撼' "$copy"
test -s zhixia-feihualing/exports/yiwu-yiyuan-huanxi-cha-cha-10s-subtitled-v01.mp4
test -s zhixia-feihualing/exports/yiwu-yiyuan-huanxi-cha-cha-10s-cover-v01.png
```

Expected: all checks exit successfully with no prohibited-phrase output.

- [ ] **Step 3: Commit the publishing artifact**

```bash
git add zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/wechat-channels-copy.md
git commit -m "编写天宫恰恰视频号文案"
```
