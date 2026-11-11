# 《回雪胡旋》四句诗朗诵高清成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认可用的 15.069 秒《回雪胡旋》原片制作成栀夏四句诗朗诵、逐句竖排字幕、背景音乐全程不降音量的 1080×1920 发布成片。

**Architecture:** 原下载视频以内容不变的副本归档到单集目录，四句栀夏 TTS 由现有配音流水线分段生成。专用构建脚本负责保真放大、四段人声排布、原声与人声直接混合、总线峰值保护和字幕卡叠加，分别输出无字幕试听版与正式字幕版；独立门禁检查文案、时间轴、无背景音乐闪避、媒体规格和原片保护。

**Tech Stack:** JSON、Python 豆包 TTS 流水线、Swift/AppKit 字幕卡渲染器、FFmpeg、FFprobe、zsh、jq、CSV

## Global Constraints

- 源视频固定为 `/Users/huan.yu/Downloads/8fe8408d-b1ae-4c9e-a537-7a58ddb5cff1.mp4`，496×864、24fps、15.069002 秒、H.264/AAC；不得覆盖或修改。
- 四句固定为“弦鼓一声双袖举。”“回雪飘飖转蓬舞。”“左旋右转不知疲。”“千匝万周无已时。”，只使用栀夏固定音色 `ICL_uranus_zh_female_tianmeihuopo_tob`。
- 背景音乐全程保持原始时间结构和相对音量；禁止 `sidechaincompress`，禁止在人声区间设置原声音量包络或分段降低。
- 只允许对人声做轻度处理，并对最终总线统一限制峰值；不得产生明显抽吸。
- 字幕逐句竖排出现，第一句题署为“唐·白居易《胡旋女》”，不得遮挡脸部、核心舞姿、蓝橙飘带或 AI 标识。
- 画面保真升级到 1080×1920、24fps；不重绘面部、不补帧、不改变动作、运镜或时长。
- 输出音频固定为 48kHz 双声道 AAC 192kbps，最终真峰值不高于 −1.0 dBTP。

---

## 文件结构

- `episodes/huxuan-15s/assets/video/content-seedance-v01.mp4`：源片项目内只读归档副本。
- `episodes/huxuan-15s/voice-lines.json`：四句栀夏配音生成清单。
- `episodes/huxuan-15s/subtitle-plan.json`：四句正式字幕及目标显示窗口。
- `tests/test_huxuan_15s_final.sh`：文本、时间轴、无闪避混音、媒体规格和产物门禁。
- `scripts/build_huxuan_15s_final.sh`：唯一高清混音与字幕合成入口。
- `assets/audio/huxuan-15s-paced-v01/`：四句 TTS 与生成元数据。
- `assets/subtitles/huxuan-15s/`：四张透明字幕卡。
- `exports/huxuan-15s-voiced-v01.mp4`：无字幕朗诵试听版。
- `exports/huxuan-15s-subtitled-v01.mp4`：正式字幕成片。

### Task 1: 固定输入、配音清单与失败门禁

**Files:**
- Create: `zhixia-feihualing/episodes/huxuan-15s/assets/video/content-seedance-v01.mp4`
- Create: `zhixia-feihualing/episodes/huxuan-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/huxuan-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/tests/test_huxuan_15s_final.sh`

**Interfaces:**
- Consumes: 下载目录中的已确认原片和设计文档中的四句诗、音色、时间窗。
- Produces: 固定源片、可供 `generate_episode_audio.py` 读取的配音清单、可供字幕渲染器读取的四项 JSON 数组，以及在构建脚本和产物缺失时明确失败的门禁。

- [ ] **Step 1: 写入失败门禁**

创建可执行 `tests/test_huxuan_15s_final.sh`，固定检查：

```zsh
jq -e '
  .episode == "huxuan-15s" and
  .audio_slug == "huxuan-15s-paced-v01" and
  [.lines[].role] == ["zhixia", "zhixia", "zhixia", "zhixia"] and
  [.lines[].text] == [
    "弦鼓一声双袖举。",
    "回雪飘飖转蓬舞。",
    "左旋右转不知疲。",
    "千匝万周无已时。"
  ]
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == [
    "弦鼓一声双袖举",
    "回雪飘飖转蓬舞",
    "左旋右转不知疲",
    "千匝万周无已时"
  ] and
  .[0].start == 0.250 and .[0].end == 3.100 and
  .[1].start == 3.650 and .[1].end == 6.650 and
  .[2].start == 7.150 and .[2].end == 10.100 and
  .[3].start == 10.650 and .[3].end == 14.450 and
  .[0].attribution == "唐·白居易《胡旋女》"
' "$subtitle_plan" >/dev/null

! rg -q 'sidechaincompress|volume=.*enable|volume=.*between' "$build_script"
rg -q 'amix=inputs=2.*normalize=0' "$build_script"
```

