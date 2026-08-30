# 《月照反弹琵琶》朗诵字幕成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认的 15.104 秒无道具舞蹈原片制作成栀夏四句诗朗诵、逐句竖排字幕、原声全程 0 dB 的 1080×1920 可发布成片。

**Architecture:** 下载原片先以内容不变的副本归档到单集目录；四句栀夏 TTS 通过现有配音流水线分段生成。专用构建脚本负责保真放大、四段人声排布、原声 0 dB 叠加、透明峰值保护和逐句字幕卡合成，并分别输出无字幕试听版与最终字幕版；专用测试脚本验证文本、时间轴、无闪避混音实现、媒体规格和源文件保护。

**Tech Stack:** Python 配音清单与豆包 TTS 流水线、Swift/AppKit 字幕卡渲染器、FFmpeg/ffprobe、zsh、jq、CSV、Git。

## Global Constraints

- 设计真源：`docs/superpowers/specs/2026-08-30-fantan-pipa-recitation-subtitles-design.md`。
- 原片 `/Users/huan.yu/Downloads/45b803cd-530c-4ae0-850c-ce84cf069d4d.mp4` 不覆盖、不改速、不补帧、不重绘人物。
- 原片规格为 496×864、24fps、15.104 秒，H.264 视频与 32kHz 双声道 AAC 原声。
- 全片只使用栀夏固定音色 `ICL_uranus_zh_female_tianmeihuopo_tob` 朗诵王昌龄《从军行七首·其二》四句，无阿砚对白、额外旁白或吟唱。
- 四句时间窗固定为 `0.250—3.100`、`3.550—6.400`、`6.900—9.800`、`10.350—14.400` 秒，单句只允许在各自时间窗内微调不超过 0.200 秒。
- 字幕逐句竖排出现，第一句题署为“唐·王昌龄《从军行七首·其二》”，不得遮挡人物、主要手势、蓝橙飘带或右下角 AI 标识。
- 原片背景音乐和动作声全程保持 `volume=1.0`，不使用 sidechain compression、ducking、动态音量包络、频段削减或单独响度归一化。
- 混合使用 `amix normalize=0`，只允许在最终总线使用透明峰值限制器；最终真峰值不高于 −1.0 dBTP。
- 输出 1080×1920、24fps、约 15.104 秒、H.264 高质量视频与 48kHz 双声道 AAC 192kbps，并写入快速起播标记。
- 不提交 `.env`、API Key、请求密钥或其他凭证；保留工作区全部无关改动。

---

### Task 1: 建立源片、清单与失败测试

**Files:**
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/assets/video/content-seedance-no-prop-v02.mp4`
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/tests/test_fantan_pipa_15s_final.sh`

**Interfaces:**
- Consumes: 用户提供的无道具原片、项目固定声音配置和已确认的四句时间窗。
- Produces: 内容一致的项目原片副本、四句配音清单、四条字幕时间窗，以及后续构建必须满足的可执行验收测试。

- [ ] **Step 1: 写入四句配音清单**

创建 `voice-lines.json`，固定：

```json
{
  "episode": "fantan-pipa-15s",
  "format": "one-poem-story",
  "theme": "月照反弹琵琶十五秒四句全诗朗诵",
  "theme_slug": "fantan-pipa-15s",
  "audio_slug": "fantan-pipa-15s-paced-v01",
  "lines": [
    {
      "id": "01-zhixia-line-one",
      "role": "zhixia",
      "text": "琵琶起舞换新声。",
      "revision": 1,
      "gap_before_ms": 0,
      "context_texts": ["这是十五秒《月照反弹琵琶》舞蹈的第一句画外朗诵。保持栀夏十八岁东方少女清透、轻盈、明亮而不甜腻的固定声线，带自然书卷气；开篇随月下舞姿展开，‘琵琶起舞’清楚流动，‘换新声’轻轻提起并完整落下。不要播音腔、朗诵比赛腔、戏曲腔、吟唱、逐字等长或额外补话，不念标题和作者。"]
    },
    {
      "id": "02-zhixia-line-two",
      "role": "zhixia",
      "text": "总是关山旧别情。",
      "revision": 1,
      "gap_before_ms": 450,
      "context_texts": ["紧接上一句，画面进入月下长城的宽弓舞句。保持与上一句完全相同的栀夏固定声线，清冷而含蓄；‘总是关山’舒展开阔，‘旧别情’略有离情但不哭腔、不拖尾。不要喊诗、播音腔、戏曲腔、夸张重音、吟唱或额外补话。"]
    },
    {
      "id": "03-zhixia-line-three",
      "role": "zhixia",
      "text": "撩乱边愁听不尽。",
      "revision": 1,
      "gap_before_ms": 500,
      "context_texts": ["这是第三句，舞者在秋夜长风中完成横向舞句并为纵深高潮蓄势。保持同一位十八岁栀夏清透、轻盈、明亮的固定声线，语气比前句稍紧但不赶字；‘撩乱边愁’有内在波动，‘听不尽’清楚收住。不要主持腔、古装表演腔、戏曲腔、吟唱或额外停顿。"]
    },
    {
      "id": "04-zhixia-line-four",
      "role": "zhixia",
      "text": "高高秋月照长城。",
      "revision": 1,
      "gap_before_ms": 550,
      "context_texts": ["这是最后一句，画面中的舞者完成纵深沉提，秋月与长城共同收束全片。保持前文同一位栀夏的清透固定声线，增加辽阔、坚定与余韵但不喊；‘高高秋月’向上舒展，‘照长城’清楚完整地收住全诗，尾音自然结束在画面结束前。不要播音腔、朗诵比赛腔、戏曲腔、吟唱、夸张颤音或额外补话。"]
    }
  ]
}
```

