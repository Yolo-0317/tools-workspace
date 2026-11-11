# 「一舞一愿·重新出发」12 秒成片封面 v03 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从无字幕原片 12.300 秒精确取帧，制作用户指定最后一格的 1080×1920「重新出发」封面 v03。

**Architecture:** 新建 v03 构建脚本，用 FFmpeg 精确截取 12.300 秒，并复用现有 Swift/AppKit 排版器，以 1.12 倍中心放大生成独立输出。新建真实构建门禁，验证尺寸、格式、解码、取帧一致性以及不覆盖 v01/v02。

**Tech Stack:** zsh、FFmpeg、Swift、AppKit、CoreText、sips

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-09-01-yi-wu-yi-yuan-restart-12s-cover-v03-design.md`。
- 输入固定为无字幕原片的 12.300 秒，底图中心放大 12%。
- 封面文字只允许“一舞一愿”“重新出发”“愿你每一步，都算数”。
- 输出固定为 `exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v03.png`，1080×1920 PNG。
- 完整保留头饰、双臂、舞袖、裙摆、脚部、圆形云台和金色前路。
- 不覆盖 v01、v02，不提交或覆盖工作区中与本封面无关的修改。

---

### Task 1: 建立 v03 真实构建门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v03.sh`
- Test: `zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v03.sh`

**Interfaces:**
- Consumes: 无字幕原片、已有 v01/v02 和待创建的 v03 构建脚本。
- Produces: 对 v03 尺寸、格式、解码、独立输出和 12.300 秒底图一致性的验收。

- [x] **Step 1: 编写失败门禁**

测试先要求 v01、v02 存在和 v03 构建脚本可执行。构建后验证 v03 为 1080×1920 PNG 且可完整解码；使用 FFmpeg 从 12.300 秒生成 1.12 倍中心放大的基准图，对不含文字的下半区计算 SSIM，要求不低于 0.94；最后确认 v03 与 v01、v02 均不相同。

- [x] **Step 2: 运行门禁并确认按预期失败**

Run: `zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v03.sh`

Expected: `FAIL: missing executable 一舞一愿 restart cover v03 builder`。

### Task 2: 生成并检查 v03

**Files:**
- Create: `zhixia-feihualing/scripts/build_yiwu_yiyuan_restart_12s_cover_v03.sh`
- Create: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v03.png`
- Inspect: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v03.png`

**Interfaces:**
- Consumes: 无字幕原片 12.300 秒和排版器接口 `<base.png> <output.png> 1.12`。
- Produces: 可重复生成且不覆盖旧版本的正式 v03。

- [x] **Step 1: 编写 v03 构建脚本**

脚本验证原片和排版器，使用 FFmpeg 从 12.300 秒输出 RGB PNG 临时底图，以 `1.12` 调用排版器并写入 v03。临时目录由 `mktemp` 创建并在退出时清理。

- [x] **Step 2: 运行门禁并确认通过**

Run: `zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v03.sh`

Expected: `PASS: 一舞一愿 restart cover v03 is ready`。

- [x] **Step 3: 检查全尺寸和缩略图**

全尺寸检查人物侧脸、抬臂、舞袖、裙摆、脚部、云台和金色前路完整；生成 270×480 预览，确认主标题及动作方向可辨认。

- [x] **Step 4: 运行全部封面回归门禁**

Run:

```bash
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover.sh
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_cover_zoom.sh
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v02.sh
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_restart_12s_cover_v03.sh
sips -g pixelWidth -g pixelHeight -g format zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v03.png
ffmpeg -v error -i zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v03.png -f null -
```

Expected: 四项门禁 PASS，v03 为 1080×1920 PNG，FFmpeg 无错误输出。
