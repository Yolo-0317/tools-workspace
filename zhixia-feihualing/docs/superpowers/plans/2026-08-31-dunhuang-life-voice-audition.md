# 敦煌生活映射朗诵音色试听 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用同一段敦煌生活映射文案生成四条豆包纯人声样片，供用户直接比较音色与自然时长。

**Architecture:** 复用现有 `generate_episode_audio.py` 安全生成管线，只新增三个候选音色配置和一个四行试听清单。每个候选按单行模式独立调用，某个音色无权限时记录失败并继续下一个；生成后使用现有音频探测能力核验格式与时长。

**Tech Stack:** Python 3、豆包 Seed TTS 2.0、JSON manifest、`unittest`、FFmpeg/ffprobe

## Global Constraints

- 四条样片朗读完全相同的固定文案。
- 基准音色固定为现有 `zhixia` 对应的 `ICL_uranus_zh_female_tianmeihuopo_tob`，不得改写该配置。
- 每条样片是一次连续合成，`speech_rate` 固定为 `0`。
- 输出必须是 24 kHz、单声道、64 kbps MP3，不添加配乐或后期变速。
- 不修改现有 `zhixia` 默认音色。
- 只允许四个已确认候选各产生一次豆包 TTS 调用；单个候选失败后不得自动改用其他音色。
- 舞蹈三个高潮时间窗不在本计划中修改。

---

### Task 1: 建立可验证的四音色试听清单

**Files:**
- Modify: `config/voices.json`
- Create: `episodes/dunhuang-life-voice-audition/voice-lines.json`
- Create: `tests/test_dunhuang_life_voice_audition.py`

**Interfaces:**
- Consumes: `load_voice_config(path)` 与 `load_episode_manifest(path, voices)`。
- Produces: 可被 `generate_episode_audio.py --episode dunhuang-life-voice-audition` 读取的四行 manifest。

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from zhixia_tts_manifest import load_episode_manifest, load_voice_config


def test_dunhuang_life_voice_audition_manifest():
    voices = load_voice_config(ROOT / "config" / "voices.json")
    manifest = load_episode_manifest(
        ROOT / "episodes/dunhuang-life-voice-audition/voice-lines.json",
        voices,
    )
    expected_text = (
        "看山恰似走来迎。仔细看山，山不动，是船行。"
        "有时候，你以为是世界变了。其实，是你终于开始往前走了。"
    )
    assert [line.role for line in manifest.lines] == [
        "zhixia",
        "zhixia-qingchezizi-test",
        "zhixia-zhixingnv-test",
        "zhixia-wenrouxiaoya-test",
    ]
    assert {line.text for line in manifest.lines} == {expected_text}
    assert {line.speech_rate for line in manifest.lines} == {0}
    assert {manifest.voices[line.role].resource_id for line in manifest.lines} == {
        "seed-tts-2.0"
    }
    assert manifest.audio_slug == "dunhuang-huanxisha-life-voice-audition-v01"
```

- [ ] **Step 2: 运行测试并确认先失败**

Run: `python3 -m unittest tests.test_dunhuang_life_voice_audition -v`

Expected: FAIL，提示试听 manifest 不存在。

- [ ] **Step 3: 添加三个候选音色配置**

在 `config/voices.json` 保留现有键值不变，并新增：

```json
"zhixia-qingchezizi-test": {
  "name": "栀夏·清澈梓梓候选",
  "speaker": "zh_female_qingchezizi_uranus_bigtts",
  "resource_id": "seed-tts-2.0"
},
"zhixia-zhixingnv-test": {
  "name": "栀夏·知性女声候选",
  "speaker": "zh_female_zhixingnv_uranus_bigtts",
  "resource_id": "seed-tts-2.0"
},
"zhixia-wenrouxiaoya-test": {
  "name": "栀夏·温柔小雅候选",
  "speaker": "zh_female_wenrouxiaoya_uranus_bigtts",
  "resource_id": "seed-tts-2.0"
}
```

- [ ] **Step 4: 创建试听 manifest**

创建 `episodes/dunhuang-life-voice-audition/voice-lines.json`：

```json
{
  "episode": "dunhuang-life-voice-audition",
  "format": "one-poem-story",
  "theme": "敦煌生活映射朗诵音色试听",
  "theme_slug": "dunhuang-life-voice-audition",
  "audio_slug": "dunhuang-huanxisha-life-voice-audition-v01",
  "lines": [
    {
      "id": "01-current-zhixia",
      "role": "zhixia",
      "text": "看山恰似走来迎。仔细看山，山不动，是船行。有时候，你以为是世界变了。其实，是你终于开始往前走了。",
      "revision": 1,
      "speech_rate": 0
    },
    {
      "id": "02-qingchezizi",
      "role": "zhixia-qingchezizi-test",
      "text": "看山恰似走来迎。仔细看山，山不动，是船行。有时候，你以为是世界变了。其实，是你终于开始往前走了。",
      "revision": 1,
      "speech_rate": 0
    },
    {
      "id": "03-zhixingnv",
      "role": "zhixia-zhixingnv-test",
      "text": "看山恰似走来迎。仔细看山，山不动，是船行。有时候，你以为是世界变了。其实，是你终于开始往前走了。",
      "revision": 1,
      "speech_rate": 0
    },
    {
      "id": "04-wenrouxiaoya",
      "role": "zhixia-wenrouxiaoya-test",
      "text": "看山恰似走来迎。仔细看山，山不动，是船行。有时候，你以为是世界变了。其实，是你终于开始往前走了。",
      "revision": 1,
      "speech_rate": 0
    }
  ]
}
```

- [ ] **Step 5: 运行测试并确认通过**

Run: `python3 -m unittest tests.test_dunhuang_life_voice_audition -v`

Expected: PASS。

- [ ] **Step 6: 提交清单与测试**

```bash
git add zhixia-feihualing/config/voices.json \
  zhixia-feihualing/episodes/dunhuang-life-voice-audition/voice-lines.json \
  zhixia-feihualing/tests/test_dunhuang_life_voice_audition.py
