# 「一舞一愿·重新出发」12 秒成片封面 v02 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从无字幕原片 11.900 秒精确取帧，制作一张正面可见、完整保留舞袖与金色前路的 1080×1920「重新出发」封面 v02。

**Architecture:** v02 构建脚本用 FFmpeg 精确取帧，并复用现有 Swift/AppKit 排版器。排版器增加可选放大倍率参数，v01 保持默认 1.15，v02 明确传入 1.12；独立 Shell 门禁验证 v02 输出、取帧时刻与缩略图规格。

**Tech Stack:** zsh、FFmpeg、Swift、AppKit、CoreText、sips

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-09-01-yi-wu-yi-yuan-restart-12s-cover-v02-design.md`。
- 输入固定为无字幕原片的 11.900 秒，底图中心放大 12%。
- 封面文字只允许“一舞一愿”“重新出发”“愿你每一步，都算数”。
- 输出固定为 `exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v02.png`，1080×1920 PNG。
- 完整保留头饰、双臂、舞袖、裙摆和脚部。
- 不加入天宫、色块、贴纸、边框或其他额外文字。
- 不覆盖 v01，不提交或覆盖工作区中与本封面无关的修改。

---

### Task 1: 建立 v02 取帧与输出门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v02.sh`
- Create: `zhixia-feihualing/tests/test_yiwu_yiyuan_restart_cover_zoom.sh`
- Test: `zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v02.sh`
- Test: `zhixia-feihualing/tests/test_yiwu_yiyuan_restart_cover_zoom.sh`

**Interfaces:**
- Consumes: 无字幕原片和待创建的 v02 构建脚本。
- Produces: 对 v02 尺寸、格式、完整解码、独立输出、11.900 秒底图一致性和非法倍率拒绝行为的验收。

- [x] **Step 1: 编写失败门禁**

v02 门禁要求 v01 仍存在，v02 构建脚本可执行；运行构建后验证 v02 为 1080×1920 PNG 且可完整解码。测试使用 FFmpeg 从 11.900 秒生成 1.12 倍中心放大的基准图，对封面不含文字的下半区计算 SSIM，要求不低于 0.94；最后确认 v01 与 v02 文件内容不同。倍率门禁直接调用真实排版器，传入 `1.0` 并要求以 `zoom must be greater than 1` 拒绝。

- [x] **Step 2: 运行门禁并确认按预期失败**

Run: `zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v02.sh`

Expected: v02 门禁输出 `FAIL: missing executable 一舞一愿 restart cover v02 builder`；倍率门禁输出 `FAIL: renderer did not explain the invalid zoom`。

### Task 2: 生成封面 v02

**Files:**
- Modify: `zhixia-feihualing/scripts/render_yiwu_yiyuan_restart_12s_cover.swift`
- Create: `zhixia-feihualing/scripts/build_yiwu_yiyuan_restart_12s_cover_v02.sh`
- Create: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v02.png`

**Interfaces:**
- Consumes: `render_yiwu_yiyuan_restart_12s_cover.swift <base.png> <output.png> [zoom]`，其中 `zoom` 为大于 1 的十进制倍率。
- Produces: 可重复生成的 v02，同时保持 v01 构建脚本继续使用默认 1.15。

- [x] **Step 1: 为排版器增加可选倍率参数**

把固定倍率改为可选第三个位置参数；未传入时使用 1.15，传入无法解析或不大于 1 的值时输出错误并退出。其余文字、字体、颜色和坐标保持不变。

- [x] **Step 2: 编写 v02 构建脚本**

脚本验证原片和排版器存在，使用 FFmpeg 从 11.900 秒输出 RGB PNG 临时底图，再以 `1.12` 调用排版器，写入 v02 新文件。临时目录由 `mktemp` 创建并在退出时清理。

- [x] **Step 3: 运行 v01 与 v02 门禁**

Run:

```bash
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover.sh
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_cover_zoom.sh
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v02.sh
```

Expected: 三项均输出 PASS，证明倍率验证生效、v02 生成且 v01 未回归。

### Task 3: 视觉验收与归档

**Files:**
- Inspect: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v02.png`

**Interfaces:**
- Consumes: Task 2 的正式 v02。
- Produces: 可直接查看和发布的封面及验证证据。

- [x] **Step 1: 检查全尺寸封面**

确认栀夏接近正面，头饰、双臂、舞袖、裙摆和脚部完整；文字不遮挡人物；金色前路保持连续；画面没有正片字幕或黑边。

- [x] **Step 2: 检查缩略图可读性**

生成 270×480 预览，确认“重新出发”仍是第一信息，面部方向、展开双臂和金色前路仍可辨认。

- [x] **Step 3: 运行最终验证**

Run:

```bash
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover.sh
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_cover_zoom.sh
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v02.sh
sips -g pixelWidth -g pixelHeight -g format zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v02.png
ffmpeg -v error -i zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v02.png -f null -
```

Expected: 三项门禁 PASS，v02 为 1080×1920 PNG，FFmpeg 无错误输出。
