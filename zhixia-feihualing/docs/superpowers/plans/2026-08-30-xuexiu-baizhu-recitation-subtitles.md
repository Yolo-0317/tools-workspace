# 《雪袖白纻》朗诵字幕高清成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认保留的 15.069 秒《雪袖白纻》原片制作成栀夏四句诗朗诵、逐句竖排字幕、背景音乐全程不降音量的 1080×1920 发布成片。

**Architecture:** 将下载视频原样归档到单集目录，使用现有豆包 TTS 流水线按句生成栀夏固定音色。专用构建脚本完成画面保真放大、人声排布、原声直接混合、总线峰值保护和透明字幕卡叠加，分别输出无字幕朗诵试听版与正式字幕版；独立门禁检查文本、时间轴、原片哈希、无音乐闪避、媒体参数和产物完整性。

**Tech Stack:** JSON、Python TTS 流水线、Swift/AppKit 字幕卡渲染、FFmpeg、FFprobe、zsh、jq、Git

## Global Constraints

- 源视频固定为 `/Users/huan.yu/Downloads/4b3a6780-fa45-4745-ba77-c2dc6343752a.mp4`，496×864、24fps、15.069002 秒、H.264/AAC；原下载文件保持不变。
- 四句固定为“吴刀剪彩缝舞衣。”“明妆丽服夺春晖。”“扬眉转袖若雪飞。”“倾城独立世所稀。”，使用栀夏固定音色 `ICL_uranus_zh_female_tianmeihuopo_tob`。
- 字幕时间窗固定为 `0.250—3.200`、`3.500—6.450`、`6.750—9.850`、`10.150—14.650` 秒。
- 背景音乐全程保持原始时间结构和相对音量；不使用 `sidechaincompress`，不在人声区间设置原声音量包络。
- 最终总线只做统一峰值限制；输出 H.264、1080×1920、24fps、AAC 192kbps、48kHz 双声道。
- 字幕位于左侧安全区，第一句题署为“唐·李白《白纻辞三首·其三》”。
- 正式字幕版直接复制无字幕朗诵版音轨，确保两版音轨内容一致。
- 本次不重绘或修复原片动作、人物、舞绸、长影、场景和右下角已有标识。

---

## 文件结构

- `episodes/xuexiu-baizhu-15s/assets/video/content-seedance-v01.mp4`：项目内原片副本。
- `episodes/xuexiu-baizhu-15s/voice-lines.json`：四句配音清单。
- `episodes/xuexiu-baizhu-15s/subtitle-plan.json`：四句字幕时间轴。
- `tests/test_xuexiu_baizhu_15s_final.sh`：成片门禁。
- `scripts/build_xuexiu_baizhu_15s_final.sh`：高清混音与字幕合成入口。
- `assets/audio/xuexiu-baizhu-15s-paced-v01/`：四句 TTS 与元数据。
- `assets/subtitles/xuexiu-baizhu-15s/`：四张透明字幕卡。
- `exports/xuexiu-baizhu-15s-voiced-v01.mp4`：无字幕朗诵试听版。
- `exports/xuexiu-baizhu-15s-subtitled-v01.mp4`：正式字幕成片。

### Task 1: 固定输入、清单和失败门禁

**Files:**
- Create: `zhixia-feihualing/episodes/xuexiu-baizhu-15s/assets/video/content-seedance-v01.mp4`
- Create: `zhixia-feihualing/episodes/xuexiu-baizhu-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/xuexiu-baizhu-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/tests/test_xuexiu_baizhu_15s_final.sh`

**Interfaces:**
- Consumes: 已确认原片及设计规范中的诗句、时间窗和声音规则。
- Produces: TTS 清单、字幕清单、归档原片，以及在构建产物缺失时明确失败的门禁。

- [ ] **Step 1: 写入失败门禁**

门禁使用以下断言检查配音与字幕清单：

