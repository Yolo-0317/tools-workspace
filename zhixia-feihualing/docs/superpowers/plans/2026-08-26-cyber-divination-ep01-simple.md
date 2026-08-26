# 《栀夏赛博起卦》第一集简版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将第一集《最后一块桂花糕》改为不依赖桌子和星轨卦盘的 15 秒简版，由栀夏用三枚铜钱“掌心起卦”，并完成视频号封面、正片与发布包装。

**Architecture:** 保留现有七句对白、九张透明字幕卡和本地 FFmpeg 合成链路，只把第三句从“卦盘系统播报”改为栀夏本人读卦，并以三枚无可辨认文字的铜钱承担画面中的起卦动作。角色与场景原片不生成准确汉字或六爻，卦名、颐卦六爻、卦辞、出处、免责声明和栏目落版继续由本地透明卡叠加；星轨六爻盘资产与验收门槛不参与本集。

**Tech Stack:** Markdown、JSON、Python 3 `unittest`、Swift/AppKit/CoreText、zsh、FFmpeg/ffprobe、豆包 TTS、Seedance、PNG 角色参考图

## Global Constraints

- 本计划以 `docs/superpowers/specs/2026-08-26-cyber-divination-ep01-simple-design.md` 为唯一第一集制作依据；星轨六爻盘设计保留为未来升级版。
- 栏目名固定为 `栀夏赛博起卦`；slogan 固定为 `AI 解周易，专断日常小心思`。
- 单集时长为 15.0—15.2 秒；画幅为 720×1280；帧率为 24fps。
- 第一集只使用三枚做旧黄铜色铜钱、一块桂花糕和恰好八只空盘；起卦不依赖桌子、托盘、古籍、竹简或签筒。
- 正片不出现悬空卦盘、星轨、法阵、光柱、粒子漩涡或立体赛博界面。
- 栀夏采用“掌心起卦”：双手合拢轻摇两下，说“起卦”，打开双手后左掌恰好出现三枚铜钱。
- 铜钱表面不出现可辨认文字，正反面不承担真实推演信息。
- 首集固定使用第二十七卦颐卦、常用卦名“山雷颐”和原文“颐，贞吉。观颐，自求口实。”。
- 颐卦六爻从画面顶部到底部固定为 `[阳、阴、阴、阴、阴、阳]`。
- 正片从 12.1 秒持续显示 `传统文化趣味演绎，请勿作为现实决策依据`；发布说明固定包含 `起卦过程为剧情化简化展示。`。
- 发布标题固定为 `AI美女用周易起卦：最后一块桂花糕能吃吗？｜山雷颐`，内容标签必须包含 `#周易`。
- Seedance 只生成画面、背景音乐和环境声，不生成可辨识人声、汉字、卦名、卦辞或具体六爻。
- 任何豆包 TTS 付费调用前必须先运行免费预览，并再次取得用户确认。
- 不覆盖既有角色、音频、视频或字幕资产；新增媒体使用版本化文件名并登记 `assets/inventory.csv`。
- 所有用户可见文字、UI 与汇报禁止 emoji。

---

### Task 1: 将第一集资产契约切换为掌心铜钱简版

**Files:**
- Modify: `zhixia-feihualing/episodes/cyber-divination-ep01/README.md`
- Modify: `zhixia-feihualing/episodes/cyber-divination-ep01/voice-lines.json`
- Modify: `zhixia-feihualing/episodes/cyber-divination-ep01/subtitle-plan.json`
- Modify: `zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py`
- Modify: `zhixia-feihualing/tests/test_cyber_divination_cards.sh`

**Interfaces:**
- Consumes: `config/voices.json` 中 `ayan` 和 `zhixia` 的既有音色配置。
- Produces: `EpisodeManifest` 可读取的七段语音、九张透明卡清单和不依赖卦盘母板的第一集说明。

- [ ] **Step 1: 先更新测试，要求第三句明确属于栀夏**

把测试中的 `03-system-hexagram` 全部改为 `03-zhixia-hexagram`，并增加以下断言：

