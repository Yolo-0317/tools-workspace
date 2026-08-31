# 《九歌·云中君》缓慢朗诵字幕成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认保留的《九歌·云中君》15.093 秒原片制作成两句缓慢朗诵的无字幕试听版与正式竖排字幕版。

**Architecture:** 复用现有栀夏豆包 TTS 清单和九歌竖排字幕卡渲染器，先逐句生成并测量有效人声，再以受限不变调轻度减速对齐两个长时间窗。专用 FFmpeg 构建脚本完成保真高清放大、约 3 dB 平滑音乐避让、人声混合和两张透明字幕卡叠加；独立门禁验证文本、语速占比、媒体规格、字幕安全区与两版音轨一致性。

**Tech Stack:** JSON、Python TTS 流水线、Zsh、FFmpeg/FFprobe、Swift/AppKit、jq、Git。

## Global Constraints

- 原片固定为 `episodes/jiuge-yunzhongjun-15s/assets/video/content-raw-v01.mp4`，不重生成、不改舞蹈和镜头。
- 只朗诵“灵皇皇兮既降。猋远举兮云中。”，不念作者、题目、篇名或其他内容。
- 第一行时间窗固定为 1.000—6.200 秒，第二行固定为 7.700—13.500 秒。
- 第一行有效人声目标 4.300—4.700 秒；第二行目标 4.800—5.200 秒；分别占各自时间窗 82%—90%。
- “猋”必须读作 `biāo`；两句保持同一栀夏固定女声、同一距离与高天空间感。
- 缓慢必须体现在句内字间、气息和句尾留韵；生成偏快时优先重生，轻度 `atempo` 只允许 0.78—1.02。
- 第一张竖排字幕在右侧并附“屈原《九歌·云中君》节选”，第二张在左侧；不得遮挡脸、双手、袖缘、身体中轴和右下角“AI生成”标识。
- 原片音乐在人声期间只做约 3 dB 平滑轻度避让，非人声区间恢复原音量；无明显泵动。
- 输出 `exports/jiuge-yunzhongjun-15s-voiced-v01.mp4` 与 `exports/jiuge-yunzhongjun-15s-subtitled-v01.mp4`，均为 1080×1920、24 fps、H.264、48 kHz 双声道 AAC、约 15.093 秒。
- 保留右下角原片“AI生成”标识，不遮挡、不裁掉。

---

### Task 1: 建立朗诵与字幕数据契约

**Files:**
- Create: `zhixia-feihualing/episodes/jiuge-yunzhongjun-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/jiuge-yunzhongjun-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/tests/test_yunzhongjun_recitation_manifest.py`

**Interfaces:**
- Consumes: `config/voices.json` 中的 `zhixia` 固定音色、已确认设计稿中的两句文本和时间窗。
- Produces: `generate_episode_audio.py --episode jiuge-yunzhongjun-15s` 可读取的两句 TTS 清单，以及 `render_jiuge_vertical_subtitle_cards.swift` 可读取的两项字幕清单。

- [ ] **Step 1: 写入失败的清单契约测试**

测试加载两个 JSON，并断言：`format=one-poem-story`、两句文本、`start_ms` 为 1000/7700、两侧为 right/left、第一句题署准确、第二句无题署、时间窗为 1.000—6.200 与 7.700—13.500。

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_yunzhongjun_voice_and_subtitle_contract():
    episode = ROOT / "episodes" / "jiuge-yunzhongjun-15s"
    voice = json.loads((episode / "voice-lines.json").read_text(encoding="utf-8"))
    subtitle = json.loads((episode / "subtitle-plan.json").read_text(encoding="utf-8"))

    assert voice["episode"] == "jiuge-yunzhongjun-15s"
    assert voice["format"] == "one-poem-story"
    assert voice["audio_slug"] == "jiuge-yunzhongjun-15s-slow-v01"
    assert [line["text"] for line in voice["lines"]] == ["灵皇皇兮既降。", "猋远举兮云中。"]
    assert [line["start_ms"] for line in voice["lines"]] == [1000, 7700]

    assert [(item["text"], item["side"]) for item in subtitle] == [
        ("灵皇皇兮既降", "right"),
        ("猋远举兮云中", "left"),
    ]
    assert subtitle[0]["attribution"] == "屈原《九歌·云中君》节选"
    assert "attribution" not in subtitle[1]
    assert [(item["start"], item["end"]) for item in subtitle] == [
        (1.0, 6.2),
        (7.7, 13.5),
    ]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```zsh
cd zhixia-feihualing
python3 -m pytest tests/test_yunzhongjun_recitation_manifest.py -q
```