```zsh
jq -e '
  .episode == "xuexiu-baizhu-15s" and
  .audio_slug == "xuexiu-baizhu-15s-paced-v01" and
  [.lines[].role] == ["zhixia","zhixia","zhixia","zhixia"] and
  [.lines[].text] == [
    "吴刀剪彩缝舞衣。",
    "明妆丽服夺春晖。",
    "扬眉转袖若雪飞。",
    "倾城独立世所稀。"
  ]
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == [
    "吴刀剪彩缝舞衣",
    "明妆丽服夺春晖",
    "扬眉转袖若雪飞",
    "倾城独立世所稀"
  ] and
  .[0].start == 0.250 and .[0].end == 3.200 and
  .[1].start == 3.500 and .[1].end == 6.450 and
  .[2].start == 6.750 and .[2].end == 9.850 and
  .[3].start == 10.150 and .[3].end == 14.650 and
  .[0].attribution == "唐·李白《白纻辞三首·其三》"
' "$subtitle_plan" >/dev/null
```

门禁同时检查：下载原片与项目归档 SHA-256 一致；四个 MP3 存在；构建脚本不含 `sidechaincompress` 或区间音量表达式；两个输出为 1080×1920、24fps、约 15.069 秒、48kHz 双声道 AAC；两个输出提取的音轨 SHA-256 一致。

- [ ] **Step 2: 运行测试确认失败**

Run: `zsh tests/test_xuexiu_baizhu_15s_final.sh`

Expected: FAIL，首先报告缺少配音清单、字幕计划、归档原片或构建产物，而不是 zsh 语法错误。

- [ ] **Step 3: 创建配音清单**

`voice-lines.json` 固定使用：

```json
{
  "episode": "xuexiu-baizhu-15s",
  "format": "one-poem-story",
  "theme": "雪袖白纻十五秒四句诗朗诵",
  "theme_slug": "xuexiu-baizhu-15s",
  "audio_slug": "xuexiu-baizhu-15s-paced-v01",
  "lines": [
    {"id":"01-zhixia-line-one","role":"zhixia","text":"吴刀剪彩缝舞衣。","revision":1,"gap_before_ms":0},
    {"id":"02-zhixia-line-two","role":"zhixia","text":"明妆丽服夺春晖。","revision":1,"gap_before_ms":300},
    {"id":"03-zhixia-line-three","role":"zhixia","text":"扬眉转袖若雪飞。","revision":1,"gap_before_ms":300},
    {"id":"04-zhixia-line-four","role":"zhixia","text":"倾城独立世所稀。","revision":1,"gap_before_ms":300}
  ]
}
```

每项补充一个 `context_texts` 数组：固定同一位栀夏清透明亮女声、自然说诗、不念作者篇名、不添加额外内容；四句分别强调“舞衣”舒展收住、“春晖”明亮温润、“转袖若雪飞”流动清楚、“倾城独立世所稀”从容开阔并完整收尾。

- [ ] **Step 4: 创建字幕计划**

```json
[
  {"id":"01-poem-line-one","kind":"poem","text":"吴刀剪彩缝舞衣","attribution":"唐·李白《白纻辞三首·其三》","start":0.250,"end":3.200},
  {"id":"02-poem-line-two","kind":"poem","text":"明妆丽服夺春晖","start":3.500,"end":6.450},
  {"id":"03-poem-line-three","kind":"poem","text":"扬眉转袖若雪飞","start":6.750,"end":9.850},
  {"id":"04-poem-line-four","kind":"poem","text":"倾城独立世所稀","start":10.150,"end":14.650}
]
```

- [ ] **Step 5: 归档原片并校验哈希**

```zsh
mkdir -p episodes/xuexiu-baizhu-15s/assets/video
cp -p /Users/huan.yu/Downloads/4b3a6780-fa45-4745-ba77-c2dc6343752a.mp4 episodes/xuexiu-baizhu-15s/assets/video/content-seedance-v01.mp4
shasum -a 256 /Users/huan.yu/Downloads/4b3a6780-fa45-4745-ba77-c2dc6343752a.mp4 episodes/xuexiu-baizhu-15s/assets/video/content-seedance-v01.mp4
```

