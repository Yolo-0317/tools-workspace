# 「一舞一愿·重新出发」12 秒成片封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从无字幕原片 11.500 秒精确取帧，制作一张突出栀夏与金色前路的 1080×1920「重新出发」正式封面。

**Architecture:** 构建脚本用 FFmpeg 精确取帧，Swift/AppKit 渲染器负责中心放大、铺满画布和确定性中文排版。Shell 门禁运行真实构建流程并验证输出尺寸、格式、解码与文字叠加结果。

**Tech Stack:** zsh、FFmpeg、Swift、AppKit、CoreText、sips

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-09-01-yi-wu-yi-yuan-restart-12s-cover-design.md`。
- 输入固定为无字幕原片的 11.500 秒，底图中心放大约 15%。
- 封面文字只允许“一舞一愿”“重新出发”“愿你每一步，都算数”。
- 输出固定为 `exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v01.png`，1080×1920 PNG。
- 不加入天宫、色块、贴纸、边框或其他额外文字。
- 不提交或覆盖工作区中与本封面无关的修改。

---

### Task 1: 建立封面构建门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover.sh`
- Test: `zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover.sh`

**Interfaces:**
- Consumes: 无字幕原片和待创建的封面构建脚本。
- Produces: 对真实封面输出的尺寸、格式、解码和文字叠加行为验收。

- [x] **Step 1: 编写失败门禁**

门禁先验证输入存在，再要求可执行构建脚本；运行构建后使用 `sips` 验证 1080×1920 PNG，使用 FFmpeg 验证完整解码，并对正式封面下半区与 11.500 秒同倍率取帧做 SSIM 对比，保证底图确实来自用户确认的候选帧。

- [x] **Step 2: 运行门禁并确认按预期失败**

Run: `zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover.sh`

Expected: `FAIL: missing executable 一舞一愿 restart cover builder`。

### Task 2: 实现可重复封面构建

**Files:**
- Create: `zhixia-feihualing/scripts/build_yiwu_yiyuan_restart_12s_cover.sh`
- Create: `zhixia-feihualing/scripts/render_yiwu_yiyuan_restart_12s_cover.swift`
- Create: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v01.png`

**Interfaces:**
- Consumes: 无字幕原片、11.500 秒取帧和固定三组文案。
- Produces: 可重复生成的 1080×1920 正式封面。

- [x] **Step 1: 编写最小构建脚本**

脚本验证原片和渲染器存在，使用 FFmpeg 在 11.500 秒输出 RGB PNG 临时底图，再调用 Swift 渲染器生成正式文件。临时目录由 `mktemp` 创建，并在退出时清理。

- [x] **Step 2: 编写最小 Swift/AppKit 渲染器**

渲染器创建 1080×1920 RGB 位图，将底图以 1.15 倍中心放大铺满；注册系统行楷和楷体；在上方天空区域居中绘制“一舞一愿”“重新出发”“愿你每一步，都算数”，使用米金色和轻微暗金阴影，不绘制其他装饰。

- [x] **Step 3: 运行门禁并确认通过**

Run: `zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover.sh`

Expected: `PASS: 一舞一愿 restart cover is ready`。

### Task 3: 视觉验收与交付

**Files:**
- Inspect: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v01.png`

**Interfaces:**
- Consumes: Task 2 的正式封面。
- Produces: 可直接查看和发布的封面及验证证据。

- [x] **Step 1: 检查全尺寸封面**

使用图像查看器确认人物未被文字遮挡，金色天路完整，主标题在天空安全区，且没有正片字幕或黑边。

- [x] **Step 2: 检查缩略图可读性**

生成 270×480 预览，确认“重新出发”仍是第一信息，人物动作和金色前路仍可辨认。

- [x] **Step 3: 运行最终验证**

Run:

```bash
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover.sh
sips -g pixelWidth -g pixelHeight -g format zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v01.png
ffmpeg -v error -i zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v01.png -f null -
```

Expected: 门禁 PASS，尺寸为 1080×1920，格式为 PNG，FFmpeg 无错误输出。
