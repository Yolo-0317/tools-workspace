# 《霓裳飞天》朗诵字幕高清成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认保留的 15.069 秒《霓裳飞天》原片制作成栀夏四句诗朗诵、逐句竖排字幕、背景音乐全程不降音量的 1080×1920 发布成片。

**Architecture:** 将下载视频原样归档到单集目录，使用现有豆包 TTS 流水线按句生成栀夏固定音色。专用构建脚本完成画面保真放大、人声排布、原声直接混合、总线峰值保护和透明字幕卡叠加，分别输出无字幕朗诵试听版与正式字幕版；独立门禁检查文本、时间轴、无音乐闪避、媒体参数和产物完整性。

**Tech Stack:** JSON、Python TTS 流水线、Swift/AppKit 字幕卡渲染、FFmpeg、FFprobe、zsh、jq、Git。

## Global Constraints

- 源视频固定为 `/Users/huan.yu/Downloads/d2a00f67-6708-4440-b225-ccfc270a01c6.mp4`，496×864、24fps、15.069002 秒、H.264/AAC；原下载文件保持不变。
- 四句固定为“素手把芙蓉。”“虚步蹑太清。”“霓裳曳广带。”“飘拂升天行。”，使用栀夏固定音色 `ICL_uranus_zh_female_tianmeihuopo_tob`。
- 字幕时间窗固定为 `0.250—3.050`、`3.500—6.350`、`6.850—9.750`、`10.200—14.550` 秒。
- 背景音乐全程保持原始时间结构和相对音量；不使用 `sidechaincompress`，不在人声区间设置原声音量包络。
- 最终总线只做统一峰值限制；输出 H.264、1080×1920、24fps、AAC 192kbps、48kHz 双声道。
- 字幕位于左侧安全区，第一句题署为“唐·李白《古风·其十九》”。

---

## 文件结构

- `episodes/nichang-feitian-15s/assets/video/content-seedance-v01.mp4`：项目内原片副本。
- `episodes/nichang-feitian-15s/voice-lines.json`：四句配音清单。
- `episodes/nichang-feitian-15s/subtitle-plan.json`：四句字幕时间轴。
- `tests/test_nichang_feitian_15s_final.sh`：成片门禁。
- `scripts/build_nichang_feitian_15s_final.sh`：高清混音与字幕合成入口。
- `assets/audio/nichang-feitian-15s-paced-v01/`：四句 TTS。
- `assets/subtitles/nichang-feitian-15s/`：四张透明字幕卡。
- `exports/nichang-feitian-15s-voiced-v01.mp4`：无字幕朗诵试听版。
- `exports/nichang-feitian-15s-subtitled-v01.mp4`：正式字幕成片。

### Task 1: 固定输入、清单和失败门禁

**Files:**
- Create: `zhixia-feihualing/episodes/nichang-feitian-15s/assets/video/content-seedance-v01.mp4`
- Create: `zhixia-feihualing/episodes/nichang-feitian-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/nichang-feitian-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/tests/test_nichang_feitian_15s_final.sh`

**Interfaces:**
- Consumes: 已确认原片及设计规范中的诗句、时间窗和声音规则。
- Produces: TTS 清单、字幕清单、归档原片，以及在构建产物缺失时明确失败的门禁。

- [ ] **Step 1: 写入失败门禁**

门禁使用 `jq` 检查：

```zsh
jq -e '
  .episode == "nichang-feitian-15s" and
  .audio_slug == "nichang-feitian-15s-paced-v01" and
  [.lines[].role] == ["zhixia","zhixia","zhixia","zhixia"] and
  [.lines[].text] == ["素手把芙蓉。","虚步蹑太清。","霓裳曳广带。","飘拂升天行。"]
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == ["素手把芙蓉","虚步蹑太清","霓裳曳广带","飘拂升天行"] and
  .[0].start == 0.250 and .[0].end == 3.050 and
  .[1].start == 3.500 and .[1].end == 6.350 and
  .[2].start == 6.850 and .[2].end == 9.750 and
  .[3].start == 10.200 and .[3].end == 14.550 and
  .[0].attribution == "唐·李白《古风·其十九》"
' "$subtitle_plan" >/dev/null
```

