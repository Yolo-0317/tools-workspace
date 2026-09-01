# 《一舞一愿·欢喜得意》10 秒朗诵试听 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用栀夏固定音色生成一条有感情的连续朗诵试听，并核对它是否适配 10 秒天宫恰恰视频。

**Architecture:** 新建独立单集配音清单，通过既有 `generate_episode_audio.py` 与豆包 Seed-TTS 2.0 生成一条原始 MP3。情绪通过单条 `context_texts` 控制，正文、speaker 与正常语速保持固定；生成后使用 `ffprobe` 记录真实时长，不进行加速、截断或变调。

**Tech Stack:** JSON 配音清单、现有 Python TTS 流水线、豆包 Seed-TTS 2.0、FFprobe

## Global Constraints

- 正文固定为“愿你心有欢喜，步步生风。春风得意马蹄疾，一日看尽长安花。”
- 使用 `config/voices.json` 中 `zhixia` 固定音色和 `speech_rate=0`。
- 只生成一条连续朗诵，不拆句，不添加背景音乐。
- 不使用后期加速、变调、截断或拖腔修正时长。
- 本轮只验证朗诵，不生成 Seedance 视频、字幕成片或最终混音。

---

### Task 1: 建立并验证连续朗诵清单

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/voice-lines.json`

**Interfaces:**
- Consumes: `zhixia-feihualing/config/voices.json` 中的 `zhixia` 声线。
- Produces: 一条可被既有 TTS 流水线读取的 `one-poem-story` 清单。

- [ ] **Step 1: 写入配音清单**

清单包含唯一台词 `01-full-recitation`、固定正文、`speech_rate=0`、`start_ms=100`，以及亲切明亮、逐步上扬、开阔收束的完整情绪说明。

- [ ] **Step 2: 运行预览验证**

Run: `python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-huanxi-cha-cha-10s`

Expected: 待生成 1 句、豆包 TTS 调用 1 次、当前为预览模式。

- [ ] **Step 3: 提交清单**

```bash
git add episodes/yiwu-yiyuan-huanxi-cha-cha-10s/voice-lines.json
git commit -m "配置一舞一愿欢喜得意朗诵"
```

### Task 2: 生成并验收原始试听

**Files:**
- Create: `zhixia-feihualing/assets/audio/yiwu-yiyuan-huanxi-cha-cha-10s-voice-v01/01-zhixia-full-recitation.mp3`
- Create: `zhixia-feihualing/assets/audio/yiwu-yiyuan-huanxi-cha-cha-10s-voice-v01/01-zhixia-full-recitation.json`

**Interfaces:**
- Consumes: Task 1 的配音清单与项目现有豆包 TTS 凭据。
- Produces: 一条原始 MP3 试听及可追溯的生成元数据。

- [ ] **Step 1: 执行一次已确认的付费生成**

Run: `printf 'GENERATE yiwu-yiyuan-huanxi-cha-cha-10s\n' | python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-huanxi-cha-cha-10s --generate`

Expected: 生成完成，本次生成 1 句。

- [ ] **Step 2: 检查音频技术属性与时长**

Run: `ffprobe -v error -show_entries format=duration:stream=codec_name,sample_rate,channels -of json assets/audio/yiwu-yiyuan-huanxi-cha-cha-10s-voice-v01/01-zhixia-full-recitation.mp3`

Expected: MP3、24000 Hz、单声道、有效时长大于 0；如不在 8.500—9.700 秒，仅如实汇报，不修改播放速度。

- [ ] **Step 3: 交付试听**

在最终回复中直接展示绝对路径音频，并报告实测时长和是否进入 10 秒适配目标。
