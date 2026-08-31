# 《飞袂绿腰》朗诵字幕成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的《飞袂绿腰》无文字特效轻修母版制作成栀夏四句自然朗诵、逐句竖排字幕、背景音乐和既有特效声音全程不降音量的 1080×1920 正式成片。

**Architecture:** 先用两个 JSON 清单固定 TTS 文本、正常语速和字幕时间轴，并用专用 zsh 门禁锁定轻修母版哈希、开场 1.300 秒留白、无后期变速、0 dB 主床和输出参数。随后复用项目豆包 TTS 流水线生成四句独立音频；专用 FFmpeg 脚本只裁去每句头尾静音，把人声叠加到轻修母版原声上，再使用透明字幕卡生成正式版。无字幕版复制轻修母版视频流，字幕版复制无字幕版音轨，保证已有视觉特效不被重复处理且两版音轨一致。

**Tech Stack:** JSON、Python 豆包 TTS 流水线、Swift/AppKit 字幕卡渲染、FFmpeg、FFprobe、zsh、jq、Git。

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-31-feimei-lvyao-recitation-subtitles-design.md`。
- 唯一视频输入为 `exports/feimei-lvyao-15s-repaired-v01.mp4`，SHA-256 固定为 `1df9482117c07833f8c7efaa23bc56f4d2cd76010002580db87e95e70bf4a6a5`。
- 四句固定为“南国有佳人。”“轻盈绿腰舞。”“华筵九秋暮。”“飞袂拂云雨。”，使用栀夏固定声线，不念作者、题目或篇名。
- TTS 固定使用正常速度 `speech_rate=0`；后期禁止任何 `atempo`、音高改变或音素拉伸。
- 朗诵和字幕时间窗固定为 `1.300—3.450`、`4.100—6.250`、`7.050—9.200`、`11.100—13.350` 秒。
- 第一句题署固定为 `唐·李群玉《长沙九日登东楼观舞》`。
- 0.000—1.300 秒无朗诵字幕；13.350—15.093 秒保留舞蹈、音乐与环境余韵。
- 轻修母版原声作为 0 dB 主床；禁止对主床使用 `volume`、`loudnorm`、`sidechaincompress`、人声区间表达式或分段闪避。
- 输出固定为 H.264、1080×1920、24 fps、AAC 192 kbps、48 kHz 双声道，时长 15.05—15.15 秒。
- 无字幕版与字幕版提取出的 AAC 音轨 SHA-256 必须一致，两个输出的 AIGC 容器标识必须与输入一致。
- 不重绘、不修复或重新生成栀夏、舞蹈、服装、飘带和环境，不重复叠加已有光痕、辉光、曝光脉冲或声音重音。
- 只提交本计划涉及的文件，不带入工作区其他既有修改。

---

## 文件结构

- `episodes/feimei-lvyao-15s/voice-lines.json`：四句 TTS 文本、正常语速和表演约束。
- `episodes/feimei-lvyao-15s/subtitle-plan.json`：四张字幕卡的文字、题署和显示时间。
- `tests/test_feimei_lvyao_15s_final.sh`：文本、时间、输入哈希、自然语速、0 dB 主床、字幕卡和成片规格门禁。
- `scripts/build_feimei_lvyao_15s_final.sh`：唯一朗诵字幕成片构建入口。
- `assets/audio/feimei-lvyao-15s-paced-v01/`：四句 MP3 与生成元数据。
- `assets/subtitles/feimei-lvyao-15s/`：四张透明字幕卡。
- `exports/feimei-lvyao-15s-voiced-v01.mp4`：无字幕朗诵版。
- `exports/feimei-lvyao-15s-subtitled-v01.mp4`：正式字幕版。

### Task 1: 固定配音字幕契约与失败门禁

**Files:**
- Create: `zhixia-feihualing/episodes/feimei-lvyao-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/feimei-lvyao-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/tests/test_feimei_lvyao_15s_final.sh`

**Interfaces:**
- Consumes: 已确认设计中的诗句、题署、四个时间窗、轻修母版哈希和混音规则。
- Produces: TTS 清单、字幕清单以及在音频或构建脚本缺失时可预测失败的门禁入口。

- [ ] **Step 1: 写入失败门禁**

测试首先断言配音清单：

```zsh
jq -e '
  .episode == "feimei-lvyao-15s" and
  .audio_slug == "feimei-lvyao-15s-paced-v01" and
  [.lines[].role] == ["zhixia","zhixia","zhixia","zhixia"] and
  [.lines[].text] == [
    "南国有佳人。",
    "轻盈绿腰舞。",
    "华筵九秋暮。",
    "飞袂拂云雨。"
  ] and
  ([.lines[].speech_rate] | all(. == 0))
