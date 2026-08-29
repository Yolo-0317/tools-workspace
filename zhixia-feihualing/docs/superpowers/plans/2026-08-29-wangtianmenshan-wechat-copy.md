# 《望天门山》视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 输出可直接发布的《望天门山》视频号文案。

**Architecture:** 单一 Markdown 文件保存标题、正文、标签、置顶评论和发布提醒；壳测试校验诗文、关键词、原创声明与禁用制作术语。

**Tech Stack:** Markdown、Zsh、ripgrep

## Global Constraints

- 标题固定为“栀夏这一舞，把青山碧水都舞醒了”。
- 正文包含李白《望天门山》全诗、四类关键词和原创虚拟角色声明。
- 不出现 Seedance、提示词、模型参数或专业真人舞者暗示。

---

### Task 1: 文案与检查

**Files:** Create `episodes/wangtianmenshan-15s/wechat-channels-copy.md`; create `tests/test_wangtianmenshan_wechat_channels_copy.sh`.

**Interfaces:** Consumes the accepted final video narrative; produces one copy-ready social post.

- [ ] Write a failing test for the title, four poem lines, keywords, declaration and final-video path.
- [ ] Run the test and confirm failure for the missing copy file.
- [ ] Write the final copy with title, body, tags, pinned comment and publishing reminder.
- [ ] Run the focused test and `git diff --check`.
