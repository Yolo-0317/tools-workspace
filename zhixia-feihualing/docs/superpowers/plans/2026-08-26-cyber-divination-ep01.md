# 《栀夏赛博起卦》第一集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 制作一条约 15 秒、9:16 的《栀夏赛博起卦》第一集《最后一块桂花糕》，用“山雷颐”卦象完成栀夏严肃断卦、阿砚被八只空盘拆穿的日常喜剧。

**Architecture:** 用户先提供并确认 AI 卦盘道具卡，项目将其归档为唯一道具母板；随后建立单集台词、字幕和场景资产，使用角色母板与卦盘母板生成无可辨识人声的 15 秒原始视频。角色对白由既有豆包 TTS 流程生成，精确卦名、卦辞、六爻与免责声明由本地透明字幕卡叠加，最终通过 FFmpeg 合成并执行规格、文本、音频与关键帧质检。

**Tech Stack:** Markdown、JSON、zsh、Python 3、Swift/AppKit/CoreText、FFmpeg/ffprobe、豆包 TTS、Seedance、PNG 角色与道具参考图

## Global Constraints

- 栏目名固定为 `栀夏赛博起卦`；单集时长约 15 秒；画幅固定为 9:16 竖屏。
- 栀夏保持冷静严肃、绝不笑场；阿砚负责提问、嘴馋和反转后的心虚反应。
- 栀夏身份参考固定为 `assets/characters/栀夏角色卡电影半写实-v02.png`；阿砚身份参考固定为 `assets/characters/阿砚角色卡电影半写实-v01.png`。
- AI 卦盘由用户独立设计；通过确认后归档到 `assets/props/ai-divination-disk-v01/master.png`，后续不得在场景提示词中重新设计外观。
- 卦盘道具卡必须表达“未起卦”“六爻生成中”“卦象揭示”三个状态；单集只替换卦名、上下卦、六爻阴阳线与原文。
- 首集固定使用第二十七卦颐卦、常用卦名“山雷颐”和原文“颐，贞吉。观颐，自求口实。”。
- 最终片从证据反转开始持续显示“传统文化趣味演绎，请勿作为现实决策依据”，不能只闪现一帧。
- Seedance 只生成画面、背景音乐和环境声，不生成可辨识人声、对白、卦名或卦辞。
- 任何豆包 TTS 付费调用前必须先运行免费预览，并再次取得用户确认。
- 不覆盖既有角色、音频、视频或字幕资产；所有新增资产使用版本化文件名并登记 `assets/inventory.csv`。
- 所有用户可见文字、UI 与汇报禁止 emoji。

---

### Task 1: 归档并验收用户提供的 AI 卦盘道具卡

**Files:**
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/README.md`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/qa-checklist.md`
- User provides: `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Create: `zhixia-feihualing/tests/test_cyber_divination_prop.sh`

**Interfaces:**
- Consumes: 用户确认的单张 AI 卦盘道具卡。
- Produces: 状态为 `approved` 的 `ai-divination-disk-v01` 道具母板，供全部场景卡与视频提示词引用。

- [ ] **Step 1: 写失败测试**

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
prop="$project_dir/assets/props/ai-divination-disk-v01/master.png"
inventory="$project_dir/assets/inventory.csv"

test -s "$prop"
dimensions="$(sips -g pixelWidth -g pixelHeight "$prop" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w" "h}')"
read width height <<< "$dimensions"
awk -v w="$width" -v h="$height" 'BEGIN { exit !(w >= 720 && h >= 1280 && w / h >= 0.55 && w / h <= 0.57) }'
ffmpeg -v error -i "$prop" -frames:v 1 -f null -
rg -q '^ai-divination-disk-v01,prop,AI卦盘,identity-master,assets/props/ai-divination-disk-v01/master.png,approved,' "$inventory"
echo "cyber divination prop: PASS"
```