' "$voice_manifest" >/dev/null
```

测试继续断言字幕清单：

```zsh
jq -e '
  length == 4 and
  [.[].text] == ["南国有佳人","轻盈绿腰舞","华筵九秋暮","飞袂拂云雨"] and
  [.[].start] == [1.300,4.100,7.050,11.100] and
  [.[].end] == [3.450,6.250,9.200,13.350] and
  .[0].attribution == "唐·李群玉《长沙九日登东楼观舞》"
' "$subtitle_plan" >/dev/null
```

门禁还必须检查：轻修母版 SHA-256 正确；四个 MP3 存在；四个经头尾静音裁切后的有效音频都不超过各自字幕窗口；构建脚本可执行且不包含 `atempo`，不对 `[bed]` 使用 `volume`、`loudnorm` 或 `sidechaincompress`；四张字幕卡存在；两个输出可解码并满足固定规格；两版 AAC 音轨哈希一致；AIGC 标识与输入一致。

- [ ] **Step 2: 运行测试并确认失败原因**

Run: `cd zhixia-feihualing && zsh tests/test_feimei_lvyao_15s_final.sh`

Expected: FAIL，提示缺少 `voice-lines.json`，而不是 zsh 或 jq 语法错误。

- [ ] **Step 3: 创建配音清单**

```json
{
  "episode": "feimei-lvyao-15s",
  "format": "one-poem-story",
  "theme": "飞袂绿腰十五秒四句自然朗诵",
  "theme_slug": "feimei-lvyao-15s",
  "audio_slug": "feimei-lvyao-15s-paced-v01",
  "lines": [
    {"id":"01-zhixia-line-one","role":"zhixia","text":"南国有佳人。","revision":1,"speech_rate":0,"gap_before_ms":0,"context_texts":["这是十五秒《飞袂绿腰》的第一句画外朗诵。保持栀夏固定清透女声，年轻、自然、温柔而克制；南国有佳人清雅引入并自然收句。使用正常说诗语速，不念作者、题目、篇名或其他内容，不使用播音腔、吟唱、耳语、拖字或额外感叹。"]},
    {"id":"02-zhixia-line-two","role":"zhixia","text":"轻盈绿腰舞。","revision":1,"speech_rate":0,"gap_before_ms":0,"context_texts":["保持同一位栀夏、同一距离感和自然语速；轻盈略提明度，绿腰舞清楚落下，不解释舞名。自然说诗，不念作者、题目、篇名或其他内容，不吟唱、不拖腔。"]},
    {"id":"03-zhixia-line-three","role":"zhixia","text":"华筵九秋暮。","revision":1,"speech_rate":0,"gap_before_ms":0,"context_texts":["保持同一位栀夏固定声线和正常语速；华筵清楚，九秋暮略收情绪但不压低到耳语。自然说诗，不念作者、题目、篇名或其他内容，不使用播音腔、吟唱或拖字。"]},
    {"id":"04-zhixia-line-four","role":"zhixia","text":"飞袂拂云雨。","revision":1,"speech_rate":0,"gap_before_ms":0,"context_texts":["这是十五秒《飞袂绿腰》的最后一句。保持同一位栀夏固定声线与自然语速；飞袂略舒展，拂云雨自然收住并留下呼吸余韵，不拖长末字。不念作者、题目、篇名或其他内容，不吟唱、不使用仙侠配音腔。"]}
  ]
}
```

- [ ] **Step 4: 创建字幕计划**

```json
[
  {"id":"01-poem-line-one","kind":"poem","text":"南国有佳人","attribution":"唐·李群玉《长沙九日登东楼观舞》","start":1.300,"end":3.450},
  {"id":"02-poem-line-two","kind":"poem","text":"轻盈绿腰舞","start":4.100,"end":6.250},
  {"id":"03-poem-line-three","kind":"poem","text":"华筵九秋暮","start":7.050,"end":9.200},
  {"id":"04-poem-line-four","kind":"poem","text":"飞袂拂云雨","start":11.100,"end":13.350}
]
```

- [ ] **Step 5: 再次运行门禁并确认进入下一预期失败点**

Run: `cd zhixia-feihualing && zsh tests/test_feimei_lvyao_15s_final.sh`

Expected: FAIL，提示缺少第一句 MP3 或构建脚本。

- [ ] **Step 6: 提交契约与门禁**

```bash
git add zhixia-feihualing/episodes/feimei-lvyao-15s/voice-lines.json \
  zhixia-feihualing/episodes/feimei-lvyao-15s/subtitle-plan.json \
  zhixia-feihualing/tests/test_feimei_lvyao_15s_final.sh
