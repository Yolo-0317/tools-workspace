# 《鼓催柘枝》舞蹈版封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《鼓催柘枝》无字幕高清配音版 7.500 秒精确截帧，制作“栀夏＋鼓催柘枝”竖排标题的 1080×1920 正式发布封面。

**Architecture:** 构建脚本只负责校验输入、精确截帧和调用渲染器；Swift/AppKit 渲染器只负责在原始帧上绘制确定性竖排文字。Shell 测试先验证文件缺失会失败，再构建封面并检查 PNG 规格、不透明度、关键文字和资产登记。

**Tech Stack:** zsh、FFmpeg/ffprobe、Swift、AppKit、CoreText、PNG、CSV。

## Global Constraints

- 唯一底图为 `exports/gucuizhezhi-15s-voiced-v01.mp4` 的 7.500 秒帧，不从烧录字幕成片取帧。
- 输出固定为 `exports/gucuizhezhi-dance-cover-v01.png`，1080×1920，无透明像素。
- 左侧竖排双列为小字“栀夏”和大字“鼓催柘枝”，辅助题署为“唐·白居易《柘枝妓》”。
- 文字使用暖象牙白行楷与楷体、轻微深色柔影，不遮挡脸、躯干、上扬手臂、主要飘带或右下角 AI 标识。
- 不调用图片生成，不重绘人物，不改变画面、调色、服装、飘带或背景，不加入完整诗句、标签、额外水印和边框。
- 只提交本次封面脚本、测试、计划和资产记录，保留工作区其他改动。

---

### Task 1: 建立失败测试

**Files:**
- Create: `zhixia-feihualing/tests/test_gucuizhezhi_dance_cover.sh`
- Test: `zhixia-feihualing/exports/gucuizhezhi-dance-cover-v01.png`

**Interfaces:**
- Consumes: 已存在的无字幕高清配音版、预期构建脚本与渲染器路径。
- Produces: 一个可执行验收入口，验证构建、PNG 规格、完全不透明和资产清单记录。

- [x] **Step 1: 写失败测试**

测试依次检查 `exports/gucuizhezhi-15s-voiced-v01.mp4`、构建脚本、渲染器和资产清单；随后调用构建脚本，并用 `ffprobe` 断言 PNG 为 1080×1920，用 alpha 通道统计断言 `YMIN=255`，最后检查资产 ID `gucuizhezhi-dance-cover-v01`。

- [x] **Step 2: 运行测试确认失败**

Run: `zsh tests/test_gucuizhezhi_dance_cover.sh`

Expected: FAIL，报告缺少 `build_gucuizhezhi_dance_cover.sh` 或渲染器，而不是语法错误。

### Task 2: 实现确定性封面渲染

**Files:**
- Create: `zhixia-feihualing/scripts/build_gucuizhezhi_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/render_gucuizhezhi_dance_cover.swift`
- Create: `zhixia-feihualing/exports/gucuizhezhi-dance-cover-v01.png`

**Interfaces:**
- Consumes: 无字幕高清配音版中的 7.500 秒 1080×1920 RGB 帧。
- Produces: 无透明底、带三组准确竖排文字的 1080×1920 PNG。

- [x] **Step 1: 写最小构建脚本**

脚本使用以下精确取帧命令生成临时底图，然后调用 Swift 渲染器：

```zsh
ffmpeg -hide_banner -loglevel error -y \
  -ss 7.500 -i "$source_video" -frames:v 1 \
  -vf "format=rgb24" "$base"
swift "$renderer" "$base" "$output"
```

- [x] **Step 2: 写本地文字渲染器**

注册现有行楷和楷体字体，在 1080×1920 画布原样绘制底图；使用左侧安全区的三列坐标绘制“栀夏”“鼓催柘枝”“唐·白居易《柘枝妓》”，使用暖象牙白与深色柔影。渲染器只接收 `<base.png> <output.png>` 两个参数。

- [x] **Step 3: 运行测试确认通过**

Run: `zsh tests/test_gucuizhezhi_dance_cover.sh`

Expected: 构建先完成，但在资产清单尚未登记时只因缺少 `gucuizhezhi-dance-cover-v01` 记录而失败；PNG 媒体检查已经通过。

### Task 3: 视觉验收与归档

**Files:**
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify: `zhixia-feihualing/docs/superpowers/plans/2026-08-30-gucuizhezhi-cover.md`

**Interfaces:**
- Consumes: Task 2 的正式封面。
- Produces: 视觉确认、唯一资产记录和可重复验证的正式交付。

- [x] **Step 1: 查看原尺寸封面**

检查栀夏正脸、身体、上扬手臂和蓝橙飘带完整清楚；标题未遮挡人物与 AI 标识；没有诗句字幕残留、乱码、边框或新增图像元素。

- [x] **Step 2: 登记资产清单**

新增 `gucuizhezhi-dance-cover-v01`，记录 1080×1920、取自无字幕配音版 7.500 秒、Swift 精确排版、保留 AI 标识、无图像模型重绘。

- [x] **Step 3: 运行最终验证**

重新运行专用测试、`ffmpeg -v error -i exports/gucuizhezhi-dance-cover-v01.png -frames:v 1 -f null -`、CSV 九列与 ID 唯一检查及 `git diff --check`。

- [x] **Step 4: 提交封面**

只暂存本次封面脚本、渲染器、测试、计划与资产记录，使用中文提交：

```bash
git commit -m '制作鼓催柘枝舞蹈封面'
```
