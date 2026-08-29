# 《望天门山》封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《望天门山》原片生成“一舞入青山”1080×1920竖版封面。

**Architecture:** Zsh 构建脚本在约 12 秒抽取原片并 Lanczos 放大；Swift/AppKit 渲染器在左上安全区绘制竖排标题与诗名；壳测试执行构建并验证 PNG、尺寸、RGB 和无透明通道。

**Tech Stack:** Zsh、FFmpeg、Swift/AppKit/CoreText、sips、ripgrep

## Global Constraints

- 不重绘角色，不裁掉栀夏、阿砚、孤帆或“AI生成”标识。
- 主标题固定为“一舞入青山”，小字固定为“李白《望天门山》”。
- 输出固定为 1080×1920 RGB 无透明通道 PNG。

---

### Task 1: 封面构建与验收

**Files:**
- Create: `tests/test_wangtianmenshan_cover.sh`
- Create: `scripts/build_wangtianmenshan_cover.sh`
- Create: `scripts/render_wangtianmenshan_cover.swift`
- Create: `exports/wangtianmenshan-dance-cover-v01.png`

**Interfaces:** Consumes `episodes/wangtianmenshan-15s/assets/video/content-seedance-v01.mp4`; produces the final PNG.

- [ ] Write a failing test requiring an executable build script, renderer and RGB 1080×1920 non-alpha PNG.
- [ ] Run `zsh tests/test_wangtianmenshan_cover.sh`; expect failure for the missing build script.
- [ ] Implement the 12-second frame extraction, vertical title rendering and RGB output conversion.
- [ ] Run the test and inspect the full-resolution cover for subject and text collisions.
- [ ] Commit the plan, script, renderer and test with a Chinese commit message.