git commit -m "建立飞袂绿腰朗诵字幕门禁"
```

### Task 2: 生成并校验四句自然朗诵

**Files:**
- Create: `zhixia-feihualing/assets/audio/feimei-lvyao-15s-paced-v01/01-zhixia-zhixia-line-one.mp3`
- Create: `zhixia-feihualing/assets/audio/feimei-lvyao-15s-paced-v01/02-zhixia-zhixia-line-two.mp3`
- Create: `zhixia-feihualing/assets/audio/feimei-lvyao-15s-paced-v01/03-zhixia-zhixia-line-three.mp3`
- Create: `zhixia-feihualing/assets/audio/feimei-lvyao-15s-paced-v01/04-zhixia-zhixia-line-four.mp3`
- Create: `zhixia-feihualing/assets/audio/feimei-lvyao-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 的 `voice-lines.json` 与项目现有栀夏音色配置。
- Produces: 四个 24 kHz 单声道 MP3 和生成元数据，供 Task 3 使用同一头尾静音裁切算法排入固定时间轴。

- [ ] **Step 1: 预览 TTS 调用计划**

Run: `cd zhixia-feihualing && python3 scripts/generate_episode_audio.py --episode feimei-lvyao-15s`

Expected: 显示待生成 4 句、栀夏 4 句、预计调用 4 次；不创建音频。

- [ ] **Step 2: 调用已配置的豆包 TTS**

Run: `cd zhixia-feihualing && print 'GENERATE feimei-lvyao-15s' | python3 scripts/generate_episode_audio.py --episode feimei-lvyao-15s --generate`

Expected: 生成四个 MP3 和 `audio-metadata.json`；日志不输出 API Key。

- [ ] **Step 3: 校验媒体与元数据**

```zsh
for audio_file in zhixia-feihualing/assets/audio/feimei-lvyao-15s-paced-v01/*.mp3; do
  ffprobe -v error -show_entries stream=codec_name,sample_rate,channels \
    -show_entries format=duration -of json "$audio_file" | jq -e '
      .streams[0].codec_name == "mp3" and
      .streams[0].sample_rate == "24000" and
      .streams[0].channels == 1 and
      (.format.duration | tonumber) > 1.0
    ' >/dev/null
done
```

同时使用 `jq` 检查 `audio-metadata.json` 的四句文本、角色、revision 和 `speech_rate=0` 与清单一致。

- [ ] **Step 4: 测量经头尾静音裁切后的有效时长**

每句使用同一非破坏性滤镜：

```text
silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,
areverse,
silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,
areverse
```

把裁切结果临时输出为 WAV 后使用 `ffprobe` 测量。第一至第三句必须不超过 2.150 秒，第四句必须不超过 2.250 秒；任何一句超窗时仅重新生成该句，禁止通过加速、截断有效人声或侵占下一句时间窗处理。

### Task 3: 构建无字幕朗诵版与正式字幕版

