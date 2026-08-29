# 《鼓催柘枝》四句诗朗诵高清成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户提供的 15.069 秒《鼓催柘枝》原片制作成栀夏四句诗朗诵、逐句竖排字幕、保真高清画质的 1080×1920 可发布成片。

**Architecture:** 原下载视频以内容不变的副本进入单集资产目录；四句栀夏 TTS 由现有配音流水线分段生成。一个专用构建脚本负责保真放大、轻度降噪锐化、四段人声排布、原声动态压低和字幕卡叠加，并分别输出无字幕试听版与最终字幕版；Shell 验证脚本检查文案、时间轴、媒体规格、文件完整性和原片保护。

**Tech Stack:** Python 配音清单与豆包 TTS 流水线、Swift/AppKit 字幕卡渲染器、FFmpeg/ffprobe、zsh、jq、CSV。

## Global Constraints

- 原片 `/Users/huan.yu/Downloads/c6f92f0a-4f89-4f8a-97ff-8a86820f8548.mp4` 不覆盖、不改速、不补帧、不重绘人物。
- 全片只使用栀夏固定音色朗诵白居易《柘枝妓》前四句，无阿砚对白、无额外旁白或吟唱。
- 四句在 0.250—14.300 秒范围内依次覆盖全片，句间保留约 0.5—0.7 秒呼吸。
- 字幕逐句竖排出现，第一句题署为“唐·白居易《柘枝妓》”，不得遮挡人物、主飘带或右下角 AI 标识。
- 画面输出 1080×1920、24fps、时长约 15.069 秒；保持原比例后轻裁左右边缘，不直接拉伸。
- 保留原声；人声期间原声平滑压低约 5 dB，最终综合目标约 −16 LUFS、真峰值不高于 −1.5 dBTP。
- 输出 H.264 高质量视频、48kHz 双声道 AAC 192kbps，并写入快速起播标记。
- 不提交 `.env`、API Key、请求密钥或其他凭证；保留工作区全部无关改动。

---

### Task 1: 建立单集输入、配音清单与失败测试

**Files:**
- Create: `zhixia-feihualing/episodes/gucuizhezhi-15s/assets/video/content-seedance-v01.mp4`
- Create: `zhixia-feihualing/episodes/gucuizhezhi-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/gucuizhezhi-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/tests/test_gucuizhezhi_15s_final.sh`

**Interfaces:**
- Consumes: 用户提供的 496×864、24fps、15.069 秒原片和 `config/voices.json` 中栀夏固定音色。
- Produces: 四句 `zhixia` 配音清单、四条字幕时间窗，以及后续构建必须满足的可执行验收测试。

- [x] **Step 1: 写入四句配音清单**

创建 `voice-lines.json`，固定 `episode=gucuizhezhi-15s`、`audio_slug=gucuizhezhi-15s-paced-v01`，四行文本依次为“平铺一合锦筵开。”“连击三声画鼓催。”“红蜡烛移桃叶起。”“紫罗衫动柘枝来。”。四行 `role` 均为 `zhixia`，每行提供具体的自然朗诵语境，禁止播音腔、吟唱与额外补话。

- [x] **Step 2: 写入字幕时间窗**

创建 `subtitle-plan.json`：四条 `kind=poem` 项的时间窗依次为 `0.250—3.050`、`3.650—6.450`、`7.050—9.950`、`10.600—14.300`；只在第一条写入 `attribution: 唐·白居易《柘枝妓》`，字幕正文去掉标点。

- [x] **Step 3: 写失败测试**

测试必须先检查清单四句、角色、题署、严格递增时间窗和末句结束时间，再要求以下尚不存在的文件：

```zsh
build_script="$project_dir/scripts/build_gucuizhezhi_15s_final.sh"
source_video="$project_dir/episodes/gucuizhezhi-15s/assets/video/content-seedance-v01.mp4"
voiced="$project_dir/exports/gucuizhezhi-15s-voiced-v01.mp4"
final="$project_dir/exports/gucuizhezhi-15s-subtitled-v01.mp4"
[[ -x "$build_script" ]]
[[ -s "$source_video" ]]
[[ -s "$voiced" ]]
[[ -s "$final" ]]
```

- [x] **Step 4: 运行测试确认失败**

Run: `zsh tests/test_gucuizhezhi_15s_final.sh`

Expected: FAIL，首先报告缺少专用构建脚本或输出成片。

- [x] **Step 5: 归档原片副本**

创建单集视频目录，把下载原片复制为 `content-seedance-v01.mp4`；用 SHA-256 确认项目副本与下载原片内容一致。

### Task 2: 生成并核对四句栀夏朗诵

