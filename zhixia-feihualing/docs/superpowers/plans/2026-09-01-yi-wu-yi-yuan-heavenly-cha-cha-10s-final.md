# 《一舞一愿·欢喜得意》10 秒天宫恰恰朗诵字幕成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一份无字幕朗诵试听版和一份正式字幕版 10 秒天宫恰恰视频，并验证两版具有相同音轨、准确字幕和发布级媒体参数。

**Architecture:** 使用一个 JSON 清单驱动既有 Swift 字幕卡渲染器；新增一个 Zsh 构建脚本，先把原片裁至10秒、保真放大并与朗诵完成一次统一混音，再从同一临时母版分别复制无字幕版和叠加字幕版。测试脚本先验证清单和构建入口，再执行构建并检查媒体参数、时长、音轨哈希、完整解码与字幕抽帧。

**Tech Stack:** Zsh、FFmpeg/FFprobe、Swift/AppKit、JSON、SHA-256

## Global Constraints

- 原片从0.000秒裁至10.000秒，不变速、不补帧。
- 朗诵固定使用已确认的10秒WAV，不再次改速、变调、截断或重新生成。
- 字幕固定为0.720—2.560、2.800—4.160、4.360—10.000秒三张卡。
- 现代字幕横排行楷；古诗左侧双列竖排并显示“唐·孟郊《登科后》”。
- 音乐由人声侧链驱动避让约4—5dB，停顿处自然恢复。
- 输出为1080×1920、24fps、H.264、48kHz双声道AAC，目标时长10.000秒或不超过一帧误差。
- 两版使用同一条最终AAC音轨，区别仅为字幕。

---

### Task 1: 字幕清单与失败门禁

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/subtitle-plan-final-v01.json`
- Create: `zhixia-feihualing/tests/test_yi_wu_yi_yuan_huanxi_cha_cha_10s_final.sh`

**Interfaces:**
- Consumes: 已确认的三张字幕时间和既有 `render_story_subtitle_cards.swift` 数据结构。
- Produces: 构建脚本可直接读取的三项字幕清单，以及对输入、输出和媒体参数的自动门禁。

- [ ] **Step 1: 写入三张字幕卡清单**

清单必须依次包含：

```json
[
  {"id":"01-blessing","kind":"modern","text":"愿你心有欢喜","start":0.72,"end":2.56},
  {"id":"02-step","kind":"modern","text":"步步生风","start":2.8,"end":4.16},
  {"id":"03-poem","kind":"poem","text":"春风得意马蹄疾，一日看尽长安花","attribution":"唐·孟郊《登科后》","start":4.36,"end":10.0}
]
```

- [ ] **Step 2: 写入失败门禁**

测试脚本先检查清单文本与时间、原片和朗诵存在、构建脚本可执行。构建后使用FFprobe检查两版1080×1920、24fps、H.264、48kHz双声道AAC与10秒时长；抽取两版AAC为原始ADTS并计算SHA-256必须一致；使用FFmpeg完整解码两版。

- [ ] **Step 3: 运行测试确认失败**

Run: `bash tests/test_yi_wu_yi_yuan_huanxi_cha_cha_10s_final.sh`

Expected: `FAIL: missing executable heavenly cha-cha final builder`。

- [ ] **Step 4: 提交门禁与清单**

```bash
git add episodes/yiwu-yiyuan-huanxi-cha-cha-10s/subtitle-plan-final-v01.json tests/test_yi_wu_yi_yuan_huanxi_cha_cha_10s_final.sh
git commit -m "建立天宫恰恰朗诵字幕门禁"
```

### Task 2: 构建与视觉验收

**Files:**
- Create: `zhixia-feihualing/scripts/build_yi_wu_yi_yuan_huanxi_cha_cha_10s_final.sh`
- Create: `zhixia-feihualing/exports/yiwu-yiyuan-huanxi-cha-cha-10s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/yiwu-yiyuan-huanxi-cha-cha-10s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: Task 1字幕清单、Seedance原片、10秒朗诵WAV和既有Swift字幕渲染器。
- Produces: 音轨相同的无字幕试听版和正式字幕版。

- [ ] **Step 1: 编写最小构建脚本**

脚本先在临时目录渲染三张透明字幕卡；随后一次性完成原片裁切、Lanczos放大、居中轻裁、克制降噪锐化、朗诵处理、原声侧链避让和限制器，生成临时朗诵母版。无字幕版直接复制该母版；字幕版只重编码视频叠加三张字幕卡，AAC音轨使用stream copy。

- [ ] **Step 2: 运行构建**

Run: `bash scripts/build_yi_wu_yi_yuan_huanxi_cha_cha_10s_final.sh`

Expected: 输出两份MP4绝对路径。

- [ ] **Step 3: 运行完整门禁**

Run: `bash tests/test_yi_wu_yi_yuan_huanxi_cha_cha_10s_final.sh`

Expected: `PASS: heavenly cha-cha 10s voiced and subtitled finals are ready`。

- [ ] **Step 4: 抽帧视觉验收**

在1.500、3.300、5.500和9.900秒从字幕版抽帧，确认两张现代字幕与古诗题署可读，不遮挡面容、身体中轴和主要脚步。

- [ ] **Step 5: 检查响度与真峰值**

Run: `ffmpeg -hide_banner -i exports/yiwu-yiyuan-huanxi-cha-cha-10s-subtitled-v01.mp4 -af ebur128=peak=true -f null -`

Expected: 无削波，真峰值低于0dBFS；朗诵清楚且原音乐仍保留热烈恰恰拍点。

- [ ] **Step 6: 提交构建脚本**

```bash
git add scripts/build_yi_wu_yi_yuan_huanxi_cha_cha_10s_final.sh
git commit -m "完成天宫恰恰朗诵字幕成片"
```