```python
self.assertEqual(
    [(line.id, line.role, line.text, line.start_ms) for line in manifest.lines],
    [
        ("01-ayan-question", "ayan", "最后一块，能吃吗？", 0),
        ("02-zhixia-cast", "zhixia", "起卦。", 2200),
        ("03-zhixia-hexagram", "zhixia", "山雷颐。", 3700),
        ("04-zhixia-reading", "zhixia", "颐，贞吉。观颐，自求口实。", 4900),
        ("05-ayan-hope", "ayan", "卦说能吃？", 8500),
        ("06-zhixia-reveal", "zhixia", "先数数空盘。", 10100),
        ("07-ayan-excuse", "ayan", "那是……昨天的。", 12100),
    ],
)
self.assertEqual(cards[2]["id"], "03-zhixia-hexagram")
```

同时把 `test_cyber_divination_cards.sh` 中的 PNG 名改为 `03-zhixia-hexagram.png`。

- [ ] **Step 2: 运行测试并确认旧系统播报 ID 被拒绝**

Run: `python3 zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py -v`

Expected: FAIL，差异中出现旧值 `03-system-hexagram`。

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_cards.sh`

Expected: FAIL because `03-zhixia-hexagram.png` is not generated from the old subtitle plan.

- [ ] **Step 3: 最小修改两份 JSON 契约**

在 `voice-lines.json` 中只替换第三句 ID，角色、台词和时间不变：

```json
{
  "id": "03-zhixia-hexagram",
  "role": "zhixia",
  "text": "山雷颐。",
  "start_ms": 3700
}
```

在 `subtitle-plan.json` 中同步替换第三张卡 ID：

```json
{
  "id": "03-zhixia-hexagram",
  "kind": "hexagram",
  "text": "山雷颐",
  "secondary": "颐，贞吉。观颐，自求口实。",
  "attribution": "《周易·颐》"
}
```

- [ ] **Step 4: 重写单集说明中的制作边界**

`README.md` 必须写明：三枚铜钱掌心起卦、第三句由栀夏本人读出、无桌子依赖、无悬空卦盘、正片道具恰好为三枚铜钱/一块桂花糕/八只空盘，以及星轨六爻盘不参与本集。删除“等待 AI 卦盘道具卡后才能制作”的门槛。

- [ ] **Step 5: 运行回归测试和免费 TTS 预览**

Run: `python3 zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py -v`

Expected: `Ran 2 tests` and `OK`。

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_cards.sh`

Expected: `cyber divination cards: PASS`。

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode cyber-divination-ep01`

Expected: 待生成 7 句、阿砚 3 句、栀夏 4 句、预计 7 次调用，并明确“当前为预览模式，未调用语音接口”。

- [ ] **Step 6: 提交契约变更**

```bash
git add zhixia-feihualing/episodes/cyber-divination-ep01/README.md zhixia-feihualing/episodes/cyber-divination-ep01/voice-lines.json zhixia-feihualing/episodes/cyber-divination-ep01/subtitle-plan.json zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py zhixia-feihualing/tests/test_cyber_divination_cards.sh
git commit -m "切换第一集掌心铜钱起卦"
```

### Task 2: 建立场景、封面和发布提示词契约

**Files:**
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/scene-card-prompts-simple.md`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/cover-prompt-simple.md`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/publishing-copy.md`

**Interfaces:**
- Consumes: 栀夏 v02 角色卡、阿砚 v01 角色卡与简版设计稿。
- Produces: 四张场景卡和一张视频号封面的无文字底图提示词，以及固定发布文案。

- [ ] **Step 1: 写四张场景卡提示词**

共同场景固定为明亮低饱和的东方庭院回廊；桂花糕放在宽石栏上，石栏只是食物承托面，不参与起卦。四张卡分别锁定：

1. `01-question-medium`：双人中近景，阿砚盯着宽石栏上的唯一一块桂花糕，栀夏站在右侧，双手尚未动作。
2. `02-palm-casting-close`：栀夏胸前双手近景，双手刚刚打开，左掌恰好三枚无可辨认文字的做旧黄铜铜钱；不要求展示铜钱正反面。
3. `03-reading-reaction`：栀夏左掌保持三枚铜钱，平静读卦；阿砚耳朵竖起、眼睛发亮；画面中央为二维卦象卡留出无遮挡区域。
4. `04-empty-plates-reveal`：镜头移向石栏下方，地面恰好八只空盘，阿砚收爪垂耳；画面上方仍只有一块桂花糕。

