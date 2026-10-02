# 《九歌·云中君》诗舞剧封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从最终成片制作一张与《九歌》系列一致的 1080×1920 有字封面。

**Architecture:** 从无字幕结尾段抽取 13.500 秒画面作为底图，复用已有 Swift/AppKit 确定性排字器添加三组竖排中文，再复制到发布目录并进行尺寸、解码和缩略图视觉检查。

**Tech Stack:** FFmpeg、Swift/AppKit、ImageMagick

## Global Constraints

- 不调用图片生成模型，不改变栀夏身份、服装、动作和环境。
- 不覆盖既有封面；所有产物使用 `v02` 新文件名。
- 保留原片 AI 生成标识。

---

### Task 1: 制作并验证正式封面

**Files:**
- Create: `episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-poetry-drama-cover-base-v02.png`
- Create: `episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-poetry-drama-cover-v02.png`
- Create: `exports/yunzhongjun-poetry-drama-cover-v02.png`

**Interfaces:**
- Consumes: `exports/jiuge-yunzhongjun-poetry-drama-subtitled-v04.mp4` 和 `scripts/render_yunzhongjun_cover.swift`
- Produces: 1080×1920 PNG 正式封面与发布副本

- [x] **Step 1: 抽取底图**

  从最终成片 13.500 秒抽取一帧 PNG，写入单集封面目录。

- [x] **Step 2: 添加系列标题**

  运行现有 `render_yunzhongjun_cover.swift`，在左上方天空安全区绘制 `九歌`、`云中君`、`栀夏祭舞`。

- [x] **Step 3: 建立发布副本**

  将正式封面复制为 `exports/yunzhongjun-poetry-drama-cover-v02.png`。

- [x] **Step 4: 验证**

  检查两个输出均为 1080×1920 PNG、哈希一致、完整解码，并查看原尺寸与缩略图，确认标题可读且不遮挡人物。
