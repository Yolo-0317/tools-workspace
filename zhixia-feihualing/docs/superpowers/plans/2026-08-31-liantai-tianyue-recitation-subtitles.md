# 《莲台天乐》朗诵字幕高清成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的《莲台天乐》15.093 秒原片制作成栀夏四句舒缓朗诵、逐句竖排字幕、背景音乐全程不降音量的 1080×1920 正式成片。

**Architecture:** 先用 JSON 清单固定诗句、语速与字幕时间轴，并以专用 zsh 门禁锁定原片哈希、文本、时间、无音乐闪避和输出参数。随后复用项目豆包 TTS 流水线生成四句独立音频，专用 FFmpeg 构建脚本完成保真放大、人声排布、原声直接混合、总线峰值保护和透明字幕卡叠加，分别输出无字幕朗诵试听版与正式字幕版。

**Tech Stack:** JSON、Python 豆包 TTS 流水线、Swift/AppKit 字幕卡渲染、FFmpeg、FFprobe、zsh、jq、Git

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-31-liantai-tianyue-recitation-subtitles-design.md`。
- 原片固定为 `episodes/liantai-tianyue-15s/assets/video/content-seedance-v01.mp4`，SHA-256 为 `1561fe69b243e23b66d4a462b95207953b117616e8d4872faa9da3d219d12918`。
- 四句固定为“霜清东林钟。”“水白虎溪月。”“天香生虚空。”“天乐鸣不歇。”，使用栀夏固定音色，不念作者、题目或篇名。
- 字幕时间窗固定为 `0.250—3.200`、`3.500—6.450`、`6.750—9.800`、`10.100—14.650` 秒。
- 第一句题署固定为“唐·李白《庐山东林寺夜怀》”。
- 背景音乐全程保持原始时间结构和相对音量；禁止 `sidechaincompress`、人声区间音量表达式和分段闪避。
- 输出固定为 H.264、1080×1920、24 fps、AAC 192 kbps、48 kHz 双声道，时长约 15.093 秒。
- 正式字幕版直接复制无字幕朗诵版音轨；两个版本提取的 AAC 音轨 SHA-256 必须一致。
- 不重绘、不修复或重新生成原片人物、舞蹈、服装、飘带、香雾、壁画和已有“AI生成”标识。

---

## 文件结构

- `episodes/liantai-tianyue-15s/voice-lines.json`：四句 TTS 输入、语速与语气约束。
- `episodes/liantai-tianyue-15s/subtitle-plan.json`：四张字幕卡的文字、题署和显示时间。
- `tests/test_liantai_tianyue_15s_final.sh`：静态清单、原片哈希、无闪避混音和最终媒体参数门禁。
- `scripts/build_liantai_tianyue_15s_final.sh`：唯一成片构建入口。
- `assets/audio/liantai-tianyue-15s-paced-v01/`：四句 MP3 与生成元数据。
- `assets/subtitles/liantai-tianyue-15s/`：四张透明字幕卡。
- `exports/liantai-tianyue-15s-voiced-v01.mp4`：无字幕朗诵试听版。
- `exports/liantai-tianyue-15s-subtitled-v01.mp4`：正式字幕高清版。

### Task 1: 固定配音字幕契约和失败门禁

**Files:**
- Create: `zhixia-feihualing/episodes/liantai-tianyue-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/liantai-tianyue-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/tests/test_liantai_tianyue_15s_final.sh`

**Interfaces:**
- Consumes: 已确认设计中的诗句、题署、时间窗、原片哈希和混音规则。
- Produces: `voice-lines.json`、`subtitle-plan.json` 以及在音频或成片缺失时可预测失败的测试入口。

- [ ] **Step 1: 写入失败门禁**

测试必须先断言配音与字幕契约：

```zsh
jq -e '
  .episode == "liantai-tianyue-15s" and
  .audio_slug == "liantai-tianyue-15s-paced-v01" and
  [.lines[].role] == ["zhixia","zhixia","zhixia","zhixia"] and
  [.lines[].text] == [
    "霜清东林钟。",
    "水白虎溪月。",
    "天香生虚空。",
    "天乐鸣不歇。"
  ] and
  ([.lines[].speech_rate] | all(. == -35))
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == ["霜清东林钟","水白虎溪月","天香生虚空","天乐鸣不歇"] and
  .[0].start == 0.250 and .[0].end == 3.200 and
  .[1].start == 3.500 and .[1].end == 6.450 and
  .[2].start == 6.750 and .[2].end == 9.800 and
  .[3].start == 10.100 and .[3].end == 14.650 and
  .[0].attribution == "唐·李白《庐山东林寺夜怀》"