每张提示词都逐字包含：`掌心起卦`、`恰好三枚铜钱`、`唯一一块桂花糕`、`不出现悬空卦盘`、`不出现星轨六爻盘`、`不出现轻触古籍`；第四张额外包含 `恰好八只空盘`。

- [ ] **Step 2: 写封面提示词与发布文案**

`cover-prompt-simple.md` 使用设计稿中已确认的第一集简版封面底图提示词，并单列后期文字：

```text
顶部：AI美女·周易起卦
中央：最后一块，能吃吗？
底部：第01卦｜山雷颐
```

`publishing-copy.md` 固定为：

```text
标题：AI美女用周易起卦：最后一块桂花糕能吃吗？｜山雷颐

栀夏赛博起卦｜AI 解周易，专断日常小心思
阿砚说只想吃最后一块，栀夏一卦却先看见了八只空盘。
传统文化趣味演绎，请勿作为现实决策依据。起卦过程为剧情化简化展示。

#栀夏赛博起卦 #周易 #赛博算卦 #AI美女 #国学趣味 #搞笑日常
```

- [ ] **Step 3: 按设计稿逐项审查并提交文本契约**

逐项对照简版设计稿，确认四张场景卡均写明铜钱、桂花糕和空盘数量，所有提示词均排除悬空卦盘、星轨六爻盘、古籍与桌面起卦；确认封面三层文字、固定 slogan、发布标题、`#周易` 与剧情化简化说明完整。人类使用的提示词不增加只检查固定措辞的自动化测试；真实数量和构图在 Task 3 的图片验收中检查。

```bash
git add zhixia-feihualing/episodes/cyber-divination-ep01/scene-card-prompts-simple.md zhixia-feihualing/episodes/cyber-divination-ep01/cover-prompt-simple.md zhixia-feihualing/episodes/cyber-divination-ep01/publishing-copy.md
git commit -m "建立第一集简版提示词"
```

### Task 3: 制作并确认四张场景卡与视频号封面

**Files:**
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards-simple/01-question-medium-v01.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards-simple/02-palm-casting-close-v01.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards-simple/03-reading-reaction-v01.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards-simple/04-empty-plates-reveal-v01.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/cover/cover-base-simple-v01.png`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards-simple/qa-checklist.md`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 的完整提示词与 approved 角色卡。
- Produces: 四张用户确认的 9:16 场景卡和一张无文字封面底图，供原片与最终封面制作。

- [ ] **Step 1: 逐张生成，不引用卦盘道具母板**

一次只生成一张图片，每次仅绑定栀夏、阿砚角色参考图和当前场景提示词；不得绑定 `assets/props/ai-divination-disk-v01/master.png`。输出使用上述版本化路径，保留原图，不覆盖重试版本。

- [ ] **Step 2: 逐张执行人工数量与角色质检**

对全部图片检查同一个栀夏、同一个阿砚、阿砚严格四足和唯一墨尾。卡 2、卡 3 与封面必须恰好三枚铜钱；卡 1、卡 4 与封面必须恰好一块桂花糕；卡 4 必须恰好八只空盘。任何一项数量错误、手指畸形、可辨认伪文字、卦盘或法阵残留都必须重生成该张，不能后期掩盖。

- [ ] **Step 3: 用户确认五张图**

把四张场景卡和封面底图同时展示给用户；只有用户逐项确认后才在 `qa-checklist.md` 标记 approved，并进入视频生成。

- [ ] **Step 4: 登记并提交已确认图片**

在 `assets/inventory.csv` 新增四条 `keyframe` 和一条 `cover-base` 记录，状态为 `approved`，来源记录实际生成工具，版权说明为 `original AI-assisted asset`。

```bash
git add zhixia-feihualing/episodes/cyber-divination-ep01/assets/scene-cards-simple zhixia-feihualing/episodes/cyber-divination-ep01/assets/cover/cover-base-simple-v01.png zhixia-feihualing/assets/inventory.csv
git commit -m "归档第一集简版场景与封面底图"
```

### Task 4: 生成并验收 15 秒简版原片

