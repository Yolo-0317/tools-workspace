# 《凉州词》15 秒朗诵字幕 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已确认可用的15.093秒《凉州词》Seedance成片加入栀夏四句全诗朗诵、随真实语音出现的竖排字幕，输出可发布的1080×1920正式成片。

**Architecture:** 将用户提供的原片归档到单集目录，通过项目现有豆包TTS清单生成四句独立配音，根据有效人声区间裁切、轻微调速并排入15秒时间轴。复用透明PNG竖排字幕卡渲染器，由单一FFmpeg构建脚本完成画面放大、字幕叠加、人声区间原声压低、人声混合和峰值保护。

**Tech Stack:** JSON、Python豆包TTS、Swift/AppKit字幕渲染、FFmpeg、FFprobe、Zsh、jq

## Global Constraints

- 栀夏独诵王之涣《凉州词》四句，不增加阿砚对白、标题、作者口播或额外旁白。
- 四句分别生成、句间保留自然留白；第一句从片头开始，第四句对齐双角色飞起与玉门关揭示，并在14.6秒前结束。
- 字幕使用项目已验证的米白色行楷竖排诗句模板，随真实有效语音出现；首句附“唐·王之涣”题署，其余句不重复。
- 保留Seedance原音乐与环境声，仅在人声区间平滑压低约5dB，不整体替换原声。
- 输出1080×1920、24fps、H.264/AAC、15.0—15.2秒，保留原片“AI生成”标识，综合峰值不高于-1dBFS。
- 不重新生成或修复Seedance画面，不制作封面或发布文案，不提交密钥、未关联资产或工作区中其他用户改动。

---

### Task 1: 归档原片并建立失败门禁

**Files:**
- Create: `episodes/liangzhouci-15s/assets/video/content-seedance-v01.mp4`
- Create: `tests/test_liangzhouci_15s_final.sh`
- Test: `episodes/liangzhouci-15s/voice-lines.json`
- Test: `episodes/liangzhouci-15s/subtitle-plan.json`
- Test: `scripts/build_liangzhouci_15s_final.sh`
- Test: `exports/liangzhouci-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: `/Users/huan.yu/Downloads/c1a9b75a-ca60-4dc8-aebe-b29ad8b4c7b0.mp4`、四句诗文、预期输出规格。
- Produces: 单集内固定原片和一个对清单、时间轴、构建脚本、字幕卡数量及成片规格进行检查的Zsh门禁。

- [ ] **Step 1: 复制并核对原片**

Run:

```bash
mkdir -p episodes/liangzhouci-15s/assets/video
cp /Users/huan.yu/Downloads/c1a9b75a-ca60-4dc8-aebe-b29ad8b4c7b0.mp4 episodes/liangzhouci-15s/assets/video/content-seedance-v01.mp4
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate -of json episodes/liangzhouci-15s/assets/video/content-seedance-v01.mp4
```

Expected: 时长15.0—15.2秒，视频496×864、24fps，同时含视频流和音频流。

- [ ] **Step 2: 写入失败门禁**

`tests/test_liangzhouci_15s_final.sh` 必须检查：

```text
配音角色依次为四个zhixia
诗文依次为黄河远上白云间、一片孤城万仞山、羌笛何须怨杨柳、春风不度玉门关
字幕起止递增且不重叠
第一句在0.5秒内开始
第四句在14.0—14.6秒结束
第一句题署为唐·王之涣
透明字幕卡数量为4
成片为1080×1920、24fps、H.264/AAC、15.0—15.2秒
```

- [ ] **Step 3: 运行门禁确认红灯**

Run: `zsh tests/test_liangzhouci_15s_final.sh`

Expected: FAIL，首先报告缺少`voice-lines.json`、`subtitle-plan.json`或可执行构建脚本。

- [ ] **Step 4: 提交原片和门禁**

```bash
git add episodes/liangzhouci-15s/assets/video/content-seedance-v01.mp4 tests/test_liangzhouci_15s_final.sh
git commit -m "测试：建立凉州词成片门禁"
```

### Task 2: 生成四句栀夏朗诵

**Files:**
- Create: `episodes/liangzhouci-15s/voice-lines.json`
- Create: `assets/audio/liangzhouci-15s-paced-v01/01-zhixia-zhixia-line-one.mp3`
- Create: `assets/audio/liangzhouci-15s-paced-v01/02-zhixia-zhixia-line-two.mp3`
- Create: `assets/audio/liangzhouci-15s-paced-v01/03-zhixia-zhixia-line-three.mp3`
- Create: `assets/audio/liangzhouci-15s-paced-v01/04-zhixia-zhixia-line-four.mp3`
- Create: `assets/audio/liangzhouci-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: `config/voices.json` 中的`zhixia`固定音色映射、四句诗文与每句表演语境。
- Produces: 四个独立MP3及`audio-metadata.json`，供时间轴和混音脚本测量有效语音区间。