- [ ] **Step 2: 写入字幕时间窗**

创建 `subtitle-plan.json`：

```json
[
  {
    "id": "01-poem-line-one",
    "kind": "poem",
    "text": "琵琶起舞换新声",
    "attribution": "唐·王昌龄《从军行七首·其二》",
    "start": 0.250,
    "end": 3.100
  },
  {
    "id": "02-poem-line-two",
    "kind": "poem",
    "text": "总是关山旧别情",
    "start": 3.550,
    "end": 6.400
  },
  {
    "id": "03-poem-line-three",
    "kind": "poem",
    "text": "撩乱边愁听不尽",
    "start": 6.900,
    "end": 9.800
  },
  {
    "id": "04-poem-line-four",
    "kind": "poem",
    "text": "高高秋月照长城",
    "start": 10.350,
    "end": 14.400
  }
]
```

- [ ] **Step 3: 写失败测试**

`tests/test_fantan_pipa_15s_final.sh` 必须检查：

- `voice-lines.json` 的四句文本、四个 `zhixia` 角色和 `fantan-pipa-15s-paced-v01` 音频版本。
- `subtitle-plan.json` 的四句无标点正文、唯一题署、严格递增时间窗和末句 14.400 秒结束。
- 构建脚本存在且可执行，包含 `volume=1.0` 与 `amix=inputs=2:duration=first:dropout_transition=0:normalize=0`。
- 构建脚本不得出现 `sidechaincompress`、`sidechaingate`、人声窗口 `volume` 表达式或对原声应用 `loudnorm`。
- 源片、四条 MP3、四张字幕卡、试听版和最终版存在且非空。
- 两个输出均为 1080×1920、24fps、H.264、48kHz 双声道 AAC，时长处于 15.0—15.2 秒。

- [ ] **Step 4: 运行测试确认失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_fantan_pipa_15s_final.sh
```

Expected: FAIL，首先报告缺少专用构建脚本或正式输出。

- [ ] **Step 5: 归档原片副本并校验哈希**

创建单集视频目录，把下载原片复制为 `content-seedance-no-prop-v02.mp4`。分别运行：

```bash
shasum -a 256 /Users/huan.yu/Downloads/45b803cd-530c-4ae0-850c-ce84cf069d4d.mp4
shasum -a 256 zhixia-feihualing/episodes/fantan-pipa-15s/assets/video/content-seedance-no-prop-v02.mp4
```

Expected: 两个 SHA-256 完全一致。

- [ ] **Step 6: 提交输入、清单与失败测试**

```bash
git add -- zhixia-feihualing/episodes/fantan-pipa-15s/assets/video/content-seedance-no-prop-v02.mp4 zhixia-feihualing/episodes/fantan-pipa-15s/voice-lines.json zhixia-feihualing/episodes/fantan-pipa-15s/subtitle-plan.json zhixia-feihualing/tests/test_fantan_pipa_15s_final.sh
git commit -m "建立反弹琵琶朗诵字幕输入"
```

---

### Task 2: 生成并核对四句栀夏朗诵

**Files:**
- Create: `zhixia-feihualing/assets/audio/fantan-pipa-15s-paced-v01/01-zhixia-zhixia-line-one.mp3`
- Create: `zhixia-feihualing/assets/audio/fantan-pipa-15s-paced-v01/02-zhixia-zhixia-line-two.mp3`
- Create: `zhixia-feihualing/assets/audio/fantan-pipa-15s-paced-v01/03-zhixia-zhixia-line-three.mp3`
- Create: `zhixia-feihualing/assets/audio/fantan-pipa-15s-paced-v01/04-zhixia-zhixia-line-four.mp3`
- Create: `zhixia-feihualing/assets/audio/fantan-pipa-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 的 `voice-lines.json` 和项目本地 `.env` 中的豆包语音凭证。
- Produces: 四个可独立解码的 MP3，以及包含真实时长、台词、音色和 revision 的元数据。