**Files:**
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/video-prompt-simple.md`
- Create: `zhixia-feihualing/episodes/cyber-divination-ep01/assets/video/content-raw-simple-v01.mp4`
- Create: `zhixia-feihualing/tests/test_cyber_divination_ep01_simple_assets.sh`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3 的四张 approved 场景卡和角色母板。
- Produces: 720×1280、24fps、15.0—15.2 秒，含背景音乐与环境声但无可辨认人声的简版原片。

- [ ] **Step 1: 写失败的原片规格测试**

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
video="$project_dir/episodes/cyber-divination-ep01/assets/video/content-raw-simple-v01.mp4"
test -s "$video"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$video")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$video")" = "24/1"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
ffmpeg -v error -i "$video" -f null -
echo "cyber divination simple raw: PASS (${duration}s)"
```

- [ ] **Step 2: 运行测试并确认原片缺失**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_simple_assets.sh`

Expected: FAIL at `test -s`。

- [ ] **Step 3: 写固定视频提示词并生成原片**

`video-prompt-simple.md` 必须逐段写入：0.0—2.2 秒阿砚提问；2.2—3.7 秒栀夏双手合拢轻摇两下；3.7—4.9 秒打开左掌并保持恰好三枚铜钱；4.9—8.5 秒栀夏看掌心读卦；8.5—10.1 秒阿砚期待反问；10.1—12.1 秒栀夏看向石栏下方并带动镜头移动；12.1—14.6 秒揭示恰好八只空盘，阿砚小幅说最后一句；14.6—15.0 秒保留心虚反应。

负面约束逐字包含：无可辨认人声、无汉字、无卦名、无卦辞、无具体六爻、无悬空卦盘、无星轨、无法阵、无桌面起卦、无多余铜钱、无多余桂花糕、无多余空盘、无多肢、无多尾。使用四张 approved 场景卡生成 `content-raw-simple-v01.mp4`。

- [ ] **Step 4: 运行规格测试并做关键帧检查**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_simple_assets.sh`

Expected: `cyber divination simple raw: PASS`。

抽取 0.5、2.8、4.2、6.5、9.2、11.2、13.0、14.7 秒关键帧，检查角色身份、栀夏手指、三枚铜钱、一块桂花糕、八只空盘、阿砚四足与唯一墨尾，以及画面中没有卦盘或法阵。用户确认原片后再登记为 `available`。

- [ ] **Step 5: 提交原片与资产记录**

```bash
git add zhixia-feihualing/episodes/cyber-divination-ep01/video-prompt-simple.md zhixia-feihualing/episodes/cyber-divination-ep01/assets/video/content-raw-simple-v01.mp4 zhixia-feihualing/tests/test_cyber_divination_ep01_simple_assets.sh zhixia-feihualing/assets/inventory.csv
git commit -m "归档第一集掌心起卦原片"
```

### Task 5: 经确认生成配音并完成正片与封面

**Files:**
- Create after approval: `zhixia-feihualing/assets/audio/cyber-divination-ep01/*.mp3`
- Create after approval: `zhixia-feihualing/assets/audio/cyber-divination-ep01/audio-metadata.json`
- Create: `zhixia-feihualing/scripts/build_cyber_divination_ep01_simple.sh`
- Create: `zhixia-feihualing/scripts/render_cyber_divination_ep01_cover.swift`
- Create: `zhixia-feihualing/tests/test_cyber_divination_ep01_simple_video.sh`
- Create: `zhixia-feihualing/tests/test_cyber_divination_ep01_cover.sh`
- Create: `zhixia-feihualing/exports/cyber-divination-ep01-simple-v01.mp4`
- Create: `zhixia-feihualing/exports/cyber-divination-ep01-cover-v01.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 简版原片、七段 TTS、九张透明卡与无文字封面底图。
- Produces: 720×1280、24fps、15.0—15.2 秒的 H.264/AAC 正片，以及 720×1280 的视频号封面。

- [ ] **Step 1: 免费预览付费语音调用并取得用户确认**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode cyber-divination-ep01`

Expected: 待生成数量与缺失音频一致，没有调用接口。把调用次数和七句台词发给用户，只有用户明确确认后继续。