- [ ] **Step 1: 写入配音清单**

`episodes/liangzhouci-15s/voice-lines.json` 使用：

```json
{
  "episode": "liangzhouci-15s",
  "format": "one-poem-story",
  "theme": "凉州词十五秒全诗朗诵",
  "theme_slug": "liangzhouci-15s",
  "audio_slug": "liangzhouci-15s-paced-v01",
  "lines": [
    {"id": "01-zhixia-line-one", "role": "zhixia", "text": "黄河远上白云间。", "revision": 1, "gap_before_ms": 0},
    {"id": "02-zhixia-line-two", "role": "zhixia", "text": "一片孤城万仞山。", "revision": 1, "gap_before_ms": 900},
    {"id": "03-zhixia-line-three", "role": "zhixia", "text": "羌笛何须怨杨柳。", "revision": 1, "gap_before_ms": 900},
    {"id": "04-zhixia-line-four", "role": "zhixia", "text": "春风不度玉门关。", "revision": 1, "gap_before_ms": 900}
  ]
}
```

实际清单必须为每句补充设计规格中的`context_texts`，明确固定18岁声线、苍茫开阔的本集表演层、句内重音及禁止播音腔、戏曲腔、拖腔和额外口播。

- [ ] **Step 2: 运行清单测试并预览生成计划**

Run:

```bash
python3 -m unittest tests.test_generate_episode_audio tests.test_zhixia_tts_manifest
python3 scripts/generate_episode_audio.py --episode liangzhouci-15s
```

Expected: 单元测试全部PASS；预览显示四句待生成、四次TTS调用，输出目录为`assets/audio/liangzhouci-15s-paced-v01`。

- [ ] **Step 3: 调用固定音色并生成配音**

Run: `python3 scripts/generate_episode_audio.py --episode liangzhouci-15s --generate`

Interactive confirmation: `GENERATE liangzhouci-15s`

Expected: 生成四个非空MP3和`audio-metadata.json`，元数据记录实际供应商、音色、文本和文件路径，不记录API密钥。

- [ ] **Step 4: 测量每句有效语音边界**

Run:

```bash
for f in assets/audio/liangzhouci-15s-paced-v01/*.mp3; do
  ffmpeg -hide_banner -i "$f" -af silencedetect=noise=-38dB:d=0.08 -f null - 2>&1
done
```

Expected: 每句都能确定有效起声与收声边界；文本完整、无多读、无截断。

- [ ] **Step 5: 提交配音清单与生成资产**

```bash
git add episodes/liangzhouci-15s/voice-lines.json assets/audio/liangzhouci-15s-paced-v01
git commit -m "制作：生成凉州词四句朗诵"
```

### Task 3: 编排真实时间轴并构建正式成片

**Files:**
- Create: `episodes/liangzhouci-15s/subtitle-plan.json`
- Create: `episodes/liangzhouci-15s/subtitles-liangzhouci-15s.json`
- Create: `scripts/build_liangzhouci_15s_final.sh`
- Create: `assets/subtitles/liangzhouci-15s/*.png`
- Create: `exports/liangzhouci-15s-subtitled-v01.mp4`
- Modify: `episodes/liangzhouci-15s/README.md`
- Modify: `assets/inventory.csv`

