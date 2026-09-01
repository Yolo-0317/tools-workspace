# 《曲终胡腾》15 秒朗诵音频 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用栀夏固定声线生成四句《曲终胡腾》朗诵，并合成为一条自然结束、不拖腔的 15 秒纯人声试听音频。

**Architecture:** 新建单集 `voice-lines.json`，复用现有豆包 TTS 管线分别生成四条 MP3，再依据真实有效语音时长用 FFmpeg 放置到 15 秒立体声音轨。单句原件保持不变，试听音频只裁切头尾静音、调整句间留白和统一响度，不改变有效人声速度与音高。

**Tech Stack:** JSON 配音清单、现有 Python TTS 管线、FFmpeg/FFprobe、现有栀夏音色配置。

## Global Constraints

- 四句逐字固定，不朗读作者、篇名、标点或说明文字。
- 使用当前 `zhixia` 固定声线和 `speech_rate=0`。
- 禁止机械减速、变调、拉伸、吟唱和句尾拖腔。
- “发”按诗意读作 `fā`。
- 试听音频总时长 15.000 秒，不含背景音乐、视频原声、字幕或其他对白。
- 不修改工作区中已有的无关文件。

---

### Task 1: 建立并校验配音清单

**Files:**
- Create: `episodes/quzhong-huteng-15s/voice-lines.json`

**Interfaces:**
- Consumes: `config/voices.json` 中的 `zhixia` 音色和已确认四句文本。
- Produces: `generate_episode_audio.py` 可读取的 `one-poem-story` 清单。

- [ ] **Step 1: 新建四句配音清单**

四句分别设置 `start_ms` 为 `200`、`3300`、`7300`、`10500`，`speech_rate` 均为 `0`；上下文明确现代文自然说话、古诗自然说诗、末字不拖长以及“发”读 `fā`。

- [ ] **Step 2: 运行只读预览校验**

```bash
python3 scripts/generate_episode_audio.py --episode quzhong-huteng-15s
```

Expected: 显示待生成 4 句、栀夏 4 句、预计调用 4 次，并明确当前未调用语音接口。

- [ ] **Step 3: 检查清单文本和禁用参数**

```bash
python3 -m json.tool episodes/quzhong-huteng-15s/voice-lines.json >/dev/null
rg -n 'speech_rate|atempo|拖腔|发.*fā' episodes/quzhong-huteng-15s/voice-lines.json
```

Expected: JSON 合法；四处 `speech_rate` 均为 `0`；不存在 `atempo`；声音说明包含不拖腔和 `fā` 发音约束。

### Task 2: 生成四条栀夏朗诵

**Files:**
- Create: `assets/audio/quzhong-huteng-15s-v01/*.mp3`
- Create: `episodes/quzhong-huteng-15s/subtitle-plan.json`

**Interfaces:**
- Consumes: `episodes/quzhong-huteng-15s/voice-lines.json`。
- Produces: 四条独立 MP3 和管线自动生成的音频时间信息。

- [ ] **Step 1: 调用现有 TTS 管线**

```bash
python3 scripts/generate_episode_audio.py --episode quzhong-huteng-15s --generate
```

在现有确认门槛中输入 `GENERATE quzhong-huteng-15s`。Expected: 本次生成 4 句，四句均就绪，并写出字幕计划。

- [ ] **Step 2: 检查四条原始音频**

```bash
find assets/audio/quzhong-huteng-15s-v01 -type f -name '*.mp3' -maxdepth 1
ffprobe -v error -show_entries format=duration -of default=nw=1 assets/audio/quzhong-huteng-15s-v01/*.mp3
```

Expected: 恰好四条可解码 MP3，每条时长大于 0；人工试听确认同一声线、句尾无明显拖腔且“发”读作 `fā`。

### Task 3: 合成 15 秒纯人声试听版

**Files:**
- Create: `episodes/quzhong-huteng-15s/assets/audio/quzhong-huteng-15s-recitation-v01.wav`
- Create: `exports/quzhong-huteng-15s-recitation-v01.m4a`

**Interfaces:**
- Consumes: Task 2 的四条 MP3 和真实有效语音时长。
- Produces: 48 kHz 双声道 15 秒 WAV 母版和 M4A 试听版。

- [ ] **Step 1: 探测头尾静音和有效语音时长**

```bash
for file in assets/audio/quzhong-huteng-15s-v01/*.mp3; do ffmpeg -hide_banner -i "$file" -af silencedetect=noise=-45dB:d=0.08 -f null -; done
```

Expected: 得到每句有效语音起止位置；只移除头尾静音，不裁切有效发音。

- [ ] **Step 2: 按真实时长合成 15 秒音轨**

使用 FFmpeg 为四句分别执行 `atrim`、`asetpts`、`aresample=48000`、`aformat=channel_layouts=stereo` 和对应 `adelay`，随后以 `amix=inputs=4:duration=longest:normalize=0` 合并，并用 `loudnorm=I=-18:TP=-3:LRA=7,apad,atrim=0:15` 输出 WAV。若第四句超过 14.300 秒，只压缩句间留白，不使用 `atempo`。

- [ ] **Step 3: 编码试听版**

```bash
ffmpeg -hide_banner -loglevel error -y -i episodes/quzhong-huteng-15s/assets/audio/quzhong-huteng-15s-recitation-v01.wav -c:a aac -b:a 192k -ar 48000 -ac 2 -t 15 exports/quzhong-huteng-15s-recitation-v01.m4a
```

Expected: 得到可播放的 15 秒 M4A。

### Task 4: 完成质量门禁与归档

**Files:**
- Modify: `assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3 的 WAV 母版和 M4A 试听版。
- Produces: 可交付试听音频及资产登记。

- [ ] **Step 1: 验证媒体参数**

```bash
ffprobe -v error -show_entries format=duration:stream=codec_name,sample_rate,channels -of json exports/quzhong-huteng-15s-recitation-v01.m4a
ffmpeg -v error -i exports/quzhong-huteng-15s-recitation-v01.m4a -f null -
```

Expected: 时长为 15.000 秒附近、AAC、48 kHz、双声道并可完整解码。

- [ ] **Step 2: 验证声音内容**

完整试听一次，确认四句顺序和文字正确、无其他声音、声线一致、无拖腔、无机械变速、句间无重叠，最后一句在 14.300 秒前结束并保留自然尾韵。

- [ ] **Step 3: 登记最终采用资产**

只向 `assets/inventory.csv` 增加本集四条原始朗诵、WAV 母版和 M4A 试听版的记录，不改写已有行。

- [ ] **Step 4: 提交本集新增文件**

```bash
git add zhixia-feihualing/episodes/quzhong-huteng-15s/voice-lines.json zhixia-feihualing/episodes/quzhong-huteng-15s/subtitle-plan.json zhixia-feihualing/docs/superpowers/plans/2026-09-01-quzhong-huteng-15s-recitation-audio.md
git commit -m "制作曲终胡腾十五秒朗诵音频"
```

音频二进制是否进入 Git 继续遵循项目现有忽略规则；工作区原有未提交修改不进入本次提交。