- [ ] **Step 2: 生成并验证七段配音**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode cyber-divination-ep01 --generate`

At prompt enter exactly: `GENERATE cyber-divination-ep01`

Expected: 七段状态均为 `ready`，每段 MP3 可由 `ffprobe` 解码且时长大于 0。第三句保持栀夏正常音色，不添加高通、回声、窄化或系统播报效果。

- [ ] **Step 3: 写失败的正片与封面规格测试**

正片测试检查：文件存在、720×1280、H.264、AAC、24fps、15.0—15.2 秒、FFmpeg 可完整解码。封面测试检查：PNG 存在、720×1280、可解码。

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_simple_video.sh`

Expected: FAIL because final video is absent.

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_cover.sh`

Expected: FAIL because final cover is absent.

- [ ] **Step 4: 实现可重复正片合成**

`build_cyber_divination_ep01_simple.sh` 调用 `render_cyber_divination_cards.swift` 生成九张透明卡，将七段音频按 0、2200、3700、4900、8500、10100、12100 毫秒放入时间轴。所有七句只做 `loudnorm=I=-18:TP=-2:LRA=7`；第三句不得增加系统音效果。

3.7—8.5 秒叠加 `03-zhixia-hexagram`；4.9—8.5 秒不重复叠加 `04-zhixia-reading` 底部对白卡；12.1—14.6 秒叠加 `07-ayan-excuse`；12.1—15.0 秒叠加 `08-disclaimer`；14.6—15.0 秒叠加 `09-series-title`。输出编码为 `libx264 -preset medium -crf 18 -pix_fmt yuv420p` 和 `aac -b:a 160k -ar 48000 -ac 2`。

对白目标时长依次为 2.1、1.0、1.1、3.5、1.5、1.9、2.4 秒；若任一句所需 `atempo` 倍率不在 0.80—1.25，脚本退出并报告台词 ID，不截断句尾。

- [ ] **Step 5: 实现固定封面文字排版**

`render_cyber_divination_ep01_cover.swift` 读取 `cover-base-simple-v01.png`，在透明安全区叠加：顶部 `AI美女·周易起卦`、中央 `最后一块，能吃吗？`、底部 `第01卦｜山雷颐`。不得修改底图人物、铜钱或桂花糕，不让文字覆盖栀夏面部、左掌、阿砚面部或桂花糕。

- [ ] **Step 6: 构建并运行全部相关测试**

Run: `zsh zhixia-feihualing/scripts/build_cyber_divination_ep01_simple.sh`

Run: `python3 zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py -v`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_cards.sh`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_simple_assets.sh`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_simple_video.sh`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_ep01_cover.sh`

Expected: 所有命令 exit 0；Python 测试均为 `OK`；四个 shell 测试均输出 `PASS`。

- [ ] **Step 7: 视觉、听觉与文本终检**

抽取 0.5、2.8、4.2、6.5、9.2、11.2、13.0、14.7 秒组成联系表。逐项确认：首帧双人可见；掌心恰好三枚铜钱；没有卦盘、法阵或桌面起卦；栀夏本人自然读出“山雷颐”；卦辞和六爻准确；八只空盘清楚可数；免责声明从 12.1 秒持续到结尾；栏目名在最后 0.4 秒可辨；对白持续至约 14.5 秒；音乐与环境声不压对白。封面另检三层文字、角色身份、三枚铜钱、一块桂花糕与空盘悬念。

- [ ] **Step 8: 登记最终资产并提交**

在 `assets/inventory.csv` 登记七段配音、简版原片、最终正片和视频号封面。正片状态为 `final`，备注包含 720×1280、24fps、约 15.1 秒、H.264/AAC、掌心三枚铜钱、山雷颐卦辞、八只空盘、免责声明；封面状态为 `final`，备注包含三层固定文字。

```bash
git add zhixia-feihualing/assets/audio/cyber-divination-ep01 zhixia-feihualing/episodes/cyber-divination-ep01/subtitles-cyber-divination-ep01.json zhixia-feihualing/scripts/build_cyber_divination_ep01_simple.sh zhixia-feihualing/scripts/render_cyber_divination_ep01_cover.swift zhixia-feihualing/tests/test_cyber_divination_ep01_simple_video.sh zhixia-feihualing/tests/test_cyber_divination_ep01_cover.sh zhixia-feihualing/exports/cyber-divination-ep01-simple-v01.mp4 zhixia-feihualing/exports/cyber-divination-ep01-cover-v01.png zhixia-feihualing/assets/inventory.csv
git commit -m "完成赛博起卦第一集简版"
```
