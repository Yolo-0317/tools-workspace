# 《一舞一愿·重新出发》全程朗诵试验 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为《一舞一愿·重新出发》生成一版从视频第一帧贯穿至约 14.800 秒的自然语速朗诵，并用真实音频判断 58 字四段结构能否支撑十五秒诗舞。

**Architecture:** 把季级合同从“短朗诵加纯舞尾段”升级为“首帧开口、末尾收声”的全程朗诵合同，只将第一条标记为 `voice-trial`，第二、第三条保留为 `theme-outline`，禁止提前生成。第一条使用独立 `voice-v02` 音频目录和四段 TTS 清单，生成后裁去每段首尾无效静音，按真实时长排布字幕；只有首字、末字、段间气口和试听均通过门禁，才允许进入舞蹈提示词修订。

**Tech Stack:** JSON、Python 3 标准库与 `unittest`、豆包 Seed TTS 2.0、FFmpeg、FFprobe、SHA-256、Git。

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-31-yi-wu-yi-yuan-blessing-series-design.md`，以提交 `7ae80aa` 及后续修订为准。
- 新版朗诵逐字固定为：`送给重新出发的你。也许这一程并不轻松，也许前方还有风浪。愿你此去有路，所盼有期；走过的每一步，都算数。长风破浪会有时，直挂云帆济沧海。`
- 全文共 58 个汉字，顺序固定为“赠送对象—处境共鸣—现代祝愿—古诗原句”；古诗必须是最后一句。
- 固定使用 `config/voices.json` 当前 `zhixia` 音色和 `speech_rate=0`，不得使用负语速、`atempo`、机械拉伸、变调、赶字、截断、吟唱或拖腔。
- 首个可辨识语音最晚在 0.200 秒出现；最后一字目标落在 14.000—14.800 秒，自然尾音允许延续到 15.000 秒。
- 相邻两段有效语音之间的气口不得超过 500 毫秒；不得用长空白填满十五秒。
- TTS 生成是产生费用的外部操作；执行前必须展示 4 次预计调用并取得当次明确确认。任何重试或改稿后重生成都需要新的调用预览与确认。
- 第一版若短于 14.000 秒或长于 15.000 秒，只报告真实结果并停止；不得自动变速、自动追加空白或未经用户确认生成第二版。
- 第二、第三条在本计划中保持 `theme-outline`，不得调用 TTS 或生成视频。
- 旧 `voice-v01` 三段音频、哈希和时间轴仅作失败实验留档，不覆盖、不删除、不伪装成新版结果。
- 只提交本计划明确列出的配置、测试和时间轴文件，不提交 `assets/audio/` 中被 `.gitignore` 忽略的音频，不带入工作区其他修改。

---

## File Structure

- `operations/yi-wu-yi-yuan/qiancheng-v01.json`：记录全程朗诵统一门槛、第一条完整四段文本和三条生产状态。
- `scripts/validate_yi_wu_yi_yuan.py`：按 `voice-trial` 状态校验 55—60 字、四段顺序、首末时间与最大气口；不把选题骨架误判为可生产清单。
- `tests/test_validate_yi_wu_yi_yuan.py`：覆盖 58 字合同、过短文本、晚开口、早结束、超时和过长气口。
- `tests/test_yi_wu_yi_yuan_qiancheng_configs.py`：验证第一条 v02 四段 TTS 清单与季级合同逐字一致，第二、第三条仍为选题骨架。
- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json`：第一条四段正常语速 TTS 清单，输出到独立 `voice-v02` 目录。
- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-v02.json`：记录四段原始与有效时长、SHA-256、真实排布和门禁结果。
- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-v02.json`：记录四段逐句字幕的真实开始、结束、类型和古诗题署。
- `assets/audio/yiwu-yiyuan-qiancheng-01-restart-15s-voice-v02/`：四段本地 MP3 和生成元数据，不进入 Git。

### Task 1: 升级全程朗诵合同与校验门禁

**Files:**
- Modify: `operations/yi-wu-yi-yuan/qiancheng-v01.json`
- Modify: `scripts/validate_yi_wu_yi_yuan.py`
- Modify: `tests/test_validate_yi_wu_yi_yuan.py`

**Interfaces:**
- Consumes: 设计真源中的 58 字固定文本、四段结构和 0.200／14.000／14.800／15.000 秒门槛。
- Produces: `validate_season(path: Path) -> None` 对 `voice-trial` 与 `theme-outline` 分流校验；`validate_subtitle_plan(path: Path, duration_ms: int, voice_start_max_ms: int, voice_end_min_ms: int, voice_end_target_max_ms: int, max_gap_ms: int) -> None` 校验全程字幕时间轴。

