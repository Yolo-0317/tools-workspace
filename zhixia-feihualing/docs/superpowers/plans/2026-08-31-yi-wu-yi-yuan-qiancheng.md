# 《一舞一愿·前程》首轮三条 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 制作《一舞一愿·前程》首轮三条十五秒祝福诗舞，分别覆盖重新出发、奔赴远方和走出困境，并建立可重复验证字数、朗诵时长、字幕、成片与发布数据的最小流水线。

**Architecture:** 用一个季级 JSON 固定三条文本、出处、赠送场景与硬门槛，用 Python 校验器阻止超字数、诱导转发和超时字幕进入制作。每条先通过豆包 TTS 生成三段栀夏固定声线并测量真实时长，再按真实节点设计 Seedance 舞蹈；Seedance 原片只保留音乐与环境声，后期使用同一通用构建入口叠加朗诵和两种层级字幕。三条逐条生成、逐条验收，首条通过后才继续产生后两条的付费调用。

**Tech Stack:** JSON、Python 3 标准库与 `unittest`、豆包 Seed TTS 2.0、Seedance、Swift/AppKit、FFmpeg/FFprobe、zsh、jq、CSV、Git。

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-31-yi-wu-yi-yuan-blessing-series-design.md`。
- 公开栏目名固定为《一舞一愿》；栏目名只用于封面、合集和发布文案，不进入朗诵，不作为成片持续水印。
- 三条文本逐字固定为本计划“文件结构”中的季级 JSON；改字必须先更新设计与季级 JSON，不能只改配音清单。
- 赠送对象句不超过 10 个汉字，现代祝福句不超过 12 个汉字，古诗不超过 14 个汉字，总计不超过 34 个汉字；三条当前均为 32 字。
- 所有人声必须在 11.500 秒前自然结束，末尾至少保留 3.000 秒无人声音乐、舞蹈和画面余韵。
- 栀夏固定使用 `speech_rate=0` 的现有音色；禁止 `atempo`、机械加速、截断有效人声、播音腔、广告祝福腔、吟唱和拖腔。
- 《一舞一愿》因固定音色和精确时长要求，明确使用后期 TTS；Seedance 原片只生成音乐、环境声和动作声，不生成可辨识人声，不要求口型。
- 新视频只上传日常栀夏 v04 输入：`assets/characters/栀夏角色卡高写实CG-v04.png` 与 `assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg`；不得混入敦煌或九歌专属母板。
- 栀夏从第一帧开始真实起舞；持续奔跑、普通走路、衣料摆动、特效或镜头运动不能代替舞蹈。
- 每条只有一个连续空间、一个主要视觉事件和一条摄影机主路径；现代祝福、古诗、动作、环境反馈和音乐高潮表达同一种祝愿。
- 禁止“转给某人”“接住好运”“刷到就是有福气”“转发必上岸”等诱导转发或玄学承诺。
- 三条的第一评价指标是分享率与收藏率；三条均未改善时先检查赠送对象、现代祝福和诗舞同义性，不得直接归因为 AI 技术或继续提高视觉复杂度。
- TTS 与 Seedance 都是产生费用或外部状态的步骤；执行前必须向用户展示预览和调用数量，并取得当次明确确认。
- `assets/audio/`、`episodes/*/assets/video/`、封面图和导出 MP4 按 `.gitignore` 保持本地，不强制加入 Git；用 `assets/inventory.csv`、清单、哈希和 QA 文档记录可追溯性。
- 只暂存和提交本计划明确列出的文件，不带入工作区其他既有修改；提交信息使用中文。

---

## 文件结构

- `operations/yi-wu-yi-yuan/qiancheng-v01.json`：三条文本、出处、分享场景、舞蹈事件和统一硬门槛的单一事实源。
- `scripts/validate_yi_wu_yi_yuan.py`：校验汉字数、禁用话术、出处、三条唯一性和最终字幕时间轴。
- `tests/test_validate_yi_wu_yi_yuan.py`：季级契约与超时、超字数、禁用话术的单元测试。
- `tests/test_yi_wu_yi_yuan_qiancheng_configs.py`：三份 TTS 清单与季级 JSON 的逐字一致性门禁。
- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/`：重新出发单集清单、提示词、字幕计划、发布文案和 QA。
- `episodes/yiwu-yiyuan-qiancheng-02-journey-15s/`：奔赴远方单集清单、提示词、字幕计划、发布文案和 QA。
- `episodes/yiwu-yiyuan-qiancheng-03-persist-15s/`：走出困境单集清单、提示词、字幕计划、发布文案和 QA。
- `scripts/build_yi_wu_yi_yuan_15s_final.sh`：读取单集清单并生成无字幕朗诵版和正式字幕版的通用构建入口。
- `tests/test_yi_wu_yi_yuan_15s_final.sh`：对任一单集验证字数、时长、禁变速、字幕卡和成片媒体规格。
- `assets/audio/yiwu-yiyuan-qiancheng-01-restart-15s-voice-v01/`、`assets/audio/yiwu-yiyuan-qiancheng-02-journey-15s-voice-v01/`、`assets/audio/yiwu-yiyuan-qiancheng-03-persist-15s-voice-v01/`：本地三段 MP3 与生成元数据，不进入 Git。
- `assets/subtitles/yiwu-yiyuan-qiancheng-01-restart-15s/`、`assets/subtitles/yiwu-yiyuan-qiancheng-02-journey-15s/`、`assets/subtitles/yiwu-yiyuan-qiancheng-03-persist-15s/`：本地透明字幕卡。
- 三个单集目录各自的 `assets/video/content-seedance-v01.mp4`：本地 Seedance 原片，不进入 Git。
- `exports/yiwu-yiyuan-qiancheng-01-restart-15s-voiced-v01.mp4` 至 `exports/yiwu-yiyuan-qiancheng-03-persist-15s-subtitled-v01.mp4`：三条本地试听版与正式成片，不进入 Git。
- `assets/inventory.csv`：三条原片、九段人声、六个导出版本与封面的资产登记。
- `operations/performance-data.csv`：发布后的分享、收藏和关注数据。

### 季级 JSON 的固定内容

```json
{
  "series": "yi-wu-yi-yuan",
  "season": "qiancheng-v01",
  "duration_ms": 15000,
  "voice_end_max_ms": 11500,
  "tail_min_ms": 3000,
  "max_hanzi": {"recipient": 10, "blessing": 12, "poem": 14, "total": 34},
  "banned_phrases": ["转给某人", "接住好运", "刷到就是有福气", "转发必上岸"],
  "episodes": [
    {
      "episode": "yiwu-yiyuan-qiancheng-01-restart-15s",
      "recipient": "送给重新出发的你",
      "blessing": "愿你此去有路，所盼有期",
      "poem": "长风破浪会有时，直挂云帆济沧海",
      "attribution": "唐·李白《行路难·其一》",
      "share_scene": "换工作、毕业、重新开始，也可自我收藏",
      "dance_event": "迎风破浪后远方航路打开"
    },
    {
      "episode": "yiwu-yiyuan-qiancheng-02-journey-15s",
      "recipient": "送给奔赴远方的你",
      "blessing": "愿你一路有景，前路有友",
      "poem": "莫愁前路无知己，天下谁人不识君",
      "attribution": "唐·高适《别董大二首·其一》",
      "share_scene": "送朋友、同学、同事及远行者",
      "dance_event": "回望送别后转身走向展开的远路"
    },
    {
      "episode": "yiwu-yiyuan-qiancheng-03-persist-15s",
      "recipient": "送给仍在坚持的你",
      "blessing": "愿你越过此山，得见新路",
      "poem": "山重水复疑无路，柳暗花明又一村",
      "attribution": "宋·陆游《游山西村》",
      "share_scene": "鼓励正在经历困难的人，也可自我收藏",
      "dance_event": "受阻越山后柳色与村路同时显现"
    }
  ]
}
```

### Task 1: 建立季级契约与自动校验器

**Files:**
- Create: `zhixia-feihualing/operations/yi-wu-yi-yuan/qiancheng-v01.json`
- Create: `zhixia-feihualing/scripts/validate_yi_wu_yi_yuan.py`
- Create: `zhixia-feihualing/tests/test_validate_yi_wu_yi_yuan.py`
- Modify: `zhixia-feihualing/docs/production-workflow.md`

**Interfaces:**
- Consumes: 设计真源中的字数、时长、双入口和回退规则。
- Produces: `count_hanzi(text: str) -> int`、`validate_season(path: Path) -> None`、`validate_subtitle_plan(path: Path, duration_ms: int, voice_end_max_ms: int, tail_min_ms: int) -> None` 与 CLI 入口。

- [ ] **Step 1: 写失败测试**

```python
import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEASON_PATH = ROOT / "operations/yi-wu-yi-yuan/qiancheng-v01.json"
VALIDATOR_PATH = ROOT / "scripts/validate_yi_wu_yi_yuan.py"
SPEC = importlib.util.spec_from_file_location("validate_yi_wu_yi_yuan", VALIDATOR_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def valid_season() -> dict:
    return json.loads(SEASON_PATH.read_text(encoding="utf-8"))

def validate_temp(data: dict) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "season.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        module.validate_season(path)

def validate_plan_temp(plan: list[dict]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "subtitle-plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        module.validate_subtitle_plan(path, 15000, 11500, 3000)

class YiWuYiYuanValidationTests(unittest.TestCase):
    def test_counts_only_hanzi(self):
        self.assertEqual(module.count_hanzi("愿你此去有路，所盼有期。"), 10)

    def test_rejects_overlong_recipient(self):
        data = valid_season()
        data["episodes"][0]["recipient"] = "送给每一个正在重新出发的朋友"
        with self.assertRaisesRegex(ValueError, "recipient.*10"):
            validate_temp(data)

    def test_rejects_banned_phrase(self):
        data = valid_season()
        data["episodes"][0]["blessing"] = "接住好运"
        with self.assertRaisesRegex(ValueError, "banned phrase"):
            validate_temp(data)

    def test_rejects_voice_end_after_11500(self):
        plan = [{"id":"01-recipient","start":0.0,"end":2.5},
                {"id":"02-blessing","start":2.7,"end":5.4},
                {"id":"03-poem","start":6.0,"end":11.6}]
        with self.assertRaisesRegex(ValueError, "voice end"):
            validate_plan_temp(plan)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd zhixia-feihualing && python3 -m unittest tests.test_validate_yi_wu_yi_yuan -v`

Expected: FAIL，提示 `validate_yi_wu_yi_yuan` 模块不存在。

- [ ] **Step 3: 写入季级 JSON**

使用本计划“季级 JSON 的固定内容”逐字创建文件；不得添加状态占位词或候选文案。

- [ ] **Step 4: 实现最小校验器**

```python
HANZI = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

def count_hanzi(text: str) -> int:
    return len(HANZI.findall(text))

def validate_subtitle_plan(path: Path, duration_ms: int, voice_end_max_ms: int,
                           tail_min_ms: int) -> None:
    items = json.loads(path.read_text(encoding="utf-8"))
    if [item["id"] for item in items] != ["01-recipient", "02-blessing", "03-poem"]:
        raise ValueError("subtitle ids must be recipient, blessing, poem")
    if any(items[index]["end"] > items[index + 1]["start"] for index in range(2)):
        raise ValueError("subtitle timeline overlaps")
    voice_end_ms = round(float(items[-1]["end"]) * 1000)
    if voice_end_ms > voice_end_max_ms:
        raise ValueError(f"voice end {voice_end_ms} exceeds {voice_end_max_ms}")
    if duration_ms - voice_end_ms < tail_min_ms:
        raise ValueError("tail is shorter than required")
```

`validate_season` 还要验证：三条 slug 唯一且符合小写连字符格式；每条六个字段均为非空字符串；分项与总汉字数不超上限；禁用词不出现在三个朗诵字段中；出处分别包含朝代、作者和篇名；三条诗句、赠送对象与 `dance_event` 互不重复。CLI 固定支持：

```text
python3 scripts/validate_yi_wu_yi_yuan.py --season operations/yi-wu-yi-yuan/qiancheng-v01.json
python3 scripts/validate_yi_wu_yi_yuan.py --subtitle-plan episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan.json
```

CLI 的字幕校验参数固定使用 `duration_ms=15000`、`voice_end_max_ms=11500` 和 `tail_min_ms=3000`；不允许由单集静默放宽。

- [ ] **Step 5: 明确后期 TTS 例外**

在 `docs/production-workflow.md` 的声音规则旁加入：

```markdown
**《一舞一愿》例外：** 该栏目为同时锁定栀夏固定音色、现代祝福逐字内容和 11.500 秒人声截止门槛，先用项目豆包 TTS 生成并测量三段朗诵，再据实设计舞蹈与字幕。Seedance 原片只生成音乐、环境声和动作声，不生成可辨识人声；后期不得对 TTS 使用 `atempo`、截断或机械加速。
```

- [ ] **Step 6: 运行校验与回归**

Run: `cd zhixia-feihualing && python3 -m unittest tests.test_validate_yi_wu_yi_yuan -v && python3 scripts/validate_yi_wu_yi_yuan.py --season operations/yi-wu-yi-yuan/qiancheng-v01.json`

Expected: 全部 PASS，并输出三条均为 32 字。

- [ ] **Step 7: 提交契约与校验器**

```bash
git add zhixia-feihualing/operations/yi-wu-yi-yuan/qiancheng-v01.json \
  zhixia-feihualing/scripts/validate_yi_wu_yi_yuan.py \
  zhixia-feihualing/tests/test_validate_yi_wu_yi_yuan.py \
  zhixia-feihualing/docs/production-workflow.md
git commit -m "建立一舞一愿前程季制作门禁"
```

### Task 2: 创建三条配音契约

**Files:**
- Create: `zhixia-feihualing/tests/test_yi_wu_yi_yuan_qiancheng_configs.py`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/README.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/README.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/README.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/voice-lines.json`

**Interfaces:**
- Consumes: Task 1 的季级 JSON 与项目 `scripts/generate_episode_audio.py`。
- Produces: 三份 `one-poem-story` TTS 清单；每份固定三行 `01-recipient`、`02-blessing`、`03-poem`，供 Task 3、6、7 分别产生三次调用。

- [ ] **Step 1: 写失败测试**

测试加载季级 JSON 和三份 `voice-lines.json`，逐条断言：

```python
self.assertEqual([line["id"] for line in manifest["lines"]],
                 ["01-recipient", "02-blessing", "03-poem"])
self.assertEqual([line["text"].rstrip("。") for line in manifest["lines"]],
                 [entry["recipient"], entry["blessing"], entry["poem"]])
self.assertEqual({line["role"] for line in manifest["lines"]}, {"zhixia"})
self.assertEqual({line["speech_rate"] for line in manifest["lines"]}, {0})
self.assertEqual([line["gap_before_ms"] for line in manifest["lines"]], [0, 180, 400])
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd zhixia-feihualing && python3 -m unittest tests.test_yi_wu_yi_yuan_qiancheng_configs -v`

Expected: FAIL，提示第一份 `voice-lines.json` 不存在。

- [ ] **Step 3: 创建三份 TTS 清单**

三份清单的固定元数据为：

| episode 与 theme_slug | theme | audio_slug |
| --- | --- | --- |
| `yiwu-yiyuan-qiancheng-01-restart-15s` | `一舞一愿前程季重新出发` | `yiwu-yiyuan-qiancheng-01-restart-15s-voice-v01` |
| `yiwu-yiyuan-qiancheng-02-journey-15s` | `一舞一愿前程季奔赴远方` | `yiwu-yiyuan-qiancheng-02-journey-15s-voice-v01` |
| `yiwu-yiyuan-qiancheng-03-persist-15s` | `一舞一愿前程季走出困境` | `yiwu-yiyuan-qiancheng-03-persist-15s-voice-v01` |

每份 `format` 固定为 `one-poem-story`，每份 `lines` 固定包含：

```json
[
  {"id":"01-recipient","role":"zhixia","revision":1,"speech_rate":0,"gap_before_ms":0},
  {"id":"02-blessing","role":"zhixia","revision":1,"speech_rate":0,"gap_before_ms":180},
  {"id":"03-poem","role":"zhixia","revision":1,"speech_rate":0,"gap_before_ms":400}
]
```

三行 `text` 从季级 JSON 精确复制。三行 `context_texts` 分别要求：

- `01-recipient`：年轻清透、真诚克制，像把一句话递给具体的人；不喊栏目名、不用广告腔，只读给定文本。
- `02-blessing`：保持同一距离与声线，语气温和明亮，句内自然连贯；不说教、不甜腻、不拖尾，只读给定文本。
- `03-poem`：由现代话自然提升为清朗说诗，保持正常语速；不念作者篇名、不吟唱、不用朗诵比赛腔，只读给定原文。

三个 README 记录：赠送场景、32 字预算、日常 v04 角色输入、后期 TTS 例外、原片无可辨识人声和 `11.500` 秒截止门槛。

- [ ] **Step 4: 运行清单测试与只读预览**

```bash
cd zhixia-feihualing
python3 -m unittest tests.test_yi_wu_yi_yuan_qiancheng_configs -v
python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-01-restart-15s
python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-02-journey-15s
python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-03-persist-15s
```

Expected: 测试 PASS；每个预览显示 3 句、3 次预计调用且不创建音频。

- [ ] **Step 5: 提交三份配音契约**

```bash
git add zhixia-feihualing/tests/test_yi_wu_yi_yuan_qiancheng_configs.py \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/README.md \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/README.md \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/voice-lines.json \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/README.md \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/voice-lines.json
git commit -m "建立前程季三条配音契约"
```

### Task 3: 生成并测量“重新出发”朗诵

**Files:**
- Local create: `zhixia-feihualing/assets/audio/yiwu-yiyuan-qiancheng-01-restart-15s-voice-v01/*.mp3`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-v01.json`

**Interfaces:**
- Consumes: Task 2 的第一份清单和用户对 3 次豆包 TTS 调用的明确确认。
- Produces: 三段正常语速 MP3、真实时间轴、题署 `唐·李白《行路难·其一》`，供 Task 4 编舞和 Task 5 合成。

- [ ] **Step 1: 再次展示付费预览并取得确认**

Run: `cd zhixia-feihualing && python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-01-restart-15s`

Expected: 显示 3 次调用。暂停执行，取得用户对本次 3 次调用的明确确认。

- [ ] **Step 2: 生成三段朗诵**

Run: `cd zhixia-feihualing && print 'GENERATE yiwu-yiyuan-qiancheng-01-restart-15s' | python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-01-restart-15s --generate`

Expected: 三个 24 kHz 单声道 MP3 和元数据生成完成；日志不包含 API Key。

- [ ] **Step 3: 测量真实有效时长**

对三段音频统一使用双向头尾静音裁切，仅输出到临时 WAV 测量：

```text
silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,
areverse,
silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,
areverse
```

用 `ffprobe` 记录每段裁切前后时长与 SHA-256 到 `audio-timing-v01.json`。按 `0 ms`、上一句结束后 `180 ms`、第二句结束后 `400 ms` 排布；第三句结束必须不晚于 `11500 ms`。

- [ ] **Step 4: 生成正式字幕计划并校验**

`subtitle-plan.json` 固定三项：现代两句 `kind=modern`，诗句 `kind=poem` 并带题署；`start`、`end` 使用 Step 3 的真实毫秒值除以 1000，不能使用预估时间。

Run: `cd zhixia-feihualing && python3 scripts/validate_yi_wu_yi_yuan.py --subtitle-plan episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan.json`

Expected: PASS，末句不晚于 11.500 秒，余韵不少于 3.000 秒。失败时先缩短现代祝福并将对应 `revision` 加一，只重新生成超窗句；禁止加速。

- [ ] **Step 5: 提交可追溯时间轴**

```bash
git add zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan.json \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-v01.json
git commit -m "锁定重新出发朗诵时间轴"
```

### Task 4: 设计并生成“重新出发”舞蹈原片

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md`
- Local create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/assets/video/content-seedance-v01.mp4`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/qa-video-v01.md`
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: Task 3 的真实三段时间轴、日常 v04 两张角色输入、`docs/zhixia-poetry-dance-composer.md` 和舞蹈去重台账最近五行。
- Produces: 一个十五秒无可辨识人声、含音乐与环境声的连续诗舞原片。

- [ ] **Step 1: 写舞蹈设计卡与提示词**

提示词必须把同一事件写成：栀夏在风浪将起的湿润石岸第一帧即以换重和大幅身体轨迹起舞；现代祝福阶段由迎风蓄力进入向前的圆场连接；古诗阶段完成一次完整旋转、一次清楚高低层次变化和一次由身体动作触发的浪线打开；高潮时云层裂开，远方唯一白帆与水面金色航路显现。摄影机只沿侧前方跟随并在破浪高潮短促扩大景别，不环绕到背后。栀夏不持道具、不持续奔跑，服装与脸保持日常 v04，原片不生成字幕、标题或可辨识人声。

- [ ] **Step 2: 运行提示词自检**

逐项确认：第一帧已起舞、非跑步、一个事件、一个主要特效、一个白帆、两次以内镜头反应、人物全身与脸在高潮可见、音乐转折对齐真实朗诵节点、末尾 3 秒继续跳舞。

- [ ] **Step 3: 展示完整提示词并取得一次 Seedance 生成确认**

向用户展示将上传的两张 v04 文件、完整可复制提示词和预计一次视频生成。未获确认不得操作外部生成页面。

- [ ] **Step 4: 生成、下载并登记原片**

将下载文件保存为固定路径，用 `ffprobe` 验证约 15 秒、竖屏、24 fps、有音频；记录 SHA-256、生成日期、输入文件和平台任务标识到 `qa-video-v01.md`。原片有可辨识人声、人物漂移、持续奔跑、核心动作遮脸或结尾提前停舞时标记为 rejected，不进入 Task 5。

- [ ] **Step 5: 提交提示词与原片 QA**

```bash
git add zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/qa-video-v01.md
git add -p zhixia-feihualing/operations/dance-design-history.csv
git diff --cached --name-only
git commit -m "完成重新出发诗舞原片设计"
```

### Task 5: 建立通用合成入口并完成首条成片

**Files:**
- Create: `zhixia-feihualing/scripts/build_yi_wu_yi_yuan_15s_final.sh`
- Create: `zhixia-feihualing/tests/test_yi_wu_yi_yuan_15s_final.sh`
- Reuse: `zhixia-feihualing/scripts/render_story_subtitle_cards.swift`
- Local create: `zhixia-feihualing/assets/subtitles/yiwu-yiyuan-qiancheng-01-restart-15s/*.png`
- Local create: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-15s-voiced-v01.mp4`
- Local create: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-15s-subtitled-v01.mp4`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/qa-final-v01.md`

**Interfaces:**
- Consumes: `--episode SLUG` 参数，单集 `voice-lines.json`、`subtitle-plan.json`、三段 MP3 和 Seedance 原片；`SLUG` 必须是季级 JSON 中三个完整 episode 值之一。
- Produces: 1080×1920、24 fps、H.264/AAC 的无字幕朗诵版与正式字幕版；两版音轨一致。

- [ ] **Step 1: 写失败门禁**

测试固定调用：

```bash
zsh tests/test_yi_wu_yi_yuan_15s_final.sh yiwu-yiyuan-qiancheng-01-restart-15s
```

测试先运行 Python 校验器，再断言构建脚本存在且不含 `atempo`；三张字幕卡存在；两个输出可解码；视频为 1080×1920、24 fps、15.0—15.2 秒，音频为 AAC、48 kHz、双声道；两个输出提取的 AAC 音轨 SHA-256 一致。

- [ ] **Step 2: 运行测试并确认失败**

Expected: FAIL，提示缺少通用构建脚本，而不是 shell 语法错误。

- [ ] **Step 3: 实现通用构建脚本**

脚本从 `voice-lines.json` 读取 `audio_slug`，从 `subtitle-plan.json` 读取三项真实 `start` 和 `end`。三段人声只裁头尾静音、`asetpts=PTS-STARTPTS`、转为 48 kHz 双声道并按各自 `start` 使用 `adelay`；不得使用 `atempo`、音高改变或有效人声截断。

使用以下人声处理链：

```text
highpass=f=90,
equalizer=f=2600:t=q:w=1.0:g=1.5,
acompressor=threshold=0.08:ratio=2:attack=10:release=120:makeup=1.25
```

三段先 `amix normalize=0` 为 `voice_mix`，原片音乐与环境声作为 `bed`；用温和侧链让朗诵清楚，人声结束后自然恢复原片音乐，最终限制真峰值：

```text
[bed][voice_mix]sidechaincompress=threshold=0.03:ratio=3:attack=20:release=220[ducked];
[ducked][voice_mix]amix=inputs=2:duration=first:normalize=0,
alimiter=limit=0.891251:attack=5:release=80:level=false[aout]
```

字幕渲染继续使用 `render_story_subtitle_cards.swift`：两句 `kind=modern` 为水平字幕，诗句 `kind=poem` 为竖排并带题署。字幕启用区间从 JSON 读取，不在脚本硬编码预估时间。无字幕版先完成统一音轨；字幕版复制其音轨，只重新编码带字幕画面。

- [ ] **Step 4: 构建并运行完整门禁**

```bash
chmod +x zhixia-feihualing/scripts/build_yi_wu_yi_yuan_15s_final.sh \
  zhixia-feihualing/tests/test_yi_wu_yi_yuan_15s_final.sh
cd zhixia-feihualing
zsh scripts/build_yi_wu_yi_yuan_15s_final.sh --episode yiwu-yiyuan-qiancheng-01-restart-15s
zsh tests/test_yi_wu_yi_yuan_15s_final.sh yiwu-yiyuan-qiancheng-01-restart-15s
```

Expected: PASS，末句后至少 3.000 秒无人声余韵，两版音轨哈希一致。

- [ ] **Step 5: 做视听抽帧与试听 QA**

在 0.8、2.5、5.8、8.5、11.3、13.8 秒抽帧；检查现代字幕在前两秒出现赠送对象关键词、诗句题署准确、字幕不遮脸和主要舞姿。完整试听确认无赶字、无广告腔、音乐在人声后自然恢复、舞蹈高潮与“长风破浪”“云帆济沧海”一致，并把媒体参数、响度、峰值和 PASS/FAIL 写入 `qa-final-v01.md`。

- [ ] **Step 6: 提交通用构建入口与首条 QA**

```bash
git add zhixia-feihualing/scripts/build_yi_wu_yi_yuan_15s_final.sh \
  zhixia-feihualing/tests/test_yi_wu_yi_yuan_15s_final.sh \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/qa-final-v01.md
git commit -m "完成一舞一愿首条朗诵字幕成片"
```

### Task 6: 完成“奔赴远方”朗诵、舞蹈与成片

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/audio-timing-v01.json`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/prompt.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/qa-video-v01.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s/qa-final-v01.md`
- Local create: `assets/audio/yiwu-yiyuan-qiancheng-02-journey-15s-voice-v01/`、`assets/subtitles/yiwu-yiyuan-qiancheng-02-journey-15s/`、`episodes/yiwu-yiyuan-qiancheng-02-journey-15s/assets/video/content-seedance-v01.mp4`、`exports/yiwu-yiyuan-qiancheng-02-journey-15s-voiced-v01.mp4`、`exports/yiwu-yiyuan-qiancheng-02-journey-15s-subtitled-v01.mp4`。

**Interfaces:**
- Consumes: Task 2 第二份配音清单和 Task 5 通用构建入口；在首条成片通过用户验收后才开始。
- Produces: “送给奔赴远方的你”正式成片和完整时间、视频、成片 QA。

- [ ] **Step 1: 预览并经用户确认后产生 3 次 TTS 调用**

```bash
cd zhixia-feihualing
python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-02-journey-15s
print 'GENERATE yiwu-yiyuan-qiancheng-02-journey-15s' | python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-02-journey-15s --generate
```

只有在预览后获得明确确认才运行第二条命令。

- [ ] **Step 2: 测时并生成字幕计划**

三段音频都使用 `silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse` 输出临时 WAV，写入裁切前后真实毫秒与 SHA-256；按 `0 ms`、上一句结束后 `180 ms`、第二句结束后 `400 ms` 排布。现代两句水平字幕，诗句题署固定为 `唐·高适《别董大二首·其一》`。运行 `validate_yi_wu_yi_yuan.py --subtitle-plan`，确保人声结束不晚于 11.500 秒。

- [ ] **Step 3: 写独立舞蹈提示词并取得 Seedance 确认**

本条唯一事件固定为：栀夏在开阔古道与风动长草间第一帧即起舞，现代祝福阶段完成一次克制回望，古诗阶段明确转身向远方并以连续旋转打开道路；远景只出现逐渐显露的山口与同行飞鸟，不复用第一条的海浪、白帆和水面金路。摄影机侧后方短暂跟随但不长期拍背，高潮恢复侧前全身构图。展示 v04 输入与完整提示词并取得一次生成确认。

- [ ] **Step 4: 生成原片并调用通用构建入口**

保存、探测、哈希和人工验收原片后运行：

```bash
cd zhixia-feihualing
zsh scripts/build_yi_wu_yi_yuan_15s_final.sh --episode yiwu-yiyuan-qiancheng-02-journey-15s
zsh tests/test_yi_wu_yi_yuan_15s_final.sh yiwu-yiyuan-qiancheng-02-journey-15s
```

Expected: PASS；现代话、送别回望、转身远行和“前路无知己”形成同一关系，结尾仍有至少 3 秒舞蹈余韵。

- [ ] **Step 5: 提交第二条的可追溯文本资产**

```bash
git add zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s
git add -p zhixia-feihualing/operations/dance-design-history.csv
git diff --cached --name-only
git commit -m "完成奔赴远方祝福诗舞"
```

提交前用 `git diff --cached --name-only` 排除 `assets/video/`、音频与 MP4。

### Task 7: 完成“走出困境”朗诵、舞蹈与成片

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/subtitle-plan.json`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/audio-timing-v01.json`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/prompt.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/qa-video-v01.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s/qa-final-v01.md`
- Local create: `assets/audio/yiwu-yiyuan-qiancheng-03-persist-15s-voice-v01/`、`assets/subtitles/yiwu-yiyuan-qiancheng-03-persist-15s/`、`episodes/yiwu-yiyuan-qiancheng-03-persist-15s/assets/video/content-seedance-v01.mp4`、`exports/yiwu-yiyuan-qiancheng-03-persist-15s-voiced-v01.mp4`、`exports/yiwu-yiyuan-qiancheng-03-persist-15s-subtitled-v01.mp4`。

**Interfaces:**
- Consumes: Task 2 第三份配音清单和 Task 5 通用构建入口；在第二条成片通过用户验收后才开始。
- Produces: “送给仍在坚持的你”正式成片和完整时间、视频、成片 QA。

- [ ] **Step 1: 预览并经用户确认后产生 3 次 TTS 调用**

```bash
cd zhixia-feihualing
python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-03-persist-15s
print 'GENERATE yiwu-yiyuan-qiancheng-03-persist-15s' | python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-03-persist-15s --generate
```

只有在预览后获得明确确认才运行第二条命令。

- [ ] **Step 2: 测时并生成字幕计划**

三段音频都使用 `silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse` 输出临时 WAV，记录裁切前后真实毫秒与 SHA-256；按 `0 ms`、上一句结束后 `180 ms`、第二句结束后 `400 ms` 排布。现代两句水平字幕，诗句题署固定为 `宋·陆游《游山西村》`。校验人声结束不晚于 11.500 秒，不通过则只缩短现代祝福并递增 revision。

- [ ] **Step 3: 写独立舞蹈提示词并取得 Seedance 确认**

本条唯一事件固定为：栀夏在山径被巨石与昏暗林影阻断处第一帧即以低重心拧倾起舞，现代祝福阶段沿原地小范围完成受阻和换向，古诗阶段用一次由低到高的翻身与旋转越过视线障碍；柳枝、暖光与远处村路只在高潮同时显现。不得持续爬山、跑台阶，不复用第一条的风浪白帆或第二条的古道飞鸟。展示 v04 输入与完整提示词并取得一次生成确认。

- [ ] **Step 4: 生成原片并调用通用构建入口**

```bash
cd zhixia-feihualing
zsh scripts/build_yi_wu_yi_yuan_15s_final.sh --episode yiwu-yiyuan-qiancheng-03-persist-15s
zsh tests/test_yi_wu_yi_yuan_15s_final.sh yiwu-yiyuan-qiancheng-03-persist-15s
```

Expected: PASS；受阻、越过与新路显现构成同一事件，人物不跑步，末句后至少保留 3 秒舞蹈与音乐收束。

- [ ] **Step 5: 提交第三条的可追溯文本资产**

```bash
git add zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s
git add -p zhixia-feihualing/operations/dance-design-history.csv
git diff --cached --name-only
git commit -m "完成走出困境祝福诗舞"
```

提交前用 `git diff --cached --name-only` 排除本地媒体。

### Task 8: 发布准备、资产登记与三条验证闭环

**Files:**
- Create: `zhixia-feihualing/operations/yi-wu-yi-yuan/qiancheng-v01-publishing.md`
- Create: each episode's `wechat-channels-copy.md`
- Modify: each episode's `README.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify after publication: `zhixia-feihualing/operations/performance-data.csv`

**Interfaces:**
- Consumes: 三条正式字幕成片、各自 QA、季级 JSON 与账号实际发布数据。
- Produces: 三条可发布文案、可追溯资产登记和决定是否扩展《前程》的数据结论。

- [ ] **Step 1: 写三条发布文案**

三条标题分别固定为：

```text
一舞一愿｜愿你此去有路
一舞一愿｜愿你一路有景
一舞一愿｜愿你越过此山
```

正文不重复整段朗诵，不要求转发，只补充赠送场景、诗句出处和 `原创虚拟角色｜AI辅助制作`。每条标签不超过六个，以 `一舞一愿`、诗名、国风舞蹈、古诗词和对应生活场景为主。

- [ ] **Step 2: 登记本地媒体与版本**

在 `assets/inventory.csv` 为每条记录：Seedance 原片、三段 voice、voiced preview、final subtitled；填写实际路径、状态、生成方式、来源、时长、分辨率、帧率、音频规格和 SHA-256。失败版本只在 QA 中记录，不登记为 final。

- [ ] **Step 3: 运行发布前总门禁**

```bash
cd zhixia-feihualing
python3 scripts/validate_yi_wu_yi_yuan.py --season operations/yi-wu-yi-yuan/qiancheng-v01.json
for episode in \
  yiwu-yiyuan-qiancheng-01-restart-15s \
  yiwu-yiyuan-qiancheng-02-journey-15s \
  yiwu-yiyuan-qiancheng-03-persist-15s; do
  zsh tests/test_yi_wu_yi_yuan_15s_final.sh "$episode"
done
git diff --check -- operations/yi-wu-yi-yuan episodes assets/inventory.csv
```

Expected: 季级校验和三条成片门禁全部 PASS，无 whitespace error。

- [ ] **Step 4: 按同一测试条件发布并记录数据**

三条保持 15 秒、相同封面层级和相近发布时间条件，不连续批量发布；在 `performance-data.csv` 填写 `views`、`shares`、`favorites`、`comments`、`new_followers`，并在 `notes` 标记 `yi-wu-yi-yuan-qiancheng-v01` 与具体赠送场景。

- [ ] **Step 5: 计算并记录扩展结论**

在 `qiancheng-v01-publishing.md` 记录每千次播放分享数与收藏数：

```text
shares_per_1000 = shares / views * 1000
favorites_per_1000 = favorites / views * 1000
```

与账号同期中位水平比较。某一场景明显更高时，只沿该场景扩展三至五条；三条均未改善时，先检查前两秒对象关键词、现代祝福可转送性和诗舞同义性，不增加视觉复杂度。

- [ ] **Step 6: 提交发布准备与数据记录**

```bash
git add zhixia-feihualing/operations/yi-wu-yi-yuan/qiancheng-v01-publishing.md \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-02-journey-15s \
  zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-03-persist-15s
git add -p zhixia-feihualing/operations/performance-data.csv
git add -p zhixia-feihualing/assets/inventory.csv
git diff --cached --name-only
git commit -m "完成前程季发布验证闭环"
```

提交前确认暂存区没有 `.env`、音频、原始视频、导出 MP4、持仓或其他项目文件。
