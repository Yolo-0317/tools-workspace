# 《惊涛》舞蹈版封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《惊涛》无字幕配音版 4.000 秒旋转帧制作一张突出“栀夏·惊涛一舞”的 1080×1920 PNG 发布封面。

**Architecture:** 构建脚本使用 FFmpeg 从无字幕配音版精确截取底图并以 Lanczos 放大；独立 Swift 渲染器在底图上绘制双列竖排主标题和小字题署。回归测试调用真实构建脚本，检查最终 PNG 的媒体规格、可解码性、非透明输出和资产登记。

**Tech Stack:** Zsh、FFmpeg、FFprobe、Swift、AppKit、CoreText

## Global Constraints

- 底图固定来自 `exports/jingtao-voiced-v01.mp4` 的 4.000 秒，不从带字幕成片截图。
- 输出固定为 `exports/jingtao-dance-cover-v01.png`，1080×1920、PNG、无透明底。
- 左侧竖排双列标题由较小的“栀夏”和较大的“惊涛一舞”组成。
- 辅助题署固定为“苏轼《念奴娇·赤壁怀古》”，字号和亮度弱于主标题。
- 标题不得覆盖栀夏、长袖主要圆弧或阿砚。
- 不重绘人物、动物、浪势、光线或背景；保留右下角“AI生成”标识。

---

### Task 1: 建立封面输出失败门禁

**Files:**
- Create: `tests/test_jingtao_dance_cover.sh`
- Test: `tests/test_jingtao_dance_cover.sh`

**Interfaces:**
- Consumes: `scripts/build_jingtao_dance_cover.sh` 的可执行入口。
- Produces: 对封面构建流程、最终尺寸、PNG 编码、非透明像素和资产登记的自动门禁。

- [x] **Step 1: 写入失败测试**

测试要求构建脚本、渲染器和无字幕配音版存在；执行构建后，用 FFprobe 断言输出为 1080×1920 PNG，用 FFmpeg 完整解码一帧，用 `pix_fmt` 排除透明输出，并在 `assets/inventory.csv` 中查找 `jingtao-dance-cover-v01`。

- [x] **Step 2: 运行测试并确认正确失败**

Run: `zsh tests/test_jingtao_dance_cover.sh`

Expected: FAIL，提示缺少 `scripts/build_jingtao_dance_cover.sh` 或 `scripts/render_jingtao_dance_cover.swift`。

### Task 2: 实现精确截帧和标题渲染

**Files:**
- Create: `scripts/build_jingtao_dance_cover.sh`
- Create: `scripts/render_jingtao_dance_cover.swift`
- Create: `exports/jingtao-dance-cover-v01.png`
- Test: `tests/test_jingtao_dance_cover.sh`

**Interfaces:**
- Consumes: `exports/jingtao-voiced-v01.mp4` 与系统行楷、楷体字体。
- Produces: `render_jingtao_dance_cover.swift <base.png> <output.png>` 和最终 1080×1920 PNG。

- [x] **Step 1: 写入构建脚本**

脚本创建临时目录，执行 `ffmpeg -ss 4.000` 截取一帧并缩放为 1080×1920 RGB 底图，再调用 Swift 渲染器；退出时清理临时目录。

- [x] **Step 2: 写入 Swift 渲染器**

渲染器加载底图并注册项目现用行楷、楷体字体；在左侧安全区绘制小列“栀夏”、大列“惊涛一舞”和较弱题署“苏轼《念奴娇·赤壁怀古》”。文字使用暖象牙白与深色柔影，最终编码为无透明视觉内容的 PNG。

- [x] **Step 3: 运行回归测试**

Run: `zsh tests/test_jingtao_dance_cover.sh`

Expected: `PASS: Jingtao dance cover is valid, 1080x1920, and inventoried`

- [x] **Step 4: 视觉抽检**

使用本地图片查看器检查最终 PNG：栀夏和完整袖弧清楚、阿砚可辨认、标题不遮角色与动作、题署弱于主标题、右下角“AI生成”标识保留。

### Task 3: 登记封面并完成验收

**Files:**
- Modify: `episodes/jingtao/README.md`
- Modify: `assets/inventory.csv`
- Test: `tests/test_jingtao_dance_cover.sh`

**Interfaces:**
- Consumes: 已完成视觉抽检的 `exports/jingtao-dance-cover-v01.png`。
- Produces: 单集状态与资产清单中的正式封面记录。

- [x] **Step 1: 更新单集状态**

在《惊涛》单集 README 中记录封面路径、4.000 秒取帧、双列竖排标题、1080×1920 规格和无重绘边界。

- [x] **Step 2: 登记资产**

向 `assets/inventory.csv` 追加 `jingtao-dance-cover-v01`，类型为 `cover`，状态为 `final`，来源为本地 FFmpeg 截帧与 Swift 排版，权利说明为已确认项目视频的衍生资产。

- [x] **Step 3: 运行最终验证**

Run: `zsh tests/test_jingtao_dance_cover.sh && git diff --check`

Expected: 测试输出 PASS，差异检查无输出，命令退出码为 0。

- [x] **Step 4: 提交实现**

Run:

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-29-jingtao-cover.md \
  zhixia-feihualing/scripts/build_jingtao_dance_cover.sh \
  zhixia-feihualing/scripts/render_jingtao_dance_cover.swift \
  zhixia-feihualing/tests/test_jingtao_dance_cover.sh \
  zhixia-feihualing/episodes/jingtao/README.md \
  zhixia-feihualing/assets/inventory.csv
git commit -m "制作惊涛舞蹈版封面"
```

Expected: 只提交《惊涛》封面相关脚本、测试、计划和登记文件；PNG 保留为本地导出资产。