- [ ] **Step 1: 写合同失败测试**

把季级测试中的“三条均为 32 字”替换为以下断言，并保留禁用话术、出处和唯一性测试：

```python
def test_restart_is_the_only_full_length_voice_trial(self) -> None:
    data = valid_season()
    trials = [item for item in data["episodes"] if item["production_status"] == "voice-trial"]
    self.assertEqual([item["episode"] for item in trials],
                     ["yiwu-yiyuan-qiancheng-01-restart-15s"])
    entry = trials[0]
    self.assertEqual(
        [entry["recipient"], entry["situation"], entry["blessing"], entry["poem"]],
        [
            "送给重新出发的你",
            "也许这一程并不轻松，也许前方还有风浪",
            "愿你此去有路，所盼有期；走过的每一步，都算数",
            "长风破浪会有时，直挂云帆济沧海",
        ],
    )
    self.assertEqual(sum(module.count_hanzi(entry[field]) for field in
                         ("recipient", "situation", "blessing", "poem")), 58)

def test_rejects_voice_trial_shorter_than_55_hanzi(self) -> None:
    data = valid_season()
    data["episodes"][0]["situation"] = "前路有风浪"
    with self.assertRaisesRegex(ValueError, "voice-trial.*55"):
        validate_temp(data)
```

- [ ] **Step 2: 写时间轴失败测试**

```python
def full_length_plan() -> list[dict[str, object]]:
    return [
        {"id": "01-recipient", "start": 0.0, "end": 1.5},
        {"id": "02-situation", "start": 1.68, "end": 5.4},
        {"id": "03-blessing", "start": 5.64, "end": 10.1},
        {"id": "04-poem", "start": 10.45, "end": 14.6},
    ]

def test_rejects_voice_start_after_200_ms(self) -> None:
    plan = full_length_plan()
    plan[0]["start"] = 0.201
    with self.assertRaisesRegex(ValueError, "voice start"):
        validate_plan_temp(plan)

def test_rejects_voice_end_before_14000_ms(self) -> None:
    plan = full_length_plan()
    plan[-1]["end"] = 13.999
    with self.assertRaisesRegex(ValueError, "voice end"):
        validate_plan_temp(plan)

def test_rejects_gap_over_500_ms(self) -> None:
    plan = full_length_plan()
    plan[2]["start"] = 5.901
    with self.assertRaisesRegex(ValueError, "gap"):
        validate_plan_temp(plan)
```

- [ ] **Step 3: 运行测试并确认红灯**

Run: `python3 -m unittest tests.test_validate_yi_wu_yi_yuan -v`

Expected: FAIL；旧合同缺少 `production_status`、`situation`，旧时间轴接口仍要求三段并允许 7.441 秒结束。

- [ ] **Step 4: 修改季级合同**

在顶层用以下字段替换旧 `voice_end_max_ms`、`tail_min_ms` 和旧总字数限制：

```json
"recitation": {
  "target_hanzi_min": 55,
  "target_hanzi_max": 60,
  "voice_start_max_ms": 200,
  "voice_end_min_ms": 14000,
  "voice_end_target_max_ms": 14800,
  "duration_ms": 15000,
  "max_gap_ms": 500,
  "speech_rate": 0
}
```

第一条增加 `production_status="voice-trial"` 和固定 `situation`；第二、第三条增加 `production_status="theme-outline"`，保留现有短祝愿作为策划骨架。`validate_season` 只对 `voice-trial` 应用 55—60 字四段门禁，但三条仍统一执行非空字段、禁用话术、出处、slug 与唯一性校验。

- [ ] **Step 5: 实现四段字幕门禁**

`validate_subtitle_plan` 固定要求以下 ID：

```python
SUBTITLE_IDS = ["01-recipient", "02-situation", "03-blessing", "04-poem"]
```

校验首项 `start` 不大于 0.200 秒、末项 `end` 不小于 14.000 秒且不大于 15.000 秒、相邻有效语音间隔不大于 500 毫秒。14.800 秒是目标上沿而非硬失败上限；14.801—15.000 秒允许进入人工试听，但 CLI 必须输出超出目标的提醒。

- [ ] **Step 6: 运行合同测试与 CLI 校验**

Run: `python3 -m unittest tests.test_validate_yi_wu_yi_yuan -v && python3 scripts/validate_yi_wu_yi_yuan.py --season operations/yi-wu-yi-yuan/qiancheng-v01.json`

Expected: PASS；CLI 输出第一条 `voice-trial: 58 Hanzi`，第二、第三条输出 `theme-outline`，不得把短稿显示为生产就绪。

- [ ] **Step 7: 提交合同升级**