源片门禁同时以 SHA-256 对比下载文件和项目副本；构建后用 `ffprobe` 检查两个输出均为 H.264、1080×1920、24fps、15.0—15.2 秒、AAC、48kHz、双声道，且恰好生成四张字幕卡。

- [ ] **Step 2: 运行门禁并确认因输入文件缺失而失败**

Run: `zsh tests/test_huxuan_15s_final.sh`

Expected: FAIL，首先报告缺少 `voice-lines.json`、`subtitle-plan.json` 或构建脚本；失败原因必须是本功能尚未实现，而不是 shell 语法错误。

- [ ] **Step 3: 写入四句清单与字幕计划**

`voice-lines.json` 固定使用 `format=one-poem-story`、`episode=huxuan-15s`、`theme_slug=huxuan-15s`、`audio_slug=huxuan-15s-paced-v01`。四行 ID 依次为 `01-zhixia-line-one` 至 `04-zhixia-line-four`，`revision=1`；上下文明确同一位 18 岁栀夏、清透明亮、随胡旋节奏自然推进、不喊、不吟唱、不念作者篇名、不额外补话。

`subtitle-plan.json` 写入四个 `kind=poem` 项，正文去标点，时间窗依次为 `0.250—3.100`、`3.650—6.650`、`7.150—10.100`、`10.650—14.450`，仅第一项包含 `attribution=唐·白居易《胡旋女》`。

- [ ] **Step 4: 归档源片并校验内容不变**

Run:

```zsh
mkdir -p episodes/huxuan-15s/assets/video
cp -p /Users/huan.yu/Downloads/8fe8408d-b1ae-4c9e-a537-7a58ddb5cff1.mp4 episodes/huxuan-15s/assets/video/content-seedance-v01.mp4
shasum -a 256 /Users/huan.yu/Downloads/8fe8408d-b1ae-4c9e-a537-7a58ddb5cff1.mp4 episodes/huxuan-15s/assets/video/content-seedance-v01.mp4
```

Expected: 两个 SHA-256 完全相同。

- [ ] **Step 5: 再次运行门禁并确认只因音频或构建脚本缺失而失败**

Run: `zsh tests/test_huxuan_15s_final.sh`

Expected: FAIL，清单、字幕与源片检查已通过，失败点前移至缺少 TTS 或 `build_huxuan_15s_final.sh`。

- [ ] **Step 6: 提交本阶段**

```zsh
git add episodes/huxuan-15s/voice-lines.json episodes/huxuan-15s/subtitle-plan.json tests/test_huxuan_15s_final.sh
git commit -m "建立回雪胡旋朗诵字幕门禁"
```

视频副本受仓库忽略规则管理，仅在本地资产目录保留，不强制纳入 Git。

### Task 2: 生成并验收四句栀夏朗诵

**Files:**
- Create: `zhixia-feihualing/assets/audio/huxuan-15s-paced-v01/01-zhixia-zhixia-line-one.mp3`
- Create: `zhixia-feihualing/assets/audio/huxuan-15s-paced-v01/02-zhixia-zhixia-line-two.mp3`
- Create: `zhixia-feihualing/assets/audio/huxuan-15s-paced-v01/03-zhixia-zhixia-line-three.mp3`
- Create: `zhixia-feihualing/assets/audio/huxuan-15s-paced-v01/04-zhixia-zhixia-line-four.mp3`
- Create: `zhixia-feihualing/assets/audio/huxuan-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 的 `voice-lines.json` 与项目本地豆包 TTS 凭证。
- Produces: 四个可独立解码的 24kHz 单声道 MP3 和记录真实时长、文本、音色、revision 的元数据。

- [ ] **Step 1: 预览调用计划**

Run: `python3 scripts/generate_episode_audio.py --episode huxuan-15s`

Expected: 显示待生成 4 句、栀夏 4 句、预计 TTS 调用 4 次；预览模式不创建 MP3。

- [ ] **Step 2: 执行四句生成**

Run: `python3 scripts/generate_episode_audio.py --episode huxuan-15s --generate`

在确认提示中输入 `GENERATE huxuan-15s`。若凭证或网络不可用，保留已完成清单并报告真实阻塞，不伪造音频。

- [ ] **Step 3: 校验音频文件与元数据**

逐个用 `ffprobe` 检查 MP3 可解码、采样率为 24000、单声道、时长大于 1 秒；用 `jq` 核对元数据文本、角色、音色和 revision 与清单一致。

- [ ] **Step 4: 试听连续性**

按诗句顺序拼接临时试听，确认四句来自同一位栀夏，无读错、吞字、额外补话、明显赶字、戏曲腔或音量突变。若单句不合格，只提高该句 revision 并重新生成该句。

### Task 3: 实现不压低背景音乐的高清合成

**Files:**
- Create: `zhixia-feihualing/scripts/build_huxuan_15s_final.sh`
- Reuse: `zhixia-feihualing/scripts/render_story_subtitle_cards.swift`
- Create: `zhixia-feihualing/assets/subtitles/huxuan-15s/01-poem-line-one.png`
- Create: `zhixia-feihualing/assets/subtitles/huxuan-15s/02-poem-line-two.png`
- Create: `zhixia-feihualing/assets/subtitles/huxuan-15s/03-poem-line-three.png`
- Create: `zhixia-feihualing/assets/subtitles/huxuan-15s/04-poem-line-four.png`
- Create: `zhixia-feihualing/exports/huxuan-15s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/huxuan-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: Task 1 的源片和字幕计划、Task 2 的四条 MP3。
- Produces: 同一高清画面与固定混音的试听版，以及复制该音轨并叠加四张字幕卡的正式成片。