**Files:**
- Create: `zhixia-feihualing/scripts/build_feimei_lvyao_15s_final.sh`
- Reuse: `zhixia-feihualing/scripts/render_story_subtitle_cards.swift`
- Create: `zhixia-feihualing/assets/subtitles/feimei-lvyao-15s/*.png`
- Create: `zhixia-feihualing/exports/feimei-lvyao-15s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/feimei-lvyao-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: 轻修母版、Task 2 的四句 MP3、字幕计划和项目既有字幕渲染器。
- Produces: 保留原视频流的无字幕朗诵版，以及复用相同音轨的正式字幕版。

- [ ] **Step 1: 实现专用构建脚本**

构建脚本先渲染四张透明字幕卡。四句分别使用 Task 2 的双向头尾静音裁切滤镜、`asetpts=PTS-STARTPTS`、不超过 0.035 秒淡入和 0.120 秒淡出、48 kHz 立体声转换，并使用以下延迟：

```text
adelay=1300|1300
adelay=4100|4100
adelay=7050|7050
adelay=11100|11100
```

人声合并后使用：

```text
highpass=f=90,
equalizer=f=2600:t=q:w=1.0:g=1.8,
acompressor=threshold=0.08:ratio=2:attack=10:release=120:makeup=1.35,
loudnorm=I=-15:TP=-2:LRA=7
```

主床与人声固定使用：

```text
[0:a]aresample=48000,aformat=channel_layouts=stereo[bed];
[bed][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,
alimiter=limit=0.891251:attack=5:release=80:level=false[aout]
```

无字幕版使用 `-map 0:v:0 -c:v copy`，只重新编码混合后的 AAC 音轨；保留输入元数据并使用 `use_metadata_tags+faststart`。字幕版把四张字幕卡分别在固定窗口内以 0.120 秒淡入淡出覆盖到无字幕版视频上，使用 `libx264 -preset slow -crf 17` 编码画面，并用 `-map 0:a:0 -c:a copy` 原样复制无字幕版音轨。

- [ ] **Step 2: 运行构建入口**

Run: `chmod +x zhixia-feihualing/scripts/build_feimei_lvyao_15s_final.sh && cd zhixia-feihualing && zsh scripts/build_feimei_lvyao_15s_final.sh`

Expected: 生成四张 PNG 和两个 MP4；脚本输出两条绝对成片路径。

- [ ] **Step 3: 运行完整门禁**

Run: `cd zhixia-feihualing && zsh tests/test_feimei_lvyao_15s_final.sh`

Expected: `PASS: Feimei Lvyao four-line recitation finals are ready`。

- [ ] **Step 4: 提交构建入口与测试**

```bash
git add zhixia-feihualing/scripts/build_feimei_lvyao_15s_final.sh \
  zhixia-feihualing/tests/test_feimei_lvyao_15s_final.sh
git commit -m "制作飞袂绿腰朗诵字幕成片"
```

### Task 4: 视听验收、登记与交付

**Files:**
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify: `zhixia-feihualing/episodes/feimei-lvyao-15s/README.md`

**Interfaces:**
- Consumes: Task 3 的两个成片、四句音频和四张字幕卡。
- Produces: 可追溯的正式成片登记、单集状态和后续封面制作入口。

- [ ] **Step 1: 验证成片参数、元数据与音轨一致性**

```zsh
for final_video in \
  zhixia-feihualing/exports/feimei-lvyao-15s-voiced-v01.mp4 \
  zhixia-feihualing/exports/feimei-lvyao-15s-subtitled-v01.mp4; do
  ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,sample_rate,channels \
    -show_entries format=duration:format_tags=AIGC -of json "$final_video"
  ffmpeg -v error -i "$final_video" -f null -
done
```

从两个输出分别提取 AAC 码流并比较 SHA-256；预期完全一致。两个输出的 AIGC 标签必须与轻修母版一致。

- [ ] **Step 2: 检查响度、峰值与 0 dB 主床**

Run: `ffmpeg -hide_banner -i zhixia-feihualing/exports/feimei-lvyao-15s-subtitled-v01.mp4 -filter_complex ebur128=peak=true -f null -`

Expected: 无削波，真峰值不高于 −1.0 dBTP；构建脚本中 `[bed]` 路径没有 `volume`、`loudnorm` 或 `sidechaincompress`，人声开始和结束处没有可闻抽吸或音乐突降。

- [ ] **Step 3: 抽取字幕视觉验收拼图**

在 0.800、1.500、4.500、7.500、11.500、13.800 秒抽帧。确认 0.800 秒仍无字幕；其余画面中诗句和首句题署正确，字幕位于左上安全区，没有遮挡栀夏面部、冠饰、上举手臂、主要飘带、承重脚或右下角 AI 标识。

- [ ] **Step 4: 更新本集说明和资产台账**

在 `README.md` 标记朗诵字幕成片完成，记录“正常语速、无后期变速、背景音乐与特效声音全程 0 dB、两版音轨一致”。在 `assets/inventory.csv` 增加四句 voice、无字幕 voiced-preview 和正式 final-subtitled 共六行，使用实际媒体规格、时长与最终哈希；不登记临时 WAV 和构建目录。

- [ ] **Step 5: 最终验证与提交**

Run:

```zsh
cd zhixia-feihualing
zsh tests/test_feimei_lvyao_15s_final.sh
git diff --check -- assets/inventory.csv episodes/feimei-lvyao-15s/README.md
awk -F, 'NF != 9 {print NR ":" NF ":" $0}' assets/inventory.csv
```

Expected: 门禁通过，`git diff --check` 无输出，CSV 每行均为 9 列。

```bash
git add zhixia-feihualing/assets/inventory.csv \
  zhixia-feihualing/episodes/feimei-lvyao-15s/README.md
git commit -m "归档飞袂绿腰朗诵字幕成片"
```