门禁同时检查构建脚本不含 `sidechaincompress` 或原声区间音量表达式，并在构建后用 `ffprobe` 验证两个输出的分辨率、帧率、时长和音频参数。

- [ ] **Step 2: 运行测试并确认输入缺失导致失败**

Run: `zsh zhixia-feihualing/tests/test_nichang_feitian_15s_final.sh`

Expected: FAIL，报告缺少清单、构建脚本或正式产物。

- [ ] **Step 3: 创建配音与字幕 JSON**

`voice-lines.json` 使用 `format=one-poem-story`、`episode=nichang-feitian-15s`、`theme_slug=nichang-feitian-15s`、`audio_slug=nichang-feitian-15s-paced-v01`。四项 ID 为 `01-zhixia-line-one` 至 `04-zhixia-line-four`，`revision=1`；上下文逐句说明轻盈、清透、自然说诗、统一音色、不念作者篇名和不添加额外内容。

`subtitle-plan.json` 写入四个 `kind=poem` 项，正文去句号，使用 Global Constraints 中的四个时间窗，仅第一项包含题署。

- [ ] **Step 4: 归档原片并校验哈希**

```zsh
mkdir -p zhixia-feihualing/episodes/nichang-feitian-15s/assets/video
cp -p /Users/huan.yu/Downloads/d2a00f67-6708-4440-b225-ccfc270a01c6.mp4 zhixia-feihualing/episodes/nichang-feitian-15s/assets/video/content-seedance-v01.mp4
shasum -a 256 /Users/huan.yu/Downloads/d2a00f67-6708-4440-b225-ccfc270a01c6.mp4 zhixia-feihualing/episodes/nichang-feitian-15s/assets/video/content-seedance-v01.mp4
```

Expected: 两个 SHA-256 完全一致。

- [ ] **Step 5: 提交清单和门禁**

```zsh
git add zhixia-feihualing/episodes/nichang-feitian-15s/voice-lines.json zhixia-feihualing/episodes/nichang-feitian-15s/subtitle-plan.json zhixia-feihualing/tests/test_nichang_feitian_15s_final.sh
git commit -m "建立霓裳飞天朗诵字幕门禁"
```

### Task 2: 生成四句栀夏朗诵

**Files:**
- Create: `zhixia-feihualing/assets/audio/nichang-feitian-15s-paced-v01/01-zhixia-zhixia-line-one.mp3`
- Create: `zhixia-feihualing/assets/audio/nichang-feitian-15s-paced-v01/02-zhixia-zhixia-line-two.mp3`
- Create: `zhixia-feihualing/assets/audio/nichang-feitian-15s-paced-v01/03-zhixia-zhixia-line-three.mp3`
- Create: `zhixia-feihualing/assets/audio/nichang-feitian-15s-paced-v01/04-zhixia-zhixia-line-four.mp3`
- Create: `zhixia-feihualing/assets/audio/nichang-feitian-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 的配音清单与项目现有 TTS 凭证。
- Produces: 四个独立 MP3 和生成元数据。

- [ ] **Step 1: 预览调用计划**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode nichang-feitian-15s`

Expected: 显示待生成 4 句、栀夏 4 句、预计调用 4 次，预览不创建音频。