- [ ] **Step 1: 预览付费调用计划**

Run:

```bash
cd zhixia-feihualing
python3 scripts/generate_episode_audio.py --episode fantan-pipa-15s
```

Expected: `待生成：4 句`、`栀夏：4 句`、`预计产生豆包 TTS 调用：4 次`；预览模式不访问网络、不创建音频。

- [ ] **Step 2: 执行用户已授权的四句生成**

Run:

```bash
cd zhixia-feihualing
python3 scripts/generate_episode_audio.py --episode fantan-pipa-15s --generate
```

在程序确认提示中精确输入 `GENERATE fantan-pipa-15s`。若凭证、权限或网络不可用，停止在已完成的本地清单，不伪造音频。

- [ ] **Step 3: 校验音频与元数据**

逐个使用 `ffprobe` 验证 MP3 可解码、单声道且时长大于 1 秒；使用 `jq` 验证元数据中的四句文本、角色、固定音色和 revision 与清单一致。

- [ ] **Step 4: 核对四句连续性**

按清单顺序生成临时连续试听音频并检查：同一位栀夏、无读错、吞字、额外补话、明显赶字、戏曲腔或音量突变。若仅一行不合格，提高该行 revision 并只重新生成该行，保留旧版本。

- [ ] **Step 5: 提交四句朗诵资产**

```bash
git add -- zhixia-feihualing/assets/audio/fantan-pipa-15s-paced-v01
git commit -m "生成反弹琵琶四句诗朗诵"
```

---

### Task 3: 实现原声零衰减高清构建