- [ ] **Step 2: 运行测试并确认因母板尚未归档而失败**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_prop.sh`

Expected: FAIL at `test -s` until the user-approved `master.png` is present.

- [ ] **Step 3: 写清道具身份与人工验收项**

在 `README.md` 固定外框轮廓、材质、浅青/月白/暖金/少量朱砂配色、悬浮层级、三种状态和可变信息区；在 `qa-checklist.md` 逐项检查三个状态属于同一件道具、六爻自下而上生成、阴爻与阳爻可辨、文字区无遮挡、透明或单色背景便于引用，以及没有蓝紫法阵、粒子漩涡和机械改造角色。

- [ ] **Step 4: 等待用户放入并确认道具卡**

将用户确认的原图原样保存为 `master.png`；不裁切、不重绘、不自行改变颜色。只有用户明确说“道具卡确认”后，才把清单状态登记为：

```csv
ai-divination-disk-v01,prop,AI卦盘,identity-master,assets/props/ai-divination-disk-v01/master.png,approved,user-provided design,user-owned original asset,栀夏赛博起卦唯一卦盘母板；含未起卦、六爻生成中、卦象揭示三个状态
```

- [ ] **Step 5: 运行验收并提交**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_prop.sh`

Expected: `cyber divination prop: PASS`

```bash
git add zhixia-feihualing/assets/props/ai-divination-disk-v01 zhixia-feihualing/assets/inventory.csv zhixia-feihualing/tests/test_cyber_divination_prop.sh
git commit -m "归档赛博卦盘道具母板"
```

### Task 2: 建立第一集台词、字幕与资产契约

**Files:**
- Modify: `zhixia-feihualing/episodes/cyber-divination-ep01/README.md`
- Modify: `zhixia-feihualing/episodes/cyber-divination-ep01/voice-lines.json`
- Modify: `zhixia-feihualing/episodes/cyber-divination-ep01/subtitle-plan.json`
- Modify: `zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py`

**Interfaces:**
- Consumes: `config/voices.json` 中的 `ayan` 与 `zhixia` 固定音色。
- Produces: `EpisodeManifest` 可读取的六段语音，以及字幕渲染器可读取的八张透明卡清单。

- [ ] **Step 1: 把测试期望更新为已确认的精简对白**

```python
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from zhixia_tts_manifest import load_episode_manifest, load_voice_config


class CyberDivinationEpisodeManifestTests(unittest.TestCase):
  def test_builds_the_fixed_timeline(self):
    voices = load_voice_config(ROOT / "config" / "voices.json")
    manifest = load_episode_manifest(
        ROOT / "episodes/cyber-divination-ep01/voice-lines.json", voices
    )
    self.assertEqual(manifest.episode, "cyber-divination-ep01")
    self.assertEqual([(line.role, line.start_ms) for line in manifest.lines], [
        ("ayan", 0), ("zhixia", 2200), ("zhixia", 3700),
        ("zhixia", 4900), ("ayan", 8500), ("zhixia", 10100),
    ])
    cards = json.loads((ROOT / "episodes/cyber-divination-ep01/subtitle-plan.json").read_text())
    self.assertEqual([item["kind"] for item in cards], [
        "dialogue", "dialogue", "hexagram", "dialogue",
        "dialogue", "dialogue", "disclaimer", "title",
    ])
    self.assertEqual(cards[2]["text"], "山雷颐")
    self.assertEqual(cards[2]["secondary"], "颐，贞吉。观颐，自求口实。")
    self.assertEqual(cards[6]["text"], "传统文化趣味演绎，请勿作为现实决策依据")
```

- [ ] **Step 2: 运行测试并确认旧对白时间轴被拒绝**

Run: `python3 zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py -v`

Expected: FAIL because the existing manifest still uses 2500、4200、6800、9800、11300 毫秒和旧对白。

- [ ] **Step 3: 更新固定台词清单**