```bash
git add operations/yi-wu-yi-yuan/qiancheng-v01.json \
  scripts/validate_yi_wu_yi_yuan.py \
  tests/test_validate_yi_wu_yi_yuan.py
git commit -m "升级一舞一愿全程朗诵门禁"
```

### Task 2: 建立第一条四段 v02 配音清单

**Files:**
- Modify: `tests/test_yi_wu_yi_yuan_qiancheng_configs.py`
- Modify: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json`
- Modify: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/README.md`

**Interfaces:**
- Consumes: Task 1 的 `voice-trial` 四段文本和现有 `scripts/generate_episode_audio.py`。
- Produces: 四段 `one-poem-story` TTS 清单，输出目录固定为 `yiwu-yiyuan-qiancheng-01-restart-15s-voice-v02`。

- [ ] **Step 1: 写四段清单失败测试**

```python
self.assertEqual(
    [line["id"] for line in raw["lines"]],
    ["01-recipient", "02-situation", "03-blessing", "04-poem"],
)
self.assertEqual(
    [line["text"].rstrip("。") for line in raw["lines"]],
    [entry["recipient"], entry["situation"], entry["blessing"], entry["poem"]],
)
self.assertEqual(raw["audio_slug"],
                 "yiwu-yiyuan-qiancheng-01-restart-15s-voice-v02")
self.assertEqual({line["speech_rate"] for line in raw["lines"]}, {0})
self.assertEqual([line["gap_before_ms"] for line in raw["lines"]],
                 [0, 180, 240, 350])
```

测试同时断言第二、第三条在季级合同中为 `theme-outline`，本次不预览、不调用其 TTS。

- [ ] **Step 2: 运行测试并确认红灯**

Run: `python3 -m unittest tests.test_yi_wu_yi_yuan_qiancheng_configs -v`

Expected: FAIL；现有第一条仍为 `voice-v01` 三段清单，缺少 `02-situation` 和 `04-poem`。

- [ ] **Step 3: 修改第一条清单**

四行固定为：

```json
[
  {"id":"01-recipient","text":"送给重新出发的你。","revision":2,"speech_rate":0,"gap_before_ms":0},
  {"id":"02-situation","text":"也许这一程并不轻松，也许前方还有风浪。","revision":2,"speech_rate":0,"gap_before_ms":180},
  {"id":"03-blessing","text":"愿你此去有路，所盼有期；走过的每一步，都算数。","revision":2,"speech_rate":0,"gap_before_ms":240},
  {"id":"04-poem","text":"长风破浪会有时，直挂云帆济沧海。","revision":2,"speech_rate":0,"gap_before_ms":350}
]
```

四行 `role` 均为 `zhixia`。`context_texts` 分别要求：

- 对象句：年轻清透、真诚克制，从容把话递给一个具体的人；第一字直接进入，不喊栏目名，不赶字。
- 处境句：像理解对方正在经历的难处，语气平静、有分寸；两个“也许”自然呼应，不悲情、不说教、不用广告安慰腔。
- 祝愿句：温和而坚定，“所盼有期”自然落下，“每一步”“都算数”有轻微层次但不逐字重读；不甜腻、不拖尾。
- 古诗句：由现代话自然提升为清朗说诗，保持同一人物和距离；“长风破浪”打开，“济沧海”完整收束，不吟唱、不念作者篇名、不用比赛腔。

- [ ] **Step 4: 更新 README 的失败实验记录**

记录 `voice-v01` 的 32 字有效朗诵在 7.441 秒结束，不能用于十五秒成片；`voice-v02` 改为 58 字四段全程朗诵试验。旧文件保留但不再作为制作输入。

- [ ] **Step 5: 运行配置测试与只读预览**

Run: `python3 -m unittest tests.test_yi_wu_yi_yuan_qiancheng_configs tests.test_zhixia_tts_manifest tests.test_zhixia_tts_pipeline -v && python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-01-restart-15s`

Expected: 测试 PASS；预览显示 4 句、4 次预计调用、`voice-v02` 输出目录，并明确“未调用语音接口”。

- [ ] **Step 6: 提交四段配音清单**

```bash
git add tests/test_yi_wu_yi_yuan_qiancheng_configs.py \
  episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json \
  episodes/yiwu-yiyuan-qiancheng-01-restart-15s/README.md
git commit -m "建立重新出发全程朗诵清单"
```

### Task 3: 生成、测量并交付 v02 试听

**Files:**
- Local create: `assets/audio/yiwu-yiyuan-qiancheng-01-restart-15s-voice-v02/*.mp3`
- Create: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-v02.json`
- Create: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-v02.json`

