# Denggao Final Postproduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的《登高》Seedance 原片与四段固定音色合成为带横排互动字幕、竖排诗句字幕的 1080×1920、24fps 发布前成片，并记录后续角色动态表演标准。

**Architecture:** `docs/realistic-visual-style.md` 保存后续视频的通用身体表达标准；《登高》使用独立字幕清单和构建脚本，复用现有透明字幕卡渲染器。构建脚本保留原片音乐与环境声，在四段配音区间降低约 5dB，叠加定时 TTS 和字幕后输出 H.264/AAC 成片。

**Tech Stack:** Markdown、JSON、Zsh、Swift/AppKit 字幕卡渲染、FFmpeg、FFprobe、Shell 验收测试。

## Global Constraints

- 不重新生成或修改《登高》画面、角色母板和 Seedance 提示词。
- 保持原生 24fps，不进行光流、AI 补帧或运动插帧。
- 输出固定为 1080×1920、10.100 秒、H.264 `yuv420p`、AAC 48kHz 双声道。
- 保留原片背景音乐、环境声与“AI生成”标识。
- 四段配音从 600ms、2160ms、3740ms、6690ms 开始；配音区间原声降低约 5dB。
- 两句互动使用横排字幕，两句诗使用左侧竖排字幕；不增加标题、作者、Logo 或片尾。
- 栀夏在后续视频中必须有持续身体表达；阿砚必须同步领镜或回应。

---

### Task 1: 记录后续角色动态表演标准

**Files:**
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`

**Interfaces:**
- Consumes: 用户确认的栀夏与阿砚动态表演标准。
- Produces: 后续场景卡、分镜和 Seedance 提示词共同遵守的通用角色表演要求。

- [ ] **Step 1: 在人物与角色章节加入持续身体表达规则**

写明栀夏不得以原地站立朗诵作为默认表演；诗意适合时使用一个连续古典舞身韵或舞步动机，沉静诗句使用克制的转身、步法、重心、目光和衣袖动作。动作必须承接诗句情绪并触发或回应镜头运动。

- [ ] **Step 2: 加入阿砚同步参与规则**

写明阿砚必须通过领镜、追随诗意物象、转头、跃步、停步、抬头或墨尾动作参与同一节奏，不得长期静止成为装饰物，也不得抢占栀夏的诗句表演。

- [ ] **Step 3: 验证文档格式**

Run:

```bash
git diff --check -- zhixia-feihualing/docs/realistic-visual-style.md
```

Expected: 无输出，退出码为 0。

### Task 2: 用测试定义《登高》成片契约

**Files:**
- Create: `zhixia-feihualing/tests/test_denggao_10s_final_video.sh`

**Interfaces:**
- Consumes: `exports/denggao-10s-subtitled-v01.mp4` 与 `assets/subtitles/denggao-10s/*.png`。
- Produces: 对成片分辨率、帧率、时长、音视频编码、采样率、声道数和字幕卡尺寸的可重复验收。

- [ ] **Step 1: 写失败测试**

测试必须断言：输出文件存在；视频为 1080×1920、H.264、24/1fps；音频为 AAC、48000Hz、双声道；时长在 10.05 至 10.15 秒；四张字幕卡存在且为 720×1280；FFmpeg 可完整解码成片。

- [ ] **Step 2: 运行测试并确认因成片尚未生成而失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_denggao_10s_final_video.sh
```

Expected: 非零退出，首个失败原因为 `exports/denggao-10s-subtitled-v01.mp4` 不存在。

### Task 3: 实现字幕、混音与成片构建

**Files:**
- Create: `zhixia-feihualing/episodes/denggao-10s/subtitle-plan.json`
- Create: `zhixia-feihualing/scripts/build_denggao_10s_final.sh`
- Create: `zhixia-feihualing/episodes/denggao-10s/assets/video/content-seedance-v01.mp4`
- Generate: `zhixia-feihualing/assets/subtitles/denggao-10s/*.png`
- Generate: `zhixia-feihualing/exports/denggao-10s-subtitled-v01.mp4`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 已确认原片、四段 MP3、字幕清单与现有 `render_story_subtitle_cards.swift`。
- Produces: `exports/denggao-10s-subtitled-v01.mp4`。

- [ ] **Step 1: 保存原片副本**

将下载文件原样复制为 `episodes/denggao-10s/assets/video/content-seedance-v01.mp4`；用 SHA-256 校验复制前后一致，不改动下载文件。

- [ ] **Step 2: 创建字幕清单**

按顺序定义四项：`01-ayan-hook` dialogue“风起了！”、`02-zhixia-hook` dialogue“看江上。”、`03-zhixia-poem-one` poem“无边落木萧萧下”、`04-zhixia-poem-two` poem“不尽长江滚滚来”；四项 `attribution` 均为 `null`。

- [ ] **Step 3: 创建最小构建脚本**

脚本生成 720×1280 透明字幕卡；将原片 Lanczos 放大为 1080×1920、24fps；将字幕卡缩放到 1080×1920 后按 `0.600—2.064`、`2.160—3.624`、`3.740—6.572`、`6.690—8.946` 秒叠加。原声在四段区间乘以 `0.562341`，四段 TTS 规范到约 `-18 LUFS` 后延迟至既定起点，与原声混合并限制峰值。

- [ ] **Step 4: 登记原片与最终成片**

在 `assets/inventory.csv` 增加 `denggao-10s-seedance-v01` 和 `denggao-10s-subtitled-v01` 两条记录，分别指向保存的原片副本与最终输出。

- [ ] **Step 5: 构建成片**

Run:

```bash
zsh zhixia-feihualing/scripts/build_denggao_10s_final.sh
```

Expected: 生成四张字幕卡与 `exports/denggao-10s-subtitled-v01.mp4`。

- [ ] **Step 6: 运行测试并确认通过**

Run:

```bash
zsh zhixia-feihualing/tests/test_denggao_10s_final_video.sh
```

Expected: 输出 `denggao 10s final video: PASS`，退出码为 0。

### Task 4: 视觉与声音抽检

**Files:**
- Inspect: `zhixia-feihualing/exports/denggao-10s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: Task 3 的成片。
- Produces: 对字幕位置、时间、画面保真和混音可用性的最终验收结果。

- [ ] **Step 1: 抽取四个字幕时间点与结尾帧**

分别抽取约 1.0、2.6、4.8、7.7、9.7 秒画面，确认横排与竖排字幕类型正确、无错字、不遮挡主要面部、阿砚关键动作和“AI生成”标识。

- [ ] **Step 2: 检查音轨连续性与响度**

使用 FFmpeg 检查完整解码和静音断层；使用响度分析记录综合响度与峰值。配音区间必须可辨，原片音乐与环境声不能消失。

- [ ] **Step 3: 提交已验证产物与源文件**

```bash
git add zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/tests/test_denggao_10s_final_video.sh \
  zhixia-feihualing/episodes/denggao-10s/subtitle-plan.json \
  zhixia-feihualing/scripts/build_denggao_10s_final.sh \
  zhixia-feihualing/episodes/denggao-10s/assets/video/content-seedance-v01.mp4 \
  zhixia-feihualing/assets/inventory.csv \
  zhixia-feihualing/assets/subtitles/denggao-10s \
  zhixia-feihualing/exports/denggao-10s-subtitled-v01.mp4
git commit -m "完成登高对白字幕成片"
```
