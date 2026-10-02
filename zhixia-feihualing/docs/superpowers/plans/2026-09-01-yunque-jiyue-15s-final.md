# 《云阙伎乐》朗诵字幕成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的《云阙伎乐》原片与 15 秒栀夏朗诵合成为无字幕朗诵版和正式竖排字幕版。

**Architecture:** 复用敦煌系列竖排字幕卡渲染器；先把原片保真放大到 1080×1920，再以原片音轨 0 dB 和朗诵音轨直接混合，不做背景音乐闪避。字幕版直接复制无字幕朗诵版音轨，确保两版声音完全一致。

**Tech Stack:** JSON 字幕计划、Swift/AppKit 字幕卡、FFmpeg/FFprobe、zsh 质量门禁。

## Global Constraints

- 四句字幕与 15 秒朗诵气口一致，第三句题署为“唐·李白《宫中行乐词》”。
- 四句竖排字幕按右、左、右、左交替，避开栀夏脸部和身体中轴。
- 原片背景音乐全程保持原音量，不使用侧链压缩或分段降音量。
- 不改变朗诵速度和音高，不新增对白、音效或第四高潮。
- 输出为 1080×1920、24 fps、H.264、48 kHz 双声道 AAC，并保留原片 AIGC 元数据。

---

### Task 1: 建立成片门禁与字幕计划

**Files:**
- Create: `tests/test_yunque_jiyue_15s_final.sh`
- Create: `episodes/yunque-jiyue-15s/subtitle-plan.json`

**Interfaces:**
- Consumes: 朗诵实际气口和既有竖排字幕渲染器。
- Produces: 四张字幕卡的文字、方向和时间轴契约。

- [ ] **Step 1: 写失败门禁并运行**

门禁先校验四句文字、左右方向、时间轴和李白题署，再要求构建脚本、四张字幕卡、无字幕朗诵版和正式字幕版存在。首次运行应因缺少字幕计划而失败。

- [ ] **Step 2: 写入字幕计划**

字幕时间为 0.200—2.450、3.800—6.780、8.500—9.780、13.608—14.850 秒；现代文去除标点，诗句保持逐句展示。

### Task 2: 构建并验证两版成片

**Files:**
- Create: `scripts/build_yunque_jiyue_15s_final.sh`
- Create: `assets/subtitles/yunque-jiyue-15s/*.png`
- Create: `exports/yunque-jiyue-15s-voiced-v01.mp4`
- Create: `exports/yunque-jiyue-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: 原片、15 秒朗诵、字幕计划和 `render_jiuge_vertical_subtitle_cards.swift`。
- Produces: 无字幕朗诵试听版和正式字幕成片。

- [ ] **Step 1: 写最小构建脚本**

生成四张透明字幕卡；原片以 Lanczos 放大到 1080×1920、24 fps；原片声音保持 0 dB，与朗诵直接混合并只在总线做峰值保护；字幕版复制无字幕版音轨。

- [ ] **Step 2: 运行完整门禁**

校验两份视频均约 15.104 秒、1080×1920、24 fps、H.264/AAC、48 kHz 双声道、完整可解码、AIGC 元数据一致，且两版抽取后的 AAC 音轨哈希相同。

- [ ] **Step 3: 视觉抽帧检查**

抽取四个字幕时段与一个无字幕间隙，确认竖排文字清楚、题署完整、未遮挡栀夏面部，并且字幕只在计划时段出现。