```json
{
  "episode": "cyber-divination-ep01",
  "format": "one-poem-story",
  "theme": "山雷颐",
  "theme_slug": "cyber-divination-ep01",
  "audio_slug": "cyber-divination-ep01",
  "lines": [
    {"id": "01-ayan-question", "role": "ayan", "text": "最后一块，能吃吗？", "start_ms": 0},
    {"id": "02-zhixia-cast", "role": "zhixia", "text": "起卦。", "start_ms": 2200},
    {"id": "03-system-hexagram", "role": "zhixia", "text": "山雷颐。", "start_ms": 3700},
    {"id": "04-zhixia-reading", "role": "zhixia", "text": "颐，贞吉。观颐，自求口实。", "start_ms": 4900},
    {"id": "05-ayan-hope", "role": "ayan", "text": "卦说能吃？", "start_ms": 8500},
    {"id": "06-zhixia-reveal", "role": "zhixia", "text": "先数数空盘。", "start_ms": 10100}
  ]
}
```

`03-system-hexagram` 复用栀夏音色生成干净源音，最终混音时只对这一句增加轻微高通、短回声与窄化处理，使它成为卦盘播报而不新增第三种付费音色。

- [ ] **Step 4: 更新八项字幕清单与单集说明**

```json
[
  {"id": "01-ayan-question", "kind": "dialogue", "text": "最后一块，能吃吗？", "attribution": null},
  {"id": "02-zhixia-cast", "kind": "dialogue", "text": "起卦。", "attribution": null},
  {"id": "03-system-hexagram", "kind": "hexagram", "text": "山雷颐", "secondary": "颐，贞吉。观颐，自求口实。", "attribution": "《周易·颐》"},
  {"id": "04-zhixia-reading", "kind": "dialogue", "text": "颐，贞吉。观颐，自求口实。", "attribution": null},
  {"id": "05-ayan-hope", "kind": "dialogue", "text": "卦说能吃？", "attribution": null},
  {"id": "06-zhixia-reveal", "kind": "dialogue", "text": "先数数空盘。", "attribution": null},
  {"id": "07-disclaimer", "kind": "disclaimer", "text": "传统文化趣味演绎，请勿作为现实决策依据", "attribution": null},
  {"id": "08-series-title", "kind": "title", "text": "栀夏赛博起卦", "attribution": null}
]
```

`README.md` 记录 0.0、2.2、3.7、4.9、8.5、10.1、12.1、14.6 秒节点、四个场景卡目标、角色参考和道具参考路径。

- [ ] **Step 5: 运行测试、免费预览 TTS 计划并提交**

Run: `python3 zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py -v`

Expected: `Ran 2 tests` and `OK`

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode cyber-divination-ep01`

Expected: exit 0，显示待生成 6 句、预计 6 次调用，并明确“当前为预览模式，未调用语音接口”。

```bash
git add zhixia-feihualing/episodes/cyber-divination-ep01 zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py
git commit -m "建立赛博起卦第一集清单"
```

### Task 3: 建立独立的赛博起卦透明卡渲染器

**Files:**
- Create: `zhixia-feihualing/scripts/render_cyber_divination_cards.swift`
- Create: `zhixia-feihualing/tests/test_cyber_divination_cards.sh`
- Test fixture: `zhixia-feihualing/episodes/cyber-divination-ep01/subtitle-plan.json`

**Interfaces:**
- Consumes: `kind` 为 `dialogue`、`hexagram`、`disclaimer` 或 `title` 的 JSON 项；`hexagram` 额外读取 `secondary` 与 `attribution`。
- Produces: 每项一张 720×1280 RGBA 透明 PNG，不修改或依赖尚未提交的共享故事字幕渲染器。
- Defines: `drawHexagram(title: String, quote: String)`、`drawDisclaimer(_ text: String)`、`drawSeriesTitle(_ text: String)`；这些函数只向当前 720×1280 透明画布绘制，不读写文件。

- [ ] **Step 1: 写失败测试**

创建独立测试，检查八张 PNG 均为 720×1280；再用 FFmpeg 的 `alphaextract,signalstats` 验证：`dialogue` 底部区域、`hexagram` 中央区域、`disclaimer` 底部安全区和 `title` 上部标题区均有像素。

- [ ] **Step 2: 运行回归测试并确认新类型尚未实现**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_cards.sh`

