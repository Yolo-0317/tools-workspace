# 《一舞一愿·九月好运》三句朗诵 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不重新生成已有两段配音的前提下，新增“所念，皆能如愿。”并合成一条自然覆盖10.08秒的三句栀夏朗诵试听。

**Architecture:** 继续使用项目现有豆包TTS清单与断点复用机制；新版清单沿用原 `audio_slug`，使已有第一段和第三段被识别为 ready，只对新增中句发起一次调用。取得中句真实时长后，用FFmpeg以独立延迟排列三段原始音频，不改变任何一段的语速或音高。

**Tech Stack:** 项目 `generate_episode_audio.py`、豆包 Seed TTS 2.0、FFmpeg、ffprobe、silencedetect。

## Global Constraints

- 固定音色为 `ICL_uranus_zh_female_tianmeihuopo_tob`，`speech_rate=0`。
- 正文固定为“九月，愿所有美好，久久相伴。”“所念，皆能如愿。”“好风凭借力，送我上青云。”
- 复用已有3.864秒第一段与3.048秒诗句，只新增1次豆包TTS调用。
- 不使用 `atempo`、截断、机械拉伸、吟唱、播音腔、朗诵比赛腔或仙侠配音腔。
- 试听总长固定为10.08秒；首句靠近开头，末句最后一字贴近9.8秒，每个句间静音不超过1秒。
- 本轮只生成和合成人声，不修改原视频与原音乐。

---

### Task 1: 建立可断点复用的三句配音清单

**Files:**
- Create: `episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/voice-lines-jiuyue-haoyun-v02.json`
- Read: `episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/voice-lines-jiuyue-haoyun-v01.json`

**Interfaces:**
- Consumes: 已有 `audio_slug=tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01` 及两条 ready 元数据。
- Produces: 三句清单；新增台词ID为 `02-middle-wish`，原诗ID保持 `02-poem` 以复用现有文件。

- [ ] **Step 1: 创建新版清单**

复制v01中的第一段与诗句，不改 `text`、`role`、`revision`、`speech_rate` 和上下文；在两者之间新增：

```json
{
  "id": "02-middle-wish",
  "role": "zhixia",
  "text": "所念，皆能如愿。",
  "revision": 1,
  "speech_rate": 0,
  "gap_before_ms": 400,
  "context_texts": [
    "承接九月祝福，保持同一位栀夏和同一距离。‘所念’轻柔真诚，逗号处自然停连；‘皆能如愿’更明亮、更笃定，但不喊口号、不甜腻、不拖尾。正常语速，只读给定正文。"
  ]
}
```

将原诗的 `gap_before_ms` 改为 `450`，其余字段保持不变。

- [ ] **Step 2: 预览断点计划**

Run:

```bash
python3 scripts/generate_episode_audio.py \
  --episode tiangong-hot-dance-zhixia-ayan-duet-10s \
  --manifest episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/voice-lines-jiuyue-haoyun-v02.json
```

Expected: `已就绪并跳过：2 句`、`待生成：1 句`、`预计产生豆包 TTS 调用：1 次`，唯一待生成ID为 `02-middle-wish`。

- [ ] **Step 3: 提交清单**

```bash
git add zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/voice-lines-jiuyue-haoyun-v02.json
git diff --cached --check
git commit -m "内容：增加九月好运中段祝愿"
```

### Task 2: 生成并验证新增中句

**Files:**
- Create: `assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/02-zhixia-middle-wish.mp3`
- Modify: `assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/audio-metadata.json`
- Modify: `episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/subtitles-tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun.json`

**Interfaces:**
- Consumes: Task 1三句清单、项目 `.env` 中的TTS凭据、用户对本次1次付费调用的明确确认。
- Produces: 新增中句MP3、包含三句真实时长的元数据和自动字幕轴。

- [ ] **Step 1: 在明确确认后仅生成新增台词**

Run:

```bash
python3 scripts/generate_episode_audio.py \
  --episode tiangong-hot-dance-zhixia-ayan-duet-10s \
  --manifest episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/voice-lines-jiuyue-haoyun-v02.json \
  --line 02-middle-wish \
  --generate
```

在交互提示中输入：

```text
GENERATE tiangong-hot-dance-zhixia-ayan-duet-10s
```

Expected: `生成完成：本次生成 1 句`；已有两段未重新请求。

- [ ] **Step 2: 验证中句音频属性和元数据**

Run:

```bash
ffprobe -v error \
  -show_entries format=duration \
  -show_entries stream=codec_name,sample_rate,channels \
  -of json \
  assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/02-zhixia-middle-wish.mp3
```

Expected: MP3、24000Hz、单声道、时长大于1秒；元数据正文严格等于“所念，皆能如愿。”，speaker严格等于固定栀夏音色。

### Task 3: 以真实时长合成10.08秒三句试听

**Files:**
- Create: `assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/full-recitation-preview-three-lines-10.08s-v02.wav`
- Create: `episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/audio-timing-jiuyue-haoyun-v02.json`

**Interfaces:**
- Consumes: 三段未经变速的MP3及各自ffprobe真实时长。
- Produces: 48kHz双声道PCM试听和记录三个起止点的时间文件。

- [ ] **Step 1: 写入三段固定起点时间轴**

第一段从150毫秒开始，中句从4450毫秒开始，诗句从6800毫秒开始。以ffprobe读到的三段真实时长填写各自 `end_ms=start_ms+source_duration_ms`，并写入 `duration_ms=10080`。这组起点让已知第一段结束于4014毫秒、诗句结束于9848毫秒；中句验收时再确认它没有与相邻人声重叠。

- [ ] **Step 2: 合成试听**

Run:

```bash
ffmpeg -y -v error \
  -i assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/01-zhixia-modern-blessing.mp3 \
  -i assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/02-zhixia-middle-wish.mp3 \
  -i assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/02-zhixia-poem.mp3 \
  -filter_complex "[0:a]aresample=48000,adelay=150[a0];[1:a]aresample=48000,adelay=4450[a1];[2:a]aresample=48000,adelay=6800[a2];[a0][a1][a2]amix=inputs=3:duration=longest:normalize=0,apad=pad_dur=10,atrim=duration=10.08,alimiter=limit=0.95[out]" \
  -map "[out]" -ac 2 -ar 48000 -c:a pcm_s16le \
  assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/full-recitation-preview-three-lines-10.08s-v02.wav
```

- [ ] **Step 3: 验证成品边界**

Run:

```bash
ffprobe -v error \
  -show_entries format=duration \
  -show_entries stream=codec_name,sample_rate,channels \
  -of json \
  assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/full-recitation-preview-three-lines-10.08s-v02.wav

ffmpeg -hide_banner \
  -i assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/full-recitation-preview-three-lines-10.08s-v02.wav \
  -af silencedetect=noise=-45dB:d=0.08 -f null -
```

Expected: PCM 16-bit、48000Hz、双声道、总长10.080秒；首个发声不晚于0.50秒，任一中段静音不超过1.00秒，末次发声结束位于9.60至9.90秒。

- [ ] **Step 4: 人工试听**

逐字确认三句均无漏字、增词、错音、重读或截断；确认两处停顿清楚但不空，情绪从温暖祝愿过渡到笃定承接，再到向上展开。若不通过，只调整三段放置时间；未经用户再次授权不重新调用TTS。