Expected: FAIL，提示 `voice-lines.json` 或 `subtitle-plan.json` 不存在。

- [ ] **Step 3: 写入两句配音清单**

`voice-lines.json` 使用以下固定字段：

```json
{
  "episode": "jiuge-yunzhongjun-15s",
  "format": "one-poem-story",
  "theme": "九歌云中君十五秒两句缓慢朗诵",
  "theme_slug": "jiuge-yunzhongjun-15s",
  "audio_slug": "jiuge-yunzhongjun-15s-slow-v01",
  "lines": [
    {
      "id": "01-zhixia-line-one",
      "role": "zhixia",
      "text": "灵皇皇兮既降。",
      "revision": 1,
      "start_ms": 1000,
      "context_texts": [
        "这是《九歌·云中君》的第一句画外朗诵。保持栀夏同一固定女声，年轻、清透、克制、低甜度，有高天云海的空间感。必须比普通说话明显舒缓，六个字在一句内部均匀展开，字间有自然气息，‘既降’缓慢落下并保留句尾余韵。自然说诗，不念作者、题目、篇名或其他内容，不使用播音腔、吟唱、耳语、拖字或神谕式夸张。"
      ]
    },
    {
      "id": "02-zhixia-line-two",
      "role": "zhixia",
      "text": "猋远举兮云中。",
      "revision": 1,
      "start_ms": 7700,
      "context_texts": [
        "承接上一句，保持同一位栀夏、同一距离和同一高天空间感的克制女声。‘猋’必须读作 biāo；六个字在一句内部缓慢、均匀、清楚地展开，‘云中’舒展收住并保留较长但自然的句尾余韵。自然说诗，不念作者、题目、篇名或其他内容，不使用播音腔、吟唱、耳语、拖字或仙侠旁白腔。"
      ]
    }
  ]
}
```

- [ ] **Step 4: 写入两项字幕清单**

`subtitle-plan.json` 固定包含：第一项 `id=01-poem-line-one`、右侧、1.000—6.200 秒及题署；第二项 `id=02-poem-line-two`、左侧、7.700—13.500 秒且无题署。两项 `kind` 均为 `poem`。

- [ ] **Step 5: 运行清单测试与 TTS 预览**

Run:

```zsh
cd zhixia-feihualing
python3 -m pytest tests/test_yunzhongjun_recitation_manifest.py -q
python3 scripts/generate_episode_audio.py --episode jiuge-yunzhongjun-15s
```

Expected: 测试 PASS；预览显示待生成 2 句、2 次豆包 TTS 调用、输出目录 `assets/audio/jiuge-yunzhongjun-15s-slow-v01`，且未调用接口。

- [ ] **Step 6: 提交清单契约**

```bash
git add zhixia-feihualing/episodes/jiuge-yunzhongjun-15s/voice-lines.json \
  zhixia-feihualing/episodes/jiuge-yunzhongjun-15s/subtitle-plan.json \
  zhixia-feihualing/tests/test_yunzhongjun_recitation_manifest.py
git commit -m "建立云中君缓慢朗诵字幕契约"
```

### Task 2: 生成并验收两句缓慢朗诵