Expected: FAIL because `render_cyber_divination_cards.swift` does not exist.

- [ ] **Step 3: 最小扩展数据结构与分派**

```swift
struct CyberCard: Decodable {
    let id: String
    let kind: String
    let text: String
    let attribution: String?
    let secondary: String?
}

switch card.kind {
case "dialogue": drawDialogue(card.text)
case "hexagram": drawHexagram(title: card.text, quote: card.secondary ?? "")
case "disclaimer": drawDisclaimer(card.text)
case "title": drawSeriesTitle(card.text)
default: throw RenderError.unknownKind(card.kind)
}
```

`drawDialogue` 延续既有底部行楷对白；`drawHexagram` 在卦盘文字安全区绘制“山雷颐”、较小号卦辞与《周易·颐》出处；`drawDisclaimer` 在底部安全区使用克制的小号楷体；`drawSeriesTitle` 在上部安全区绘制“栀夏赛博起卦”。

`drawHexagram` 同时用矢量线绘制颐卦六爻，固定为从画面顶部到底部 `[阳、阴、阴、阴、阴、阳]`，等价于从下往上 `[阳、阴、阴、阴、阴、阳]`；阳爻是一条完整横线，阴爻是左右两段且中央留白。六爻图形由本地渲染保证准确，原始视频只提供卦盘框体和光效，不承担卦象文字与爻线正确性。

- [ ] **Step 4: 运行全部字幕卡测试并提交**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_cards.sh`

Expected: `cyber divination cards: PASS`

```bash
git add zhixia-feihualing/scripts/render_cyber_divination_cards.swift zhixia-feihualing/tests/test_cyber_divination_cards.sh zhixia-feihualing/episodes/cyber-divination-ep01/subtitle-plan.json
git commit -m "支持赛博起卦字幕卡"
```

### Task 4: 制作并确认四张场景卡

**Files:**
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/scene-card-prompts.md`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards/01-question-medium.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards/02-casting-close.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards/03-reading-reaction.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards/04-empty-plates-reveal.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards/qa-checklist.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 1 的卦盘母板、栀夏 v02 身份卡、阿砚 v01 身份卡与全身比例卡。
- Produces: 四张用户确认的 941×1672 场景卡，供 15 秒视频生成绑定构图和角色身份。