**Interfaces:**
- Consumes: Task 2 的四段清单和用户对本次 4 次豆包 TTS 调用的明确确认。
- Produces: 四段正常语速 MP3、原始及有效时长、真实字幕时间轴和一组可播放试听文件。

- [ ] **Step 1: 再次显示付费预览并取得确认**

Run: `python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-01-restart-15s`

Expected: `待生成：4 句`、`预计产生豆包 TTS 调用：4 次`。没有明确确认时在此停止。

- [ ] **Step 2: 生成四段 v02 音频**

Run: `python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-01-restart-15s --generate`

交互确认文字固定为 `GENERATE yiwu-yiyuan-qiancheng-01-restart-15s`。Expected: 四个 24 kHz 单声道 MP3 与 `audio-metadata.json` 生成完成；不覆盖 `voice-v01`。

- [ ] **Step 3: 测量每段有效时长与哈希**

对四段统一使用：

```text
silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,
areverse,
silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,
areverse
```

用 FFprobe 记录原始与裁切后毫秒值，用 `shasum -a 256` 记录源 MP3 哈希。按 `[0, 180, 240, 350]` 毫秒气口顺序累计真实时间轴，不手工改写有效时长。

- [ ] **Step 4: 生成 v02 时间轴与字幕计划**

`audio-timing-v02.json` 写入四段 `source_duration_ms`、`trimmed_duration_ms`、`start_ms`、`end_ms`、`sha256`，以及整体 `voice_start_ms`、`voice_end_ms`、`max_gap_ms` 和门禁结果。

`subtitle-plan-v02.json` 固定使用四项：前三项 `kind="modern"`，第四项 `kind="poem"` 并带 `attribution="唐·李白《行路难·其一》"`。开始与结束必须来自实测时间轴，不使用估算值。

- [ ] **Step 5: 执行硬门禁**

Run: `python3 scripts/validate_yi_wu_yi_yuan.py --subtitle-plan episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-v02.json`

结果处理固定为：

- `14.000—14.800 秒`：通过自动时长门禁，进入人工试听。
- `14.801—15.000 秒`：不自动判失败，但必须提示超出目标，人工确认是否仍显从容。
- `<14.000 秒`：判定覆盖不足，停止；不得加空白、降速或修改视频时长。
- `>15.000 秒`：判定超时，停止；不得加速或截断。
- 任一气口 `>500 毫秒`：判定不连续，停止。

任何失败都只汇报四段真实时长和整体差值，不自动产生第二轮 TTS 调用。

- [ ] **Step 6: 提供四段试听与整体节奏结论**

向用户提供四个本地 MP3 播放入口，并报告：每段有效时长、总有效语音时长、三个气口、最后一字时间、与 14.000—14.800 秒目标的差值。请用户分别判断是否存在赶字、广告腔、说教感、诗句比赛腔和不自然拖尾。

- [ ] **Step 7: 仅在自动门禁通过后提交时间轴**

```bash
git add episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-v02.json \
  episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-v02.json
git commit -m "锁定重新出发全程朗诵时间轴"
```

若自动门禁失败，不创建通过状态的时间轴提交；保留本地音频作为试验，等待用户确认下一版文案。

### Task 4: 语音验收后恢复视频设计

**Files:**
- Modify after approval: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md`
- Modify after approval: `docs/superpowers/plans/2026-08-31-yi-wu-yi-yuan-qiancheng.md`

**Interfaces:**
- Consumes: Task 3 通过自动门禁且由用户确认的真实 v02 时间轴。
- Produces: 与四段朗诵逐段同步的新舞蹈、音乐、镜头和字幕实施步骤；未通过语音验收时不产生视频生成请求。

- [ ] **Step 1: 等待用户明确验收语音**

用户必须明确确认整体语速自然、四段情绪连续、原诗收尾成立。仅确认“时长合格”不等于声音验收。

- [ ] **Step 2: 作废旧视频节奏映射**

删除 `prompt.md` 内旧的 `0.000—1.352`、`1.532—3.541`、`3.941—7.441` 映射，并以 v02 四段真实节点重新安排三个舞蹈高潮。不得保留“7.441—15.000 秒无人声完成航路”的旧设计。

- [ ] **Step 3: 修订总体实施计划**

把旧计划中所有三段清单、11.500 秒人声截止和 3.000 秒纯舞尾段替换为本次已验证的四段真实时间轴，再单独展示一次 Seedance 调用预览并取得确认。

- [ ] **Step 4: 提交视频设计修订**

```bash
git add episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md \
  docs/superpowers/plans/2026-08-31-yi-wu-yi-yuan-qiancheng.md
git commit -m "同步重新出发全程朗诵与诗舞设计"
```
