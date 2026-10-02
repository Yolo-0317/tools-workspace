# 《栀夏·九歌祭舞》5 秒先导片视频号文案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一套可直接用于视频号的《栀夏·九歌祭舞》5 秒先导片发布文字。

**Architecture:** 单一 Markdown 文件按画面文字、标题、正文、标签、置顶评论和发布提醒分区。发布内容以《九歌·东皇太一》原文建立文化入口，以“先导片”明确内容边界，并用一个篇章征集问题承接互动。

**Tech Stack:** Markdown、ripgrep、Git。

## Global Constraints

- 定位为《栀夏·九歌祭舞》先导片，不写成正片或第一集。
- 不提测试、母板、提示词、模型版本或技术验收。
- 不声称复原战国楚舞、古代舞谱或历史舞台。
- 标题与正文不使用 emoji。
- 正文末尾包含 `原创虚拟角色｜AI辅助制作`。
- 发布提醒包含视频号 AI 内容声明。

---

### Task 1: 编写并验收视频号发布包

**Files:**
- Create: `zhixia-feihualing/episodes/jiuge-teaser-5s/wechat-channels-copy.md`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-30-zhixia-jiuge-5s-wechat-channels-teaser-copy-design.md`

**Interfaces:**
- Consumes: 已确认的神秘先导片定位、原典引文和第二条 5 秒视频。
- Produces: 可直接复制的画面文字、标题、正文、标签、置顶评论和发布提醒。

- [x] **Step 1: 写入六个固定区块**

按 `画面文字`、`标题`、`发布正文`、`话题标签`、`置顶评论`、`发布提醒` 顺序写入，不增加内部分析。

- [x] **Step 2: 核对原文与传播边界**

确认正文准确包含 `吉日兮辰良，穆将愉兮上皇。`、`先导片`、`原创虚拟角色｜AI辅助制作`，且不包含 `测试`、`母板`、`Seedance`、`真人舞者`、`历史复原`。

- [x] **Step 3: 运行文本检查**

运行：

```bash
rg -n "画面文字|标题|发布正文|话题标签|置顶评论|发布提醒|吉日兮辰良|先导片|原创虚拟角色｜AI辅助制作|AI 内容声明" zhixia-feihualing/episodes/jiuge-teaser-5s/wechat-channels-copy.md
if rg -n "测试|母板|Seedance|真人舞者|历史复原" zhixia-feihualing/episodes/jiuge-teaser-5s/wechat-channels-copy.md; then exit 1; fi
git diff --check -- zhixia-feihualing/episodes/jiuge-teaser-5s/wechat-channels-copy.md
```

预期：十类必要条目全部命中，五类内部或越界表述无命中，格式检查无输出。

- [x] **Step 4: 提交发布文案**

```bash
git add zhixia-feihualing/episodes/jiuge-teaser-5s/wechat-channels-copy.md
git commit -m "编写九歌五秒先导片视频号文案"
```