**Files:**
- Create: `zhixia-feihualing/assets/audio/gucuizhezhi-15s-paced-v01/01-zhixia-zhixia-line-one.mp3`
- Create: `zhixia-feihualing/assets/audio/gucuizhezhi-15s-paced-v01/02-zhixia-zhixia-line-two.mp3`
- Create: `zhixia-feihualing/assets/audio/gucuizhezhi-15s-paced-v01/03-zhixia-zhixia-line-three.mp3`
- Create: `zhixia-feihualing/assets/audio/gucuizhezhi-15s-paced-v01/04-zhixia-zhixia-line-four.mp3`
- Create: `zhixia-feihualing/assets/audio/gucuizhezhi-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 的 `voice-lines.json` 和项目本地 `.env` 中的豆包语音凭证。
- Produces: 四个可独立解码的 24kHz 单声道 MP3，以及包含真实时长、台词、音色和版本的元数据。

- [x] **Step 1: 预览付费调用计划**

Run: `python3 scripts/generate_episode_audio.py --episode gucuizhezhi-15s`

Expected: `待生成：4 句`、`栀夏：4 句`、`预计产生豆包 TTS 调用：4 次`，且预览模式不访问网络、不创建音频。

- [x] **Step 2: 执行用户已授权的四句生成**

Run: `python3 scripts/generate_episode_audio.py --episode gucuizhezhi-15s --generate`

在程序确认提示中精确输入 `GENERATE gucuizhezhi-15s`。若凭证或网络不可用，停止在已完成的本地计划与清单，不伪造音频。

- [x] **Step 3: 校验音频与元数据**

逐个用 `ffprobe` 验证 MP3 可解码、采样率 24000、单声道且时长大于 1 秒；用 `jq` 验证元数据中的文本、角色、固定音色和 revision 与清单一致。

- [x] **Step 4: 试听四句连续性**

临时按清单顺序拼接四句并播放或生成波形抽查，确认是同一位栀夏、无读错、吞字、额外补话、明显赶字、戏曲腔或音量突变。若仅一行不合格，提高该行 revision 并只重新生成该行，保留旧版本。

### Task 3: 实现高清配音版与字幕成片构建

**Files:**
- Create: `zhixia-feihualing/scripts/build_gucuizhezhi_15s_final.sh`
- Reuse: `zhixia-feihualing/scripts/render_story_subtitle_cards.swift`
- Create: `zhixia-feihualing/assets/subtitles/gucuizhezhi-15s/01-poem-line-one.png`
- Create: `zhixia-feihualing/assets/subtitles/gucuizhezhi-15s/02-poem-line-two.png`
- Create: `zhixia-feihualing/assets/subtitles/gucuizhezhi-15s/03-poem-line-three.png`
- Create: `zhixia-feihualing/assets/subtitles/gucuizhezhi-15s/04-poem-line-four.png`
- Create: `zhixia-feihualing/exports/gucuizhezhi-15s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/gucuizhezhi-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: Task 1 的原片与字幕计划、Task 2 的四条 MP3。
- Produces: 同一高清画面与完成混音的无字幕试听版，以及在其基础上逐句叠加竖排字幕的最终成片。

- [x] **Step 1: 写最小构建脚本**

脚本先校验所有输入并渲染四张透明字幕卡。视频滤镜固定使用：

```text
scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,
crop=1080:1920:(iw-1080)/2:0,
hqdn3d=0.6:0.6:1.8:1.8,
unsharp=5:5:0.22:3:3:0,
eq=contrast=1.02:saturation=1.02,
fps=24,format=yuv420p
```

不得使用补帧或生成式超分辨率。

- [x] **Step 2: 按真实音频时长布置人声**

从每个 MP3 去掉大部分头尾静音，以 `atempo` 调整为舒展但不失真的诗歌语速，单段限制在 `0.65—1.05`；分别延迟至 250、3650、7050、10600 毫秒，末句允许在该时间窗内后移不超过 0.250 秒。四段合并后将人声规范到约 −18 LUFS，再与原声混合。

- [x] **Step 3: 实现原声压低和最终限幅**

在人声窗口内将原声降至约 `0.562341`，窗外保持 1.0，并用短淡入淡出避免音量台阶；混合后用限制器控制真峰值不高于 −1.5 dBTP。输出音频固定为 48kHz 双声道 AAC 192kbps。

- [x] **Step 4: 输出无字幕试听版**

从增强后的基础画面与完成混音输出 `gucuizhezhi-15s-voiced-v01.mp4`，使用 `libx264 -preset slow -crf 17 -pix_fmt yuv420p -movflags +faststart`。

- [x] **Step 5: 叠加逐句竖排字幕并输出最终版**

把四张字幕卡按 `subtitle-plan.json` 时间窗叠加到同一增强画面，使用约 0.12 秒淡入淡出，输出 `gucuizhezhi-15s-subtitled-v01.mp4`。第一句带题署，其余三句无题署。

- [x] **Step 6: 运行构建测试确认通过**

Run: `zsh tests/test_gucuizhezhi_15s_final.sh`

Expected: PASS，两个成片均为 1080×1920、24fps、H.264、48kHz 双声道 AAC，时长 15.0—15.2 秒，字幕卡恰好四张。

### Task 4: 视觉、音频和归档验收

**Files:**
- Modify: `zhixia-feihualing/episodes/gucuizhezhi-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3 的两个成片及所有源资产。
- Produces: 可追溯的最终状态、资产记录和验证证据。

- [x] **Step 1: 抽帧检查字幕避让和画质**

在 0.5、2.8、4.0、6.2、7.5、9.7、11.0、14.0 秒抽帧，检查竖排字幕没有遮挡脸、主要手势、蓝橙飘带或右下角 AI 标识；对比原片确认人物比例未拉伸、脸部未重绘、锐化无白边。

- [x] **Step 2: 检查混音指标**

用 `loudnorm=print_format=summary` 和 `astats` 检查综合响度与真峰值；人工试听四句是否完整、句间有呼吸、原声鼓点仍可辨且无爆音、突降或尾句截断。

- [x] **Step 3: 更新本集状态和资产清单**

README 记录源片已归档、四句栀夏朗诵、字幕方案、高清处理和最终文件路径。资产清单新增源片、四条语音、无字幕试听版和最终字幕成片；每行保持九列并使用唯一 asset ID。

- [x] **Step 4: 运行最终验证**

运行专用测试、`ffmpeg -v error -i <file> -f null -`、CSV 九列与 ID 唯一检查、`git diff --check`。所有验证必须使用最终文件重新执行。

- [x] **Step 5: 提交本次成片资产**

只暂存《鼓催柘枝》本次清单、脚本、测试、文档和正式资产，保留其他工作区改动。使用中文提交：

```bash
git commit -m '制作鼓催柘枝四句诗朗诵高清成片'
```