Expected: 两个 SHA-256 完全一致。

- [ ] **Step 6: 提交清单和门禁**

```zsh
git add episodes/xuexiu-baizhu-15s/voice-lines.json episodes/xuexiu-baizhu-15s/subtitle-plan.json tests/test_xuexiu_baizhu_15s_final.sh
git commit -m "建立雪袖白纻朗诵字幕门禁"
```

原片副本保持项目内归档，但按照既有媒体管理规则不随 Git 提交。

### Task 2: 生成四句栀夏朗诵

**Files:**
- Create: `zhixia-feihualing/assets/audio/xuexiu-baizhu-15s-paced-v01/01-zhixia-zhixia-line-one.mp3`
- Create: `zhixia-feihualing/assets/audio/xuexiu-baizhu-15s-paced-v01/02-zhixia-zhixia-line-two.mp3`
- Create: `zhixia-feihualing/assets/audio/xuexiu-baizhu-15s-paced-v01/03-zhixia-zhixia-line-three.mp3`
- Create: `zhixia-feihualing/assets/audio/xuexiu-baizhu-15s-paced-v01/04-zhixia-zhixia-line-four.mp3`
- Create: `zhixia-feihualing/assets/audio/xuexiu-baizhu-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 的配音清单与项目现有 TTS 凭证。
- Produces: 四个独立 MP3 和生成元数据。

- [ ] **Step 1: 预览调用计划**

Run: `python3 scripts/generate_episode_audio.py --episode xuexiu-baizhu-15s`

Expected: 显示待生成 4 句、栀夏 4 句、预计调用 4 次；预览不创建音频。

- [ ] **Step 2: 执行音频生成**

Run: `python3 scripts/generate_episode_audio.py --episode xuexiu-baizhu-15s --generate`

确认文本固定为 `GENERATE xuexiu-baizhu-15s`。如凭证或网络不可用，报告实际阻塞，不创建占位音频。

- [ ] **Step 3: 校验四句音频**

```zsh
for f in assets/audio/xuexiu-baizhu-15s-paced-v01/*.mp3; do
  ffprobe -v error -show_entries stream=codec_name,sample_rate,channels -show_entries format=duration -of json "$f" | jq -e '
    .streams[0].codec_name == "mp3" and
    .streams[0].sample_rate == "24000" and
    .streams[0].channels == 1 and
    (.format.duration | tonumber) > 1.0
  ' >/dev/null
done
```

使用 `jq` 核对 `audio-metadata.json` 中四句文本、角色、音色和 revision 与清单完全一致。

### Task 3: 构建高清朗诵与字幕版

**Files:**
- Create: `zhixia-feihualing/scripts/build_xuexiu_baizhu_15s_final.sh`
- Reuse: `zhixia-feihualing/scripts/render_story_subtitle_cards.swift`
- Create: `zhixia-feihualing/assets/subtitles/xuexiu-baizhu-15s/*.png`
- Create: `zhixia-feihualing/exports/xuexiu-baizhu-15s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/xuexiu-baizhu-15s-subtitled-v01.mp4`

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

四句先按实际有效语音区间 `atrim`，再在 `atempo=0.5—2.0` 的自然语速范围内对齐目标窗口，并分别使用 `adelay=250|250`、`3500|3500`、`6750|6750`、`10150|10150` 定位。执行时将四个实际 `atrim` 与 `atempo` 数值直接写入构建脚本并通过完整试听确认，不使用占位音频或静音替代。

人声完成高通、轻度均衡、压缩与响度整理。原声只规范为 48kHz 双声道，最终固定使用：

```text
[bed][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,
alimiter=limit=0.870964:attack=5:release=80:level=false[aout]
```

字幕卡按四个窗口各使用 0.120 秒淡入淡出；正式版直接复制试听版音轨。

- [ ] **Step 2: 运行构建与门禁**

Run: `zsh tests/test_xuexiu_baizhu_15s_final.sh`

Expected: 生成四张字幕卡、两个 MP4，输出 `PASS: Xuexiu Baizhu four-line recitation HD finals are ready`。

- [ ] **Step 3: 验证背景音乐保持原音量**

```zsh
! rg -q 'sidechaincompress|volume=.*enable|volume=.*between' scripts/build_xuexiu_baizhu_15s_final.sh
rg -q 'amix=inputs=2:duration=first:dropout_transition=0:normalize=0' scripts/build_xuexiu_baizhu_15s_final.sh
rg -q 'alimiter=limit=0.870964:attack=5:release=80:level=false' scripts/build_xuexiu_baizhu_15s_final.sh
```

完整试听四个人声区间和三个句间空白，确认鼓点与环境声连续、没有抽吸；统一总线限制器只处理叠加峰值。

- [ ] **Step 4: 提交构建入口**

```zsh
git add scripts/build_xuexiu_baizhu_15s_final.sh tests/test_xuexiu_baizhu_15s_final.sh
git commit -m "制作雪袖白纻朗诵字幕高清成片"
```

### Task 4: 视觉听觉验收与登记

**Files:**
- Modify: `zhixia-feihualing/episodes/xuexiu-baizhu-15s/README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3 的试听版、正式版、字幕卡和媒体探测数据。
- Produces: 验收记录、最终路径和资产登记。

- [ ] **Step 1: 抽帧检查字幕与画质**

```zsh
for t in 0.5 2.9 3.8 6.2 7.2 9.6 10.8 14.3; do
  ffmpeg -v error -ss "$t" -i exports/xuexiu-baizhu-15s-subtitled-v01.mp4 -frames:v 1 "/tmp/xuexiu-baizhu-$t.png"
done
```

逐张确认字幕位于左侧安全区，避开栀夏面部和躯干中心；与外围飘带或长影少量重叠可接受。画面保持自然比例，右下角已有标识保持原样。

- [ ] **Step 2: 完整试听并核对两版音轨**

```zsh
for f in exports/xuexiu-baizhu-15s-voiced-v01.mp4 exports/xuexiu-baizhu-15s-subtitled-v01.mp4; do
  ffmpeg -v error -i "$f" -map 0:a:0 -c copy -f adts "/tmp/${f:t:r}.aac"
done
shasum -a 256 /tmp/xuexiu-baizhu-15s-voiced-v01.aac /tmp/xuexiu-baizhu-15s-subtitled-v01.aac
```

Expected: 两个 AAC 提取文件 SHA-256 完全一致。完整试听四句读音、音色、句尾、留白和音量一致性；确认第四句在 14.650 秒前收住，原背景音乐全程连续。

- [ ] **Step 3: 更新 README 与资产清单**

README 记录原片确认保留、诗句、四个时间窗、背景音乐不降低、试听版与正式版路径、媒体参数和抽帧验收结论。`assets/inventory.csv` 只追加本集原片归档、四句音频、四张字幕卡、试听版和正式版必要记录；保持九列与唯一 `asset_id`，不记录凭证或下载目录路径。

- [ ] **Step 4: 最终验证并提交登记**

```zsh
zsh tests/test_xuexiu_baizhu_15s_prompt.sh
zsh tests/test_xuexiu_baizhu_15s_final.sh
git diff --check -- episodes/xuexiu-baizhu-15s scripts/build_xuexiu_baizhu_15s_final.sh tests/test_xuexiu_baizhu_15s_final.sh assets/inventory.csv
awk -F, 'NF != 9 {print NR ":" NF; bad=1} END {exit bad}' assets/inventory.csv
```

Expected: 两个测试 PASS，格式检查无输出，资产清单每行九列。

```zsh
git add episodes/xuexiu-baizhu-15s/README.md assets/inventory.csv
git commit -m "登记雪袖白纻朗诵字幕成片"
```

若资产清单同时包含其他用户未提交改动，只暂存本次新增的 `xuexiu-baizhu-15s` 记录并单独提交；不暂存其他单集、角色母板或无关资产。