' "$subtitle_plan" >/dev/null
```

测试还要检查：原片哈希正确；四个 MP3 存在；构建脚本可执行且不含 `sidechaincompress`、`volume=.*enable` 或 `volume=.*between`；两个输出均可解码且为固定规格；四张字幕卡存在；两个版本音轨哈希一致。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd zhixia-feihualing && zsh tests/test_liantai_tianyue_15s_final.sh`

Expected: FAIL，报告缺少 `voice-lines.json`，而不是 zsh 语法错误。

- [ ] **Step 3: 创建配音清单**

```json
{
  "episode": "liantai-tianyue-15s",
  "format": "one-poem-story",
  "theme": "莲台天乐十五秒四句舒缓朗诵",
  "theme_slug": "liantai-tianyue-15s",
  "audio_slug": "liantai-tianyue-15s-paced-v01",
  "lines": [
    {"id":"01-zhixia-line-one","role":"zhixia","text":"霜清东林钟。","revision":1,"speech_rate":-35,"gap_before_ms":0,"context_texts":["保持栀夏固定清透女声，年轻、舒缓、克制并有石窟空间感；霜清自然展开，东林钟沉静收住。自然说诗，不念作者、题目、篇名或其他内容，不使用播音腔、吟唱、耳语或夸张拖字。"]},
    {"id":"02-zhixia-line-two","role":"zhixia","text":"水白虎溪月。","revision":1,"speech_rate":-35,"gap_before_ms":300,"context_texts":["保持同一位栀夏、同一距离感和舒缓语速；水白清透，虎溪月略提明度并保留短余韵。自然说诗，不念作者、题目、篇名或其他内容。"]},
    {"id":"03-zhixia-line-three","role":"zhixia","text":"天香生虚空。","revision":1,"speech_rate":-35,"gap_before_ms":300,"context_texts":["保持同一位栀夏固定声线，语气轻缓空灵但仍是自然说诗；天香舒展，虚空不做玄幻化拖腔。不念作者、题目、篇名或其他内容。"]},
    {"id":"04-zhixia-line-four","role":"zhixia","text":"天乐鸣不歇。","revision":1,"speech_rate":-35,"gap_before_ms":300,"context_texts":["保持同一位栀夏固定声线，从容开阔；天乐不做神谕式强调，鸣不歇在画面结束前完整收住并留自然余韵。不念作者、题目、篇名或其他内容。"]}
  ]
}
```

- [ ] **Step 4: 创建字幕计划**

```json
[
  {"id":"01-poem-line-one","kind":"poem","text":"霜清东林钟","attribution":"唐·李白《庐山东林寺夜怀》","start":0.250,"end":3.200},
  {"id":"02-poem-line-two","kind":"poem","text":"水白虎溪月","start":3.500,"end":6.450},
  {"id":"03-poem-line-three","kind":"poem","text":"天香生虚空","start":6.750,"end":9.800},
  {"id":"04-poem-line-four","kind":"poem","text":"天乐鸣不歇","start":10.100,"end":14.650}
]
```

- [ ] **Step 5: 再次运行门禁确认进入下一预期失败点**

Run: `cd zhixia-feihualing && zsh tests/test_liantai_tianyue_15s_final.sh`

Expected: FAIL，报告缺少第一句 MP3 或构建脚本。

- [ ] **Step 6: 提交契约与门禁**