- [ ] **Step 1: 确认道具门槛通过**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_prop.sh`

Expected: `cyber divination prop: PASS`。若失败，停止本任务，不生成替代卦盘。

- [ ] **Step 2: 写四张场景卡的完整提示词**

四张卡共同前缀固定为：电影级半写实东方幻想、9:16、明亮低饱和书斋、浅暖木案、象牙白古籍、柔和自然光；栀夏与阿砚严格绑定 approved 角色卡；AI 卦盘严格绑定 `master.png`，只改变状态，不改造外观；不生成可辨识中文、Logo、水印、蓝紫法阵或多余角色。

四张卡分别锁定：

1. 双人中近景，阿砚双爪搭案盯着唯一一块桂花糕，栀夏侧坐且神情平静。
2. 古籍与栀夏指尖近景，卦盘处于六爻生成中，保留中央文字安全区。
3. 双人中近景，卦盘进入揭示状态，栀夏平静看阿砚，阿砚耳朵竖起、眼睛发亮。
4. 镜头略向桌下俯移，八只空盘整齐叠放，案上仍只有一块桂花糕；阿砚收爪垂耳，栀夏只以视线指向证据。

- [ ] **Step 3: 生成、逐张质检并等待用户确认**

使用图片生成时一次只制作一张场景卡；每张卡检查同一个栀夏、同一个阿砚、严格四足、唯一墨尾、唯一桂花糕，以及卦盘外框与母板一致。卡 4 必须恰好八只空盘，不能出现九只、盘中残糕或第二块糕点。

- [ ] **Step 4: 归档已确认场景卡并提交**

在 `assets/inventory.csv` 新增四条 `keyframe` 记录，状态使用 `approved`，来源如实记录为实际生成工具，版权说明使用 `original AI-assisted asset`。

```bash
git add zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards zhixia-feihualing/episodes/cyber-divination-ep01/scene-card-prompts.md zhixia-feihualing/assets/inventory.csv
git commit -m "归档赛博起卦第一集场景卡"
```

### Task 5: 生成并验收 15 秒无声对白原片

**Files:**
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/video-prompt.md`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/video/content-raw-v01.mp4`
- Create: `zhixia-feihualing/tests/test_cyber_divination_ep01_assets.sh`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 四张 approved 场景卡、角色母板和卦盘母板。
- Produces: 720×1280、24fps、15.0—15.2 秒、含音乐与环境声但无可辨识人声的原片。

- [ ] **Step 1: 写失败资产测试**

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
video="$project_dir/episodes/cyber-divination-ep01/assets/video/content-raw-v01.mp4"
test -s "$video"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$video")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$video")" = "24/1"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
ffmpeg -v error -i "$video" -f null -
echo "cyber divination raw assets: PASS (${duration}s)"
```

- [ ] **Step 2: 运行测试并确认原片缺失**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_assets.sh`

Expected: FAIL at `test -s`.

- [ ] **Step 3: 使用固定时间轴生成原片**

在 `video-prompt.md` 写入：0.0—2.2 秒阿砚提问表演；2.2—3.7 秒栀夏轻触古籍；3.7—4.9 秒卦盘框体进入“生成中”状态并依次亮起六个空白爻位；4.9—8.5 秒栀夏平静读卦辞；8.5—10.1 秒阿砚期待反问；10.1—12.1 秒栀夏垂眼拆穿并带动镜头下移；12.1—14.6 秒揭示八只空盘，阿砚收爪垂耳；14.6—15.0 秒保留反应与落版。要求三次以内的克制切镜、角色脸部稳定、无口型特写、无可辨识人声、卦名、卦辞或具体爻线；卦盘中央保留后期透明卡安全区，精确六爻与文字由 Task 3 本地渲染。

- [ ] **Step 4: 规格与关键帧人工验收**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_assets.sh`

Expected: `cyber divination raw assets: PASS`

抽取 0.5、2.8、4.2、6.5、9.2、11.2、13.0、14.7 秒关键帧，确认角色身份连续、六爻按自下而上方向出现、阿砚无多肢多尾、卡 4 反转可读且空盘数量为八。用户确认原片后再登记为 `available`。

- [ ] **Step 5: 提交原片资产记录**

```bash
git add zhixia-feihualing/episodes/cyber-divination-ep01/video-prompt.md zhixia-feihualing/episodes/cyber-divination-ep01/assets/video/content-raw-v01.mp4 zhixia-feihualing/tests/test_cyber_divination_ep01_assets.sh zhixia-feihualing/assets/inventory.csv
git commit -m "归档赛博起卦第一集原片"
```

### Task 6: 经确认生成配音并实现最终合成

**Files:**
- Create after approval: `zhixia-feihualing/assets/audio/cyber-divination-ep01/*.mp3`
- Create after approval: `zhixia-feihualing/assets/audio/cyber-divination-ep01/audio-metadata.json`
- Create: `zhixia-feihualing/scripts/build_cyber_divination_ep01.sh`
- Create: `zhixia-feihualing/tests/test_cyber_divination_ep01_video.sh`
- Create: `zhixia-feihualing/exports/cyber-divination-ep01-subtitled-v01.mp4`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 原片、六段 TTS、八张透明卡。
- Produces: 720×1280、24fps、15.0—15.2 秒的 H.264/AAC 最终成片。

