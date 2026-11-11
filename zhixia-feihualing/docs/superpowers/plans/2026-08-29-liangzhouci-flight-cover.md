# 《凉州词》飞天封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从已确认的《凉州词》原始视频生成“飞越玉门关”竖版封面。

**Architecture:** 构建脚本从约 12 秒处抽取原始视频帧并以 Lanczos 放大到 1080×1920；独立 Swift/AppKit 渲染器叠加三列竖排中文。壳测试执行完整构建并验证输出格式、尺寸、色彩空间和透明通道。

**Tech Stack:** zsh、FFmpeg、Swift/AppKit/CoreText、sips、ripgrep

## Global Constraints

- 只使用原始 Seedance 视频帧，不重绘或替换人物。
- 主标题固定为“飞越玉门关”。
- 输出固定为 1080×1920 RGB 无透明通道 PNG。
- 文字不得遮挡栀夏、阿砚、黄河、关塞、飞行轨迹和右下角原片标识。

---

### Task 1: 封面自动构建与格式验收

**Files:**
- Create: `tests/test_liangzhouci_flight_cover.sh`
- Create: `scripts/build_liangzhouci_flight_cover.sh`
- Create: `scripts/render_liangzhouci_flight_cover.swift`
- Create: `exports/liangzhouci-flight-cover-v01.png`

**Interfaces:**
- Consumes: `episodes/liangzhouci-15s/assets/video/content-seedance-v01.mp4`
- Produces: `exports/liangzhouci-flight-cover-v01.png`

- [ ] **Step 1: Write the failing test**

  新建壳测试，要求构建脚本可执行、渲染器存在，并在运行构建后检查 PNG、1080×1920、RGB 和无透明通道。

- [ ] **Step 2: Run test to verify it fails**

  Run: `zsh tests/test_liangzhouci_flight_cover.sh`

  Expected: FAIL with `missing executable Liangzhouci flight cover build script`。

- [ ] **Step 3: Write minimal implementation**

  构建脚本使用 `ffmpeg -ss 12.000` 抽帧、Lanczos 放大并调用 Swift 渲染器；渲染器注册系统行楷和楷体，绘制“王之涣《凉州词》”“飞越玉门关”“栀夏与阿砚”三列竖排文字。

- [ ] **Step 4: Run test to verify it passes**

  Run: `zsh tests/test_liangzhouci_flight_cover.sh`

  Expected: `PASS: Liangzhouci flight cover is ready`。

- [ ] **Step 5: Inspect the rendered image**

  打开最终 PNG，确认双角色、黄河、关塞、飞行流光与标题均清晰，且文字没有遮挡主体。