**Files:**
- Generate: `zhixia-feihualing/assets/audio/jiuge-yunzhongjun-15s-slow-v01/01-zhixia-zhixia-line-one.mp3`
- Generate: `zhixia-feihualing/assets/audio/jiuge-yunzhongjun-15s-slow-v01/02-zhixia-zhixia-line-two.mp3`
- Inspect: `zhixia-feihualing/assets/audio/jiuge-yunzhongjun-15s-slow-v01/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 的 `voice-lines.json`、`config/voices.json` 和项目 `.env` 中的豆包语音凭证。
- Produces: 两条可独立恢复、可由构建脚本裁切和轻度调速的 MP3。

- [ ] **Step 1: 调用两次豆包 TTS**

Run:

```zsh
cd zhixia-feihualing
python3 scripts/generate_episode_audio.py --episode jiuge-yunzhongjun-15s --generate
```

在交互提示中输入：

```text
GENERATE jiuge-yunzhongjun-15s
```

Expected: 生成 2 句，两条 MP3 与元数据文件存在；不得在终端或提交中暴露 API Key。

- [ ] **Step 2: 测量两句有效语音边界**

Run:

```zsh
cd zhixia-feihualing
for audio in assets/audio/jiuge-yunzhongjun-15s-slow-v01/*.mp3; do
  ffmpeg -hide_banner -nostats -i "$audio" -af silencedetect=noise=-42dB:d=0.05 -f null - 2>&1
done
```

记录每条首段 `silence_end` 与末段 `silence_start`，有效长度为二者之差。不得截断首字辅音、尾字韵母或自然句尾余韵。

- [ ] **Step 3: 执行舒缓语速门禁**

第一句目标长度取 4.500 秒，第二句目标长度取 5.000 秒；对每句使用 `atempo = 有效源长度 / 目标长度`。只有结果在 0.78—1.02 时才进入构建脚本；若任一句低于 0.78，先将该句 `revision` 加 1，并在上下文中进一步强调“句内每字缓慢展开、不可快速念完”，只重生该句后重新测量。必须人工试听确认“猋”为 `biāo`，两句没有拖字、吟唱或机械拉伸感。

### Task 3: 构建无字幕试听版和正式字幕版

**Files:**
- Create: `zhixia-feihualing/scripts/build_yunzhongjun_15s_final.sh`
- Create: `zhixia-feihualing/tests/test_yunzhongjun_15s_final.sh`
- Generate: `zhixia-feihualing/assets/subtitles/jiuge-yunzhongjun-15s/*.png`
- Generate: `zhixia-feihualing/exports/jiuge-yunzhongjun-15s-voiced-v01.mp4`
- Generate: `zhixia-feihualing/exports/jiuge-yunzhongjun-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: Task 2 两条 MP3 的实际 `atrim` 起止值和 `atempo`、Task 1 字幕清单、既有 `render_jiuge_vertical_subtitle_cards.swift`。
- Produces: 两份媒体规格一致且音轨内容相同的 1080×1920 成片。

- [ ] **Step 1: 写入失败的成片门禁**

`test_yunzhongjun_15s_final.sh` 必须检查：构建脚本可执行；两条 MP3、两张 PNG 和两份输出存在；两份输出均为 H.264、1080×1920、24 fps、15.0—15.2 秒、AAC、48 kHz、双声道；无字幕版和字幕版 AAC 音轨哈希相同；FFmpeg 可完整解码。测试还使用 `rg` 断言构建脚本包含 `adelay=1000|1000`、`adelay=7700|7700`、两个字幕时间窗和 `sidechaincompress`。

- [ ] **Step 2: 运行门禁确认失败**

Run:

```zsh
cd zhixia-feihualing
zsh tests/test_yunzhongjun_15s_final.sh
```

Expected: FAIL，提示缺少可执行构建脚本或正式输出。

- [ ] **Step 3: 写入专用构建脚本**

脚本复用东皇太一构建器的保真高清路径：竖向缩放到 1920、居中裁成 1080×1920、轻度去噪与克制锐化、24 fps、yuv420p。两句按 Task 2 的实际边界先 `atrim`，再用已通过门禁的 `atempo` 调整到 4.500/5.000 秒，并分别 `adelay=1000|1000`、`adelay=7700|7700`。

人声轨使用高通、轻度均衡、压缩和 `loudnorm=I=-18:TP=-3:LRA=7`；原声规范为 48 kHz 双声道。使用人声副本驱动 `sidechaincompress`，参数以约 3 dB 轻度避让为目标，起落缓慢；随后混合人声并用 `alimiter` 保证真峰值不高于 −1 dBTP。

先生成无字幕试听版，再用两个透明 PNG 叠加正式字幕版：第一张 1.000—6.200 秒，第二张 7.700—13.500 秒，淡入淡出各约 0.120 秒；正式版直接复制试听版 AAC 音轨。

- [ ] **Step 4: 生成字幕卡并构建两份输出**

Run:

```zsh
cd zhixia-feihualing
chmod +x scripts/build_yunzhongjun_15s_final.sh tests/test_yunzhongjun_15s_final.sh
zsh scripts/build_yunzhongjun_15s_final.sh
```

Expected: 生成 2 张透明字幕卡，以及无字幕、正式字幕两个 MP4。

- [ ] **Step 5: 运行成片门禁**

Run:

```zsh
cd zhixia-feihualing
zsh tests/test_yunzhongjun_15s_final.sh
```

Expected: `PASS: Yunzhongjun slow recitation subtitle finals are ready`。

- [ ] **Step 6: 提交构建与门禁**

```bash
git add zhixia-feihualing/scripts/build_yunzhongjun_15s_final.sh \
  zhixia-feihualing/tests/test_yunzhongjun_15s_final.sh
git commit -m "制作云中君缓慢朗诵字幕成片"
```

### Task 4: 视觉试听复核与归档

**Files:**
- Modify: `zhixia-feihualing/episodes/jiuge-yunzhongjun-15s/qa-notes.md`
- Inspect: `zhixia-feihualing/exports/jiuge-yunzhongjun-15s-voiced-v01.mp4`
- Inspect: `zhixia-feihualing/exports/jiuge-yunzhongjun-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: Task 3 的两份最终输出和字幕卡。
- Produces: 可追溯的最终声音时间窗、有效语音占比、媒体规格、字幕安全区和版本决策。

- [ ] **Step 1: 抽取关键字幕帧并视觉检查**

从正式字幕版约 2.800 秒和 10.500 秒各抽一帧，检查右/左竖排字幕、题署、栀夏脸部、双手、袖缘、身体中轴与右下角标识。字幕不得遮挡上述安全区，“猋”字必须由当前楷体正确显示而非方框或缺字。

- [ ] **Step 2: 试听完整无字幕版与正式版**

检查两句内部节奏明显慢于《东皇太一》版本，字间自然、句尾有余韵；“猋”读音正确；句间约 1.5 秒和片尾约 1.6 秒保留音乐呼吸；音乐避让无泵动或突然跳变。

- [ ] **Step 3: 运行最终技术验证**

Run:

```zsh
cd zhixia-feihualing
python3 -m pytest tests/test_yunzhongjun_recitation_manifest.py -q
zsh tests/test_yunzhongjun_15s_final.sh
ffmpeg -v error -i exports/jiuge-yunzhongjun-15s-subtitled-v01.mp4 -f null -
```

Expected: 所有测试 PASS，完整解码无错误。

- [ ] **Step 4: 更新单片 QA 记录**

在 `qa-notes.md` 增加“缓慢朗诵字幕正式版”章节，记录：两个输出路径、两句文本、实际有效语音边界与占比、`atempo`、题署和左右字幕位置、混音方式、最终媒体规格、读音与视觉检查结论。

- [ ] **Step 5: 提交归档记录**

```bash
git add zhixia-feihualing/episodes/jiuge-yunzhongjun-15s/qa-notes.md
git commit -m "归档云中君缓慢朗诵字幕成片"
```

- [ ] **Step 6: 交付**

最终回复提供两份 MP4 的绝对路径、关键语速数据、测试结果与提交号；优先请用户试听无字幕版的声线和速度，同时说明正式字幕版已经使用同一音轨生成。