**Interfaces:**
- Consumes: 归档原片、四句MP3、实际有效语音边界、`scripts/render_story_subtitle_cards.swift`和本集时间目标。
- Produces: 可重跑的字幕时间轴、四张透明字幕卡、单一构建脚本、正式成片和资产登记。

- [ ] **Step 1: 根据实际音频写入时间轴**

`subtitle-plan.json` 必须使用以下字段：

```json
[
  {"id":"01-poem-line-one","kind":"poem","text":"黄河远上白云间","attribution":"唐·王之涣","start":0.25,"end":2.70},
  {"id":"02-poem-line-two","kind":"poem","text":"一片孤城万仞山","start":3.60,"end":6.00},
  {"id":"03-poem-line-three","kind":"poem","text":"羌笛何须怨杨柳","start":6.90,"end":9.60},
  {"id":"04-poem-line-four","kind":"poem","text":"春风不度玉门关","start":10.70,"end":14.40}
]
```

上述数字是设计目标，实施时使用实际语音有效时长替换`end`，并在相邻留白中微调`start`。必须保持第一句不晚于0.5秒开始、句间至少0.7秒、第四句在14.0—14.6秒结束。

- [ ] **Step 2: 写入字幕渲染输入和构建脚本**

`subtitles-liangzhouci-15s.json` 从`subtitle-plan.json`派生四条记录，不含标点；首条含`attribution: "唐·王之涣"`。`build_liangzhouci_15s_final.sh` 必须：

```text
验证原片、四句音频、时间轴和字幕渲染器均存在
渲染四张1080×1920透明PNG字幕卡
将原画面用Lanczos放大为1080×1920，不裁切
按每句start/end叠加对应字幕卡
根据实际语音边界裁切四句，只对必要句使用轻微atempo调整
人声区间将原声平滑压低到约0.562341，句间恢复原声
人声居中混合，最后使用限制器保护峰值
编码为H.264/AAC、24fps，以原片时长结束
```

- [ ] **Step 3: 运行门禁确认绿灯**

Run: `zsh tests/test_liangzhouci_15s_final.sh`

Expected: `PASS: Liangzhouci 15s recitation mix and burned subtitles are ready`

- [ ] **Step 4: 运行视觉和音频验收**

Run:

```bash
ffmpeg -hide_banner -loglevel error -y -i exports/liangzhouci-15s-subtitled-v01.mp4 -vf "fps=1,scale=360:-2,tile=5x3" -frames:v 1 /private/tmp/liangzhouci-subtitled-contact-sheet.jpg
ffmpeg -hide_banner -i exports/liangzhouci-15s-subtitled-v01.mp4 -af astats=metadata=1:reset=0 -f null - 2>&1
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,sample_rate,channels -of json exports/liangzhouci-15s-subtitled-v01.mp4
```

Expected: 四句字幕不遮挡栀夏面部、阿砚、黄河主河道和关城；人声清楚、原声仍可感知、没有削波；成片规格与全局约束一致。

- [ ] **Step 5: 更新单集状态和资产登记**

`episodes/liangzhouci-15s/README.md` 记录原片验收、四句实际有效朗诵区间、混音方式、成片路径与规格。`assets/inventory.csv` 新增原片、四句配音和正式成片记录，不记录本地密钥或下载目录。

- [ ] **Step 6: 运行完整复验并提交**

Run:

```bash
zsh tests/test_liangzhouci_15s_final.sh
zsh tests/test_subtitle_attribution.sh
git diff --check -- episodes/liangzhouci-15s scripts/build_liangzhouci_15s_final.sh tests/test_liangzhouci_15s_final.sh assets/inventory.csv
```

Expected: 两项测试全部PASS，`git diff --check`无输出。

```bash
git add episodes/liangzhouci-15s scripts/build_liangzhouci_15s_final.sh tests/test_liangzhouci_15s_final.sh assets/audio/liangzhouci-15s-paced-v01 assets/subtitles/liangzhouci-15s exports/liangzhouci-15s-subtitled-v01.mp4 assets/inventory.csv
git commit -m "制作：完成凉州词朗诵字幕成片"
```