- [ ] **Step 2: 执行音频生成**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode nichang-feitian-15s --generate`

确认文本固定为 `GENERATE nichang-feitian-15s`。如凭证或网络不可用，报告实际阻塞，不创建占位音频。

- [ ] **Step 3: 校验四句音频**

逐个使用 `ffprobe` 检查可解码、采样率 24000、单声道、时长大于 1 秒；使用 `jq` 核对元数据中的文本、角色、音色和 revision。

### Task 3: 构建高清朗诵与字幕版

**Files:**
- Create: `zhixia-feihualing/scripts/build_nichang_feitian_15s_final.sh`
- Reuse: `zhixia-feihualing/scripts/render_story_subtitle_cards.swift`
- Create: `zhixia-feihualing/assets/subtitles/nichang-feitian-15s/*.png`
- Create: `zhixia-feihualing/exports/nichang-feitian-15s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/nichang-feitian-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: 归档原片、四句 MP3 和字幕计划。
- Produces: 固定高清画面与固定混音的试听版，以及复用相同音轨的字幕正式版。

- [ ] **Step 1: 创建专用构建脚本**

视频链固定为：

```text
scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,
crop=1080:1920:(iw-1080)/2:0,
hqdn3d=0.6:0.6:1.8:1.8,
unsharp=5:5:0.22:3:3:0,
fps=24,format=yuv420p
```

四句先按实际有效区间 `atrim`，以轻微 `atempo` 对齐四个目标窗口，再使用 `adelay=250|250`、`3500|3500`、`6850|6850`、`10200|10200` 定位。人声完成高通、轻度均衡、压缩与响度整理。原声只做 48kHz 双声道规范化，最终使用：

```text
[bed][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,
alimiter=limit=0.870964:attack=5:release=80:level=false[aout]
```

字幕卡按四个窗口各使用 0.120 秒淡入淡出；正式版直接复制试听版音轨。

- [ ] **Step 2: 运行构建与门禁**

Run: `zsh zhixia-feihualing/tests/test_nichang_feitian_15s_final.sh`

Expected: 生成四张字幕卡、两个 MP4，输出 `PASS: Nichang Feitian four-line recitation HD finals are ready`。

- [ ] **Step 3: 验证背景音乐保持原音量**

检查构建脚本没有侧链和区间音量表达式；试听四个人声区间和句间空白，确认鼓点与环境声连续、没有抽吸。统一总线限制器只处理叠加峰值。

- [ ] **Step 4: 提交构建入口**

```zsh
git add zhixia-feihualing/scripts/build_nichang_feitian_15s_final.sh zhixia-feihualing/tests/test_nichang_feitian_15s_final.sh
git commit -m "制作霓裳飞天朗诵字幕高清成片"
```

### Task 4: 视觉听觉验收与登记

**Files:**
- Modify: `zhixia-feihualing/episodes/nichang-feitian-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3 的试听版、正式版、字幕卡和媒体探测数据。
- Produces: 验收记录、最终路径和资产登记。

- [ ] **Step 1: 抽帧检查字幕与画质**

在 0.5、2.8、4.0、6.2、7.2、9.6、10.8、14.2 秒抽帧。字幕应位于左侧安全区，避开面部、核心舞姿、飘带主线、前景莲花和原片标识；画面保持自然比例。

- [ ] **Step 2: 完整试听**

检查四句读音、音色、句尾、留白和音量一致性；确认第四句在 14.550 秒前收住，原背景音乐全程连续。

- [ ] **Step 3: 更新 README 与资产清单**

README 记录原片保留、诗句、时间窗、不降低背景音乐、试听版和正式版路径。`assets/inventory.csv` 只追加本集必要资产，并保持九列与唯一 `asset_id`；不记录凭证或下载目录路径。

- [ ] **Step 4: 最终验证并提交登记**

```zsh
zsh zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh
zsh zhixia-feihualing/tests/test_nichang_feitian_15s_final.sh
git diff --check
awk -F, 'NF != 9 {print NR ":" NF; bad=1} END {exit bad}' zhixia-feihualing/assets/inventory.csv
```

Expected: 两个测试 PASS，格式检查无输出，资产清单每行九列。

```zsh
git add zhixia-feihualing/episodes/nichang-feitian-15s/README.md zhixia-feihualing/assets/inventory.csv
git commit -m "登记霓裳飞天朗诵字幕成片"
```