```bash
git add zhixia-feihualing/episodes/liantai-tianyue-15s/voice-lines.json \
  zhixia-feihualing/episodes/liantai-tianyue-15s/subtitle-plan.json \
  zhixia-feihualing/tests/test_liantai_tianyue_15s_final.sh
git commit -m "建立莲台天乐朗诵字幕门禁"
```

### Task 2: 生成并校验四句栀夏朗诵

**Files:**
- Create: `zhixia-feihualing/assets/audio/liantai-tianyue-15s-paced-v01/01-zhixia-zhixia-line-one.mp3`
- Create: `zhixia-feihualing/assets/audio/liantai-tianyue-15s-paced-v01/02-zhixia-zhixia-line-two.mp3`
- Create: `zhixia-feihualing/assets/audio/liantai-tianyue-15s-paced-v01/03-zhixia-zhixia-line-three.mp3`
- Create: `zhixia-feihualing/assets/audio/liantai-tianyue-15s-paced-v01/04-zhixia-zhixia-line-four.mp3`
- Create: `zhixia-feihualing/assets/audio/liantai-tianyue-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 的 `voice-lines.json` 与项目现有栀夏音色配置。
- Produces: 四个单声道 MP3 及其元数据，供 Task 3 按实际有效语音区间混音。

- [ ] **Step 1: 预览生成计划**

Run: `cd zhixia-feihualing && python3 scripts/generate_episode_audio.py --episode liantai-tianyue-15s`

Expected: 显示待生成 4 句、栀夏 4 句、预计调用 4 次；不创建音频。

- [ ] **Step 2: 调用已配置的 TTS**

Run: `cd zhixia-feihualing && print 'GENERATE liantai-tianyue-15s' | python3 scripts/generate_episode_audio.py --episode liantai-tianyue-15s --generate`

Expected: 生成四个 MP3 和 `audio-metadata.json`；日志不输出 API Key。

- [ ] **Step 3: 校验媒体和元数据**

```zsh
for f in zhixia-feihualing/assets/audio/liantai-tianyue-15s-paced-v01/*.mp3; do
  ffprobe -v error -show_entries stream=codec_name,sample_rate,channels \
    -show_entries format=duration -of json "$f" | jq -e '
      .streams[0].codec_name == "mp3" and
      .streams[0].sample_rate == "24000" and
      .streams[0].channels == 1 and
      (.format.duration | tonumber) > 1.0
    ' >/dev/null
done
```

同时使用 `jq` 检查 `audio-metadata.json` 的四句文本、角色、revision 与清单一致。

- [ ] **Step 4: 测量有效语音区间**

对每句运行 `silencedetect=noise=-42dB:d=0.08`，记录开头静音、有效语音结束点与总时长。构建脚本中的 `atrim` 必须使用实测值；每句有效人声目标占自身时间窗 82%—90%，低于 80%必须试听并调整 TTS 语速或后期 `atempo`。

### Task 3: 构建高清朗诵版与字幕版

**Files:**
- Create: `zhixia-feihualing/scripts/build_liantai_tianyue_15s_final.sh`
- Reuse: `zhixia-feihualing/scripts/render_story_subtitle_cards.swift`
- Create: `zhixia-feihualing/assets/subtitles/liantai-tianyue-15s/*.png`
- Create: `zhixia-feihualing/exports/liantai-tianyue-15s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/liantai-tianyue-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: 原片、四句 MP3、字幕计划和 Task 2 的有效语音测量结果。
- Produces: 音轨固定的无字幕朗诵版和复用该音轨的正式字幕版。

- [ ] **Step 1: 创建专用构建脚本**

视频链固定为：

```text
scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,
crop=1080:1920:(iw-1080)/2:0,
hqdn3d=0.6:0.6:1.8:1.8,
unsharp=5:5:0.22:3:3:0,
fps=24,format=yuv420p
```

四句分别经过实测 `atrim`、`asetpts=PTS-STARTPTS`、自然范围内的 `atempo`、短淡入淡出、48 kHz 立体声转换，再使用以下延迟定位：

```text
adelay=250|250
adelay=3500|3500
adelay=6750|6750
adelay=10100|10100
```

四句人声合并后执行高通、轻度均衡、压缩与响度整理。原声只转换采样率和声道，最终固定使用：

```text
[bed][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,
alimiter=limit=0.870964:attack=5:release=80:level=false[aout]
```

字幕卡四个窗口各使用 0.120 秒淡入淡出；正式版使用 `-map 0:a:0 -c:a copy` 复制试听版音轨。

- [ ] **Step 2: 赋予构建入口执行权限并运行**

Run: `chmod +x zhixia-feihualing/scripts/build_liantai_tianyue_15s_final.sh && cd zhixia-feihualing && zsh scripts/build_liantai_tianyue_15s_final.sh`

Expected: 生成四张 PNG 和两个 MP4；脚本输出两条绝对成片路径。

- [ ] **Step 3: 运行完整门禁**

Run: `cd zhixia-feihualing && zsh tests/test_liantai_tianyue_15s_final.sh`

Expected: `PASS: Liantai Tianyue four-line recitation HD finals are ready`。

- [ ] **Step 4: 提交构建入口**

```bash
git add zhixia-feihualing/scripts/build_liantai_tianyue_15s_final.sh \
  zhixia-feihualing/tests/test_liantai_tianyue_15s_final.sh
git commit -m "制作莲台天乐朗诵字幕高清成片"
```

### Task 4: 视听验收、登记与交付

**Files:**
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify: `zhixia-feihualing/episodes/liantai-tianyue-15s/README.md`

**Interfaces:**
- Consumes: Task 3 的两个成片、四句音频和四张字幕卡。
- Produces: 可追溯的正式成片登记、单集完成状态和用户可直接播放的交付路径。

- [ ] **Step 1: 验证视频音频参数与音轨一致性**

```zsh
for f in \
  zhixia-feihualing/exports/liantai-tianyue-15s-voiced-v01.mp4 \
  zhixia-feihualing/exports/liantai-tianyue-15s-subtitled-v01.mp4; do
  ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,sample_rate,channels \
    -show_entries format=duration -of json "$f"
  ffmpeg -v error -i "$f" -f null -
done
```

提取两个输出的 AAC 音轨并比较 SHA-256；预期完全一致。

- [ ] **Step 2: 检查响度和峰值**

Run: `ffmpeg -hide_banner -i zhixia-feihualing/exports/liantai-tianyue-15s-subtitled-v01.mp4 -filter_complex ebur128=peak=true -f null -`

Expected: 无削波，真峰值不高于 −1.0 dBTP；背景音乐在人声起止点没有可闻抽吸或突降。

- [ ] **Step 3: 抽取视觉验收拼图**

在 0.500、3.800、7.000、10.500、14.300 秒抽帧，检查：字幕在左侧安全区；首句题署正确；无错字、截断或遮脸；右下角已有标识保留；人物比例和画面内容未改变。

- [ ] **Step 4: 更新登记与单集状态**

在 `assets/inventory.csv` 增加四句 voice、无字幕 voiced-preview 和正式 final-subtitled 条目；在 README 标记朗诵字幕高清成片完成，并记录“背景音乐全程原音量、无闪避”。不登记临时构建文件。

- [ ] **Step 5: 最终验证与提交**

Run:

```zsh
cd zhixia-feihualing
zsh tests/test_liantai_tianyue_15s_final.sh
git diff --check -- assets/inventory.csv episodes/liantai-tianyue-15s/README.md
awk -F, 'NF != 9 {print NR ":" NF ":" $0}' assets/inventory.csv
```

Expected: 门禁通过、无空白错误、CSV 每行均为 9 列。

```bash
git add zhixia-feihualing/assets/inventory.csv \
  zhixia-feihualing/episodes/liantai-tianyue-15s/README.md
git commit -m "归档莲台天乐朗诵字幕成片"
```