**Files:**
- Create: `zhixia-feihualing/scripts/build_fantan_pipa_15s_final.sh`
- Reuse: `zhixia-feihualing/scripts/render_story_subtitle_cards.swift`
- Create: `zhixia-feihualing/assets/subtitles/fantan-pipa-15s/01-poem-line-one.png`
- Create: `zhixia-feihualing/assets/subtitles/fantan-pipa-15s/02-poem-line-two.png`
- Create: `zhixia-feihualing/assets/subtitles/fantan-pipa-15s/03-poem-line-three.png`
- Create: `zhixia-feihualing/assets/subtitles/fantan-pipa-15s/04-poem-line-four.png`
- Create: `zhixia-feihualing/exports/fantan-pipa-15s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/fantan-pipa-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: Task 1 的原片与字幕计划、Task 2 的四条 MP3。
- Produces: 保留原声 0 dB 的无字幕朗诵试听版，以及在相同画面和音频上叠加四句字幕的最终版。

- [ ] **Step 1: 写最小构建脚本骨架**

脚本必须校验所有输入，创建临时目录，渲染四张透明字幕卡，并保证临时文件在退出时清理。视频滤镜固定使用：

```text
scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,
crop=1080:1920:(iw-1080)/2:0,
hqdn3d=0.6:0.6:1.8:1.8,
unsharp=5:5:0.22:3:3:0,
eq=contrast=1.02:saturation=1.02,
fps=24,format=yuv420p
```

不得使用补帧或生成式超分辨率。

- [ ] **Step 2: 按真实音频时长确定四句 trim 与 atempo**

对每条 MP3 使用 `silencedetect=noise=-45dB:d=0.05` 查看头尾静音，选择不截字的 `atrim start/end`。每句目标有效朗诵长度分别不超过 2.850、2.850、2.900、4.050 秒；`atempo` 必须处于 `0.65—1.05`，并将四句分别延迟到 250、3550、6900、10350 毫秒。

每条处理链均依次使用：

```text
atrim, asetpts=PTS-STARTPTS, atempo, aresample=48000,
aformat=channel_layouts=stereo, adelay
```

- [ ] **Step 3: 实现原声 0 dB 混音**

四句先以 `amix=inputs=4:duration=longest:dropout_transition=0:normalize=0` 合并，再仅对人声总线使用轻压缩或 `loudnorm=I=-21:TP=-3:LRA=7`。原声处理链必须精确保留：

```text
[0:a]aresample=48000,aformat=channel_layouts=stereo,volume=1.0[bed];
[bed][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,
alimiter=limit=0.891251:attack=5:release=50[aout]
```

不得加入 `sidechaincompress`、`sidechaingate`、按时间变化的 `volume`、原声 `loudnorm` 或总线 `loudnorm`。`0.891251` 对应 −1.0 dBFS 峰值上限；最终仍需用响度工具检查近似真峰值。

- [ ] **Step 4: 输出无字幕试听版**

输出 `fantan-pipa-15s-voiced-v01.mp4`，视频编码使用：

```text
libx264 -preset slow -crf 17 -pix_fmt yuv420p
```

音频使用 48kHz 双声道 AAC 192kbps，并写入 `-movflags +faststart`。输出时长取源视频实际时长，不截断第四句。

- [ ] **Step 5: 叠加逐句竖排字幕并输出最终版**

四张字幕卡分别在 `0.250—3.100`、`3.550—6.400`、`6.900—9.800`、`10.350—14.400` 秒启用。每张卡使用 0.120 秒透明度淡入淡出；第一张带题署，后三张无题署。最终输出 `fantan-pipa-15s-subtitled-v01.mp4`，直接复制试听版音轨，不再次处理音频。

- [ ] **Step 6: 运行构建并让失败测试转绿**

Run:

```bash
zsh zhixia-feihualing/scripts/build_fantan_pipa_15s_final.sh
zsh zhixia-feihualing/tests/test_fantan_pipa_15s_final.sh
```

Expected: PASS；两个输出均为 1080×1920、24fps、H.264、48kHz 双声道 AAC，时长 15.0—15.2 秒，字幕卡恰好四张，测试确认脚本不存在闪避滤镜。

- [ ] **Step 7: 提交构建脚本、测试、字幕卡与成片**

```bash
git add -- zhixia-feihualing/scripts/build_fantan_pipa_15s_final.sh zhixia-feihualing/tests/test_fantan_pipa_15s_final.sh zhixia-feihualing/assets/subtitles/fantan-pipa-15s zhixia-feihualing/exports/fantan-pipa-15s-voiced-v01.mp4 zhixia-feihualing/exports/fantan-pipa-15s-subtitled-v01.mp4
git commit -m "制作反弹琵琶朗诵字幕成片"
```

---

### Task 4: 视觉、音频与归档验收

**Files:**
- Modify: `zhixia-feihualing/episodes/fantan-pipa-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Create: `zhixia-feihualing/episodes/fantan-pipa-15s/qa-recitation-subtitles-v01.md`

**Interfaces:**
- Consumes: Task 3 的两个成片、四条语音和全部源资产。
- Produces: 可追溯的成片状态、资产记录与最终验收证据。

- [ ] **Step 1: 抽帧检查字幕避让和画质**

在 0.5、2.8、4.0、6.2、7.3、9.6、10.8、14.1 秒抽帧，检查竖排字幕没有遮挡脸、主要手势、腿部、蓝橙飘带或右下角 AI 标识；对比原片确认人物比例未拉伸、脸部未重绘、锐化无白边。

- [ ] **Step 2: 检查混音实现与指标**

静态检查构建脚本确认原声链为 `volume=1.0`，且不存在 sidechain、动态 volume 和原声 loudnorm。使用 `loudnorm=print_format=json` 与 `astats` 检查试听版无削波、近似真峰值不高于 −1.0 dBTP；人工试听确认背景音乐在人声进入和退出时没有突降、回升或泵动，四句清楚完整且未压过舞蹈气势。

- [ ] **Step 3: 写 QA 记录**

`qa-recitation-subtitles-v01.md` 记录源片哈希、四句实际进入与结束、每条人声处理参数、背景原声增益、最终响度与峰值、字幕避让抽帧、媒体规格和 `PASS/FAIL` 结论。若失败，只记录首要问题并修复后重新运行全部验证，不把失败成片登记为正式版本。

- [ ] **Step 4: 更新单集状态和资产清单**

README 记录源片已归档、固定声音、无闪避混音、字幕方案、试听版和最终版路径。资产清单新增源片、四条语音、试听版和最终字幕成片；每行保持九列并使用唯一 asset ID，不修改无关条目。

- [ ] **Step 5: 运行最终验证**

Run:

```bash
zsh zhixia-feihualing/tests/test_fantan_pipa_15s_final.sh
ffmpeg -v error -i zhixia-feihualing/exports/fantan-pipa-15s-voiced-v01.mp4 -f null -
ffmpeg -v error -i zhixia-feihualing/exports/fantan-pipa-15s-subtitled-v01.mp4 -f null -
git diff --check -- zhixia-feihualing/episodes/fantan-pipa-15s/README.md zhixia-feihualing/assets/inventory.csv zhixia-feihualing/episodes/fantan-pipa-15s/qa-recitation-subtitles-v01.md
```

Expected: 专用测试 PASS、两个视频完整解码无错误、文档与 CSV 无空白错误。

- [ ] **Step 6: 提交验收与归档状态**

```bash
git add -- zhixia-feihualing/episodes/fantan-pipa-15s/README.md zhixia-feihualing/assets/inventory.csv zhixia-feihualing/episodes/fantan-pipa-15s/qa-recitation-subtitles-v01.md
git commit -m "归档反弹琵琶朗诵字幕成片"
```