git commit -m "配置敦煌朗诵四音色试听"
```

### Task 2: 预检四次调用与凭证

**Files:**
- Inspect: `episodes/dunhuang-life-voice-audition/voice-lines.json`
- Inspect: `.env`，只检查键是否存在，不输出其值

**Interfaces:**
- Consumes: Task 1 的试听 manifest。
- Produces: 明确显示 4 条待生成、4 次 API 调用和目标输出目录的零成本预览。

- [ ] **Step 1: 执行零成本预览**

Run: `python3 scripts/generate_episode_audio.py --episode dunhuang-life-voice-audition`

Expected: 输出 `待生成：4 句`、`预计产生豆包 TTS 调用：4 次`，并说明当前为预览模式。

- [ ] **Step 2: 静默检查凭证是否存在**

Run: `test -n "${VOLCENGINE_SPEECH_API_KEY:-}" || rg -q '^VOLCENGINE_SPEECH_API_KEY=' .env`

Expected: exit code 0；终端不出现凭证内容。

### Task 3: 独立生成四条试听样片

**Files:**
- Create: `assets/audio/dunhuang-huanxisha-life-voice-audition-v01/*.mp3`
- Create: `assets/audio/dunhuang-huanxisha-life-voice-audition-v01/audio-metadata.json`
- Conditionally create: `episodes/dunhuang-life-voice-audition/subtitles-dunhuang-life-voice-audition.json`

**Interfaces:**
- Consumes: Task 1 manifest 与项目内豆包凭证。
- Produces: 四条独立 MP3；无权限候选在 metadata 中保留 `failed` 状态。

- [ ] **Step 1: 生成现有栀夏基准样片**

Run: `python3 scripts/generate_episode_audio.py --episode dunhuang-life-voice-audition --line 01-current-zhixia --generate`

Confirmation: `GENERATE dunhuang-life-voice-audition`

Expected: 生成 `01-zhixia-current-zhixia.mp3`，或记录该音色的明确失败状态。

- [ ] **Step 2: 生成清澈梓梓样片**

Run: `python3 scripts/generate_episode_audio.py --episode dunhuang-life-voice-audition --line 02-qingchezizi --generate`

Confirmation: `GENERATE dunhuang-life-voice-audition`

Expected: 生成 `02-zhixia-qingchezizi-test-qingchezizi.mp3`，或记录该音色的明确失败状态。

- [ ] **Step 3: 生成知性女声样片**

Run: `python3 scripts/generate_episode_audio.py --episode dunhuang-life-voice-audition --line 03-zhixingnv --generate`

Confirmation: `GENERATE dunhuang-life-voice-audition`

Expected: 生成 `03-zhixia-zhixingnv-test-zhixingnv.mp3`，或记录该音色的明确失败状态。

- [ ] **Step 4: 生成温柔小雅样片**

Run: `python3 scripts/generate_episode_audio.py --episode dunhuang-life-voice-audition --line 04-wenrouxiaoya --generate`

Confirmation: `GENERATE dunhuang-life-voice-audition`

Expected: 生成 `04-zhixia-wenrouxiaoya-test-wenrouxiaoya.mp3`，或记录该音色的明确失败状态。

### Task 4: 核验并交付试听

**Files:**
- Inspect: `assets/audio/dunhuang-huanxisha-life-voice-audition-v01/audio-metadata.json`
- Inspect: `assets/audio/dunhuang-huanxisha-life-voice-audition-v01/*.mp3`

**Interfaces:**
- Consumes: Task 3 的音频和 metadata。
- Produces: 每条成功样片的音色名、实际时长与可点击试听入口。

- [ ] **Step 1: 运行项目专项测试和 TTS 回归测试**

Run: `python3 -m unittest tests.test_dunhuang_life_voice_audition tests.test_generate_episode_audio -v`

Expected: 全部 PASS。

- [ ] **Step 2: 核验每条成功 MP3 的编码参数**

Run: `for file in assets/audio/dunhuang-huanxisha-life-voice-audition-v01/*.mp3; do ffprobe -v error -show_entries format=duration,bit_rate:stream=codec_name,sample_rate,channels -of json "$file"; done`

Expected: 每条均为 MP3、24000 Hz、单声道、约 64000 bit/s，时长大于 0；metadata 中的 `duration_ms` 与探测结果一致。

- [ ] **Step 3: 检查改动范围**

Run: `git status --short`

Expected: 只把本次试听相关的新文件和已知配置改动纳入汇报，不覆盖工作区原有未提交内容。

- [ ] **Step 4: 向用户交付试听**

在最终回复中按 `现有栀夏 / 清澈梓梓 / 知性女声 / 温柔小雅` 顺序列出成功样片，标注自然时长并使用绝对路径嵌入音频；对失败候选说明接口返回的失败类别，不暴露凭证或请求密钥。