- [ ] **Step 1: 再次预览付费调用并取得用户确认**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode cyber-divination-ep01`

Expected: 待生成数量与实际缺失音频一致；没有接口调用。把预览中的调用次数和台词列表发给用户，只有用户确认后进入下一步。

- [ ] **Step 2: 生成六段配音并验证音频**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode cyber-divination-ep01 --generate`

At prompt enter exactly: `GENERATE cyber-divination-ep01`

Expected: 六段音频状态均为 `ready`，字幕时间轴写入 `episodes/cyber-divination-ep01/subtitles-cyber-divination-ep01.json`。逐段用 `ffprobe` 检查可解码与正时长。

- [ ] **Step 3: 写失败的最终视频测试**

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
output="$project_dir/exports/cyber-divination-ep01-subtitled-v01.mp4"
test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
ffmpeg -v error -i "$output" -f null -
echo "cyber divination final video: PASS (${duration}s)"
```

- [ ] **Step 4: 实现可重复合成脚本**

脚本先调用 `render_cyber_divination_cards.swift` 生成八张透明卡；再将六段配音按 0、2200、3700、4900、8500、10100 毫秒放入时间轴。对 `03-system-hexagram` 使用 `highpass=f=180,aecho=0.8:0.25:45:0.12`，其余对白只做 `loudnorm=I=-18:TP=-2:LRA=7`。在 3.7—8.5 秒持续叠加卦名、六爻、卦辞与出处卡；`04-zhixia-reading` 不重复叠加底部对白卡。12.1—15.0 秒叠加免责声明，14.6—15.0 秒叠加栏目名；最终编码使用 `libx264 -preset medium -crf 18 -pix_fmt yuv420p` 与 `aac -b:a 160k -ar 48000 -ac 2`。

对白若超过各自窗口，构建脚本根据 `ffprobe` 时长计算 `atempo=源时长/目标时长`，目标时长依次为 2.1、1.0、1.1、3.5、1.5、1.9 秒；若任一句所需倍率不在 0.80—1.25，脚本必须退出并报告具体台词，不允许截断句尾。

- [ ] **Step 5: 构建并运行全部相关测试**

Run: `zsh zhixia-feihualing/scripts/build_cyber_divination_ep01.sh`

Run: `python3 zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py -v`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_prop.sh`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_cards.sh`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_assets.sh`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_video.sh`

Expected: 所有命令 exit 0，Python 显示 `Ran 2 tests` 与 `OK`，四个 shell 测试分别输出 `PASS`。

- [ ] **Step 6: 视觉、听觉与文化文本终检**

抽取 0.5、2.8、4.2、6.5、9.2、11.2、13.0、14.7 秒组成联系表。逐项确认：首帧双人同框；卦名为“山雷颐”；完整卦辞无错字；栀夏不笑场；八只空盘清楚可数；阿砚最后收爪垂耳；免责声明从 12.1 秒持续到结尾；栏目名在最后 0.4 秒可辨；音乐与环境声不压对白；系统播报与栀夏正常对白有轻微但不过度的听感区分。

- [ ] **Step 7: 登记最终资产并提交**

在 `assets/inventory.csv` 登记六段配音、原片和最终成片；最终成片状态为 `final`，备注写明 720×1280、24fps、约 15.1 秒、H.264/AAC、山雷颐卦辞、六段语音、八只空盘反转与免责声明。

```bash
git add zhixia-feihualing/assets/audio/cyber-divination-ep01 zhixia-feihualing/episodes/cyber-divination-ep01/subtitles-cyber-divination-ep01.json zhixia-feihualing/scripts/build_cyber_divination_ep01.sh zhixia-feihualing/tests/test_cyber_divination_ep01_video.sh zhixia-feihualing/exports/cyber-divination-ep01-subtitled-v01.mp4 zhixia-feihualing/assets/inventory.csv
git commit -m "完成赛博起卦第一集成片"
```
