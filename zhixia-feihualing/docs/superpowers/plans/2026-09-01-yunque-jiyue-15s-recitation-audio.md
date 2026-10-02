# 《云阙伎乐》15 秒朗诵音频 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 归档用户确认保留的《云阙伎乐》原片与后续升级约束，并生成一条使用栀夏固定声线、在 15 秒内自然完成的连续朗诵试听音频。

**Architecture:** 单集只使用一次豆包 TTS 调用完成两句现代文与两句唐诗，避免分句生成导致情绪断裂。生成后只裁切头尾静音、设置开场位置和补足总时长，不改变有效人声的速度与音高。

**Tech Stack:** JSON 配音清单、现有豆包 TTS 管线、FFmpeg/FFprobe、zsh 质量门禁。

## Global Constraints

- 朗诵文本固定为“有些美好，并没有真的离开。被人记起时，它就会重新有颜色。只愁歌舞散，化作彩云飞。”
- 使用当前 `zhixia` 固定声线和 `speech_rate=0`，整段只调用一次 TTS。
- 情绪从温柔回望逐渐转为明亮笃定，最后一句舒展上扬但不吟唱、不拖字。
- 最终试听音频为 15 秒、48 kHz、双声道 AAC；最后一句必须在 15 秒内自然结束。
- 原片背景音乐暂不混入本轮纯朗诵试听。
- 后续生成提高人物占比、加强第二高潮、稳定飘带连接，并把唯一事件写成可观察的显色进度。

---

### Task 1: 归档原片与后续升级约束

**Files:**
- Create: `episodes/yunque-jiyue-15s/assets/video/content-seedance-v01.mp4`
- Create: `episodes/yunque-jiyue-15s/README.md`
- Create: `episodes/yunque-jiyue-15s/qa-notes.md`

**Interfaces:**
- Consumes: 用户确认可用的 `67fed3c0-e973-4fcf-a394-477f4863380d.mp4`。
- Produces: 后续配音、字幕和封面使用的稳定单集原片及复盘真源。

- [ ] **Step 1: 复制并探测原片**

复制原片后用 `ffprobe` 校验其为约 15.104 秒、496×864、24 fps、H.264/AAC，并保留 AIGC 元数据。

- [ ] **Step 2: 写入单集说明和复盘**

记录本版成功完成壁画仙境视觉升级；记录第二高潮偏弱、绘卷开场已显色、后段实际为壁画打开云境、人物比例略小和少数飘带靠近手腕。后续约束不得追溯返工本片。

### Task 2: 生成一次连续朗诵并建立质量门禁

**Files:**
- Create: `tests/test_yunque_jiyue_recitation.sh`
- Create: `episodes/yunque-jiyue-15s/voice-lines-continuous-v01.json`
- Create: `assets/audio/yunque-jiyue-15s-continuous-v01/*.mp3`
- Create: `exports/yunque-jiyue-15s-recitation-v01.m4a`

**Interfaces:**
- Consumes: 已确认四句文本、`config/voices.json` 中的 `zhixia` 固定音色。
- Produces: 一条 15 秒纯朗诵试听音频。

- [ ] **Step 1: 写失败门禁**

门禁运行真实清单与成品，校验整段只有一个 TTS 行、逐字文本正确、`speech_rate=0`、情绪上下文完整；成品必须可解码、时长 14.99—15.01 秒，最后有效人声在 14.50—14.95 秒结束。

- [ ] **Step 2: 确认门禁因缺少清单而失败**

运行 `zsh tests/test_yunque_jiyue_recitation.sh`，预期报告缺少连续朗诵清单。

- [ ] **Step 3: 建立清单并预览一次调用计划**

清单只包含 `01-full-recitation`，上下文明确“温柔回望—重新明亮—短暂惋惜—向上舒展”的连续情绪弧线。运行预览后应显示待生成 1 句、预计调用 1 次。

- [ ] **Step 4: 调用 TTS 并合成 15 秒试听版**

生成原始 MP3，探测有效人声起止；只裁切头尾静音并设置约 0.200 秒开场，使用 `apad` 补足 15 秒，不使用 `atempo`、变调或机械拉伸。

- [ ] **Step 5: 运行完整门禁并试听**

运行 `zsh tests/test_yunque_jiyue_recitation.sh` 与完整解码检查；人工试听确认四句连贯、无其他声音、末句在 15 秒内自然收住。