- [ ] **Step 1: 写入最小构建脚本**

脚本使用 `set -euo pipefail`，逐个校验输入存在，清空并重建本集字幕卡目录。视频链固定为：

```text
scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,
crop=1080:1920:(iw-1080)/2:0,
hqdn3d=0.6:0.6:1.8:1.8,
unsharp=5:5:0.22:3:3:0,
fps=24,format=yuv420p
```

四句音频根据真实首尾静音用 `atrim` 去除空白，以 `atempo` 轻微调整到对应字幕窗口并用 `adelay=250|250`、`3650|3650`、`7150|7150`、`10650|10650` 放置。四句先混为单一人声轨并做轻度响度统一；原声只执行 `aresample=48000,aformat=channel_layouts=stereo`，随后使用：

```text
[bed][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,
alimiter=limit=0.891251:attack=5:release=80[aout]
```

禁止 `sidechaincompress`、人声区间 `volume` 表达式和原声分段。试听版编码为 H.264 CRF 17、AAC 192kbps、48kHz 双声道，并加 `+faststart`。

- [ ] **Step 2: 运行门禁确认脚本结构通过并完成构建**

Run: `zsh tests/test_huxuan_15s_final.sh`

Expected: 构建生成四张字幕卡、试听版和正式字幕版；自动检查全部通过并输出 `PASS: Huxuan four-line recitation HD finals are ready`。

- [ ] **Step 3: 验证背景音乐没有动态压低**

从源片与试听版分别提取 0.0—15.0 秒音频，测量四个句间空白和四个人声区间的原声参考频段能量；结合脚本静态门禁确认没有侧链和区间音量表达式。允许最终总线限制器统一抑制叠加峰值，不允许人声区间出现周期性 3dB 以上原声下降。

- [ ] **Step 4: 提交构建脚本与门禁**

```zsh
git add scripts/build_huxuan_15s_final.sh tests/test_huxuan_15s_final.sh
git commit -m "制作回雪胡旋朗诵字幕高清成片"
```

### Task 4: 视觉听觉验收与项目登记

**Files:**
- Modify: `zhixia-feihualing/episodes/huxuan-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3 的试听版、正式字幕版、四张字幕卡和媒体探测数据。
- Produces: 视觉听觉验收记录、最终路径与可追溯资产登记。

- [ ] **Step 1: 抽帧检查字幕避让和画质**

分别在 0.5、2.8、4.0、6.3、7.5、9.8、11.0、14.2 秒抽帧并生成联系表。检查字幕不遮挡栀夏面部、核心手势、身体剪影、蓝橙飘带和 AI 标识；对比原片确认人物未拉伸、脸部未重绘、锐化无白边。

- [ ] **Step 2: 完整试听两个输出**

检查四句无读错、吞字、额外补话、明显赶字或音量突变；确认背景音乐在人声出现时没有明显压低或抽吸，鼓点与动作声持续可辨，正式版音轨与试听版一致。

- [ ] **Step 3: 更新 README 与资产清单**

README 将状态改为“朗诵字幕高清成片已完成”，记录源片、四句诗、时间窗、背景音乐不降音量、试听版和正式版路径。`assets/inventory.csv` 新增源片、四条语音、试听版与正式版记录，保持九列、唯一 `asset_id`，不记录密钥或下载目录路径。

- [ ] **Step 4: 运行最终验证**

Run:

```zsh
zsh tests/test_huxuan_15s_prompt.sh
zsh tests/test_huxuan_15s_final.sh
git diff --check
awk -F, 'NF != 9 {print NR ":" NF; bad=1} END {exit bad}' assets/inventory.csv
```

Expected: 两个测试均 PASS，`git diff --check` 无输出，资产清单每行均为九列。

- [ ] **Step 5: 提交登记**

```zsh
git add episodes/huxuan-15s/README.md assets/inventory.csv docs/superpowers/plans/2026-08-30-huxuan-poem-voiceover-final.md
git commit -m "登记回雪胡旋朗诵字幕成片"
```
