# 《一舞一愿·重新出发》v03 自然停顿朗诵试验 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 52 字四段稿和更完整的句间停顿，验证栀夏能否在 15 秒内从容完成“现代话朗诵—古诗原句”，并让最后一字自然落在 14.000—14.800 秒。

**Architecture:** 保留 v01、v02 音频及时序作为实验历史，不覆盖、不删除。把季级合同调整为 50—53 字、最大气口 900 毫秒，并将第一条制作清单升级为独立 `voice-v03` 四段试验。先用测试锁定逐字文案和 `[0, 650, 750, 850]` 毫秒目标停顿，再预览 4 次 TTS 调用；只有得到用户当次明确确认后才生成、裁切、测量和合成试听。自动门禁与人工听感必须同时通过，才允许恢复舞蹈和视频设计。

**Tech Stack:** JSON、Python 3 标准库与 `unittest`、豆包 Seed TTS 2.0、FFmpeg、FFprobe、SHA-256、Git。

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-31-yi-wu-yi-yuan-blessing-series-design.md`，以提交 `9209294` 及后续修订为准。
- v03 逐字固定为：`送给重新出发的你。这一程或许不轻松，前方也会有风浪。愿你所盼有期，走过的每一步都算数。长风破浪会有时，直挂云帆济沧海。`
- 四段汉字数固定为 8、15、15、14，共 52 字；顺序固定为“赠送对象—处境共鸣—现代祝愿—古诗原句”。
- 三个目标气口固定为 650、750、850 毫秒；实测气口可以因裁切产生毫秒级差异，但任一气口不得超过 900 毫秒。
- 固定使用 `config/voices.json` 当前 `zhixia` 音色和 `speech_rate=0`。不得用负语速、`atempo`、机械拉伸、变调、赶字、截断、吟唱或拖腔适配时长。
- 首个可辨识语音最晚在 0.200 秒出现；最后一字目标落在 14.000—14.800 秒；音频硬上限为 15.000 秒。
- “精确 15 秒试听”只能在自然尾音之后补静音，不得用补静音伪装朗诵覆盖达标；若最后一字早于 14.000 秒，仍判定覆盖不足。
- TTS 是产生费用的外部操作。执行前必须展示 4 次预计调用并取得当次明确确认；任何重试或改稿后重生成都必须重新预览、重新确认。
- 第二、第三条保持 `theme-outline`，不得调用其 TTS。不得生成 Seedance 视频。
- v01 的“覆盖不足”和 v02 的“时长通过、听感过密”均作为失败实验留档。不得覆盖或删除 `audio-timing-v02.json`、`subtitle-plan-v02.json` 及旧音频。
- 只提交本计划列出的合同、测试、清单、README 和 v03 时序文件，不提交被 `.gitignore` 忽略的 `assets/audio/`，不带入工作区其他修改。

---

## File Structure

- `operations/yi-wu-yi-yuan/qiancheng-v01.json`：保存 50—53 字、最大 900 毫秒气口等季级门禁，以及第一条 v03 固定文本。
- `scripts/validate_yi_wu_yi_yuan.py`：校验四段顺序、字数、首末时刻和气口上限。
- `tests/test_validate_yi_wu_yi_yuan.py`：覆盖 52 字合同、上下边界、晚开口、早结束、超时和 901 毫秒气口。
- `tests/test_yi_wu_yi_yuan_qiancheng_configs.py`：锁定 v03 文案、版本、语速、音频目录和目标停顿。
- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json`：v03 四段正常语速 TTS 清单。
- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/README.md`：记录 v01、v02 结论和 v03 试验假设。
- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-v03.json`：记录源音频哈希、原始/有效时长、自然排布和门禁结果。
- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-v03.json`：记录与真实语音严格同步的四段字幕。
- `assets/audio/yiwu-yiyuan-qiancheng-01-restart-15s-voice-v03/`：四段 MP3、裁切音频、自然尾试听和精确 15 秒试听；本地留存，不进 Git。

### Task 1: 用测试锁定 v03 合同和停顿门禁

**Files:**
- Modify: `tests/test_validate_yi_wu_yi_yuan.py`
- Modify: `operations/yi-wu-yi-yuan/qiancheng-v01.json`
- Modify: `scripts/validate_yi_wu_yi_yuan.py`

**Interfaces:**
- Consumes: 52 字固定文本、`voice_start_max_ms=200`、`voice_end_min_ms=14000`、`voice_end_target_max_ms=14800`、`duration_ms=15000`、`max_gap_ms=900`。
- Produces: `validate_season(path: Path) -> None` 和 `validate_subtitle_plan(...) -> None` 对 v03 合同及时序执行硬门禁。

- [ ] **Step 1: 先改测试，固定 52 字正文**

将当前 58 字断言替换为：

```python
self.assertEqual(
    [entry["recipient"], entry["situation"], entry["blessing"], entry["poem"]],
    [
        "送给重新出发的你",
        "这一程或许不轻松，前方也会有风浪",
        "愿你所盼有期，走过的每一步都算数",
        "长风破浪会有时，直挂云帆济沧海",
    ],
)
self.assertEqual(
    [module.count_hanzi(entry[field]) for field in
     ("recipient", "situation", "blessing", "poem")],
    [8, 15, 15, 14],
)
self.assertEqual(data["recitation"]["target_hanzi_min"], 50)
self.assertEqual(data["recitation"]["target_hanzi_max"], 53)
self.assertEqual(data["recitation"]["max_gap_ms"], 900)
self.assertEqual(data["recitation"]["target_gaps_ms"], [650, 750, 850])
```

增加两个边界失败用例：把第一条总字数改为 49 字时必须报错；改为 54 字时也必须报错。

- [ ] **Step 2: 先改时间轴测试，允许完整停顿并拒绝 901 毫秒**

测试基准时间轴使用四段 ID：

```python
def full_length_plan() -> list[dict[str, object]]:
    return [
        {"id": "01-recipient", "start": 0.0, "end": 1.25},
        {"id": "02-situation", "start": 1.90, "end": 5.20},
        {"id": "03-blessing", "start": 5.95, "end": 9.40},
        {"id": "04-poem", "start": 10.25, "end": 14.40},
    ]
```

断言该计划通过；将任一相邻间隔改为 0.901 秒时必须以 `gap` 报错。原有晚于 0.200 秒开口、早于 14.000 秒收声和晚于 15.000 秒收声的失败用例继续保留。

- [ ] **Step 3: 运行测试并确认红灯**

Run: `python3 -m unittest tests.test_validate_yi_wu_yi_yuan -v`

Expected: FAIL；当前合同仍为 55—60 字、500 毫秒气口和 v02 文案。

- [ ] **Step 4: 修改季级合同**

`recitation` 固定为：

```json
{
  "target_hanzi_min": 50,
  "target_hanzi_max": 53,
  "voice_start_max_ms": 200,
  "voice_end_min_ms": 14000,
  "voice_end_target_max_ms": 14800,
  "duration_ms": 15000,
  "max_gap_ms": 900,
  "target_gaps_ms": [650, 750, 850],
  "speech_rate": 0
}
```

只替换第一条 `voice-trial` 的 `situation` 与 `blessing`；第二、第三条的 `theme-outline` 状态和策划文案不变。

- [ ] **Step 5: 修改校验器**

让 `validate_season` 接受并校验 `target_gaps_ms`：必须恰有三个正整数、逐项不大于 `max_gap_ms`。字数使用合同中的 50—53 动态边界。`validate_subtitle_plan` 继续要求 `01-recipient`、`02-situation`、`03-blessing`、`04-poem`，将最大气口门禁从 500 改为合同传入的 900 毫秒。

- [ ] **Step 6: 运行测试和季级校验**

Run: `python3 -m unittest tests.test_validate_yi_wu_yi_yuan -v && python3 scripts/validate_yi_wu_yi_yuan.py --season operations/yi-wu-yi-yuan/qiancheng-v01.json`

Expected: PASS；CLI 显示第一条 `voice-trial: 52 Hanzi`，第二、第三条仍为 `theme-outline`。

- [ ] **Step 7: 提交合同修订**

```bash
git add operations/yi-wu-yi-yuan/qiancheng-v01.json \
  scripts/validate_yi_wu_yi_yuan.py \
  tests/test_validate_yi_wu_yi_yuan.py
git commit -m "调整一舞一愿第三版朗诵门禁"
```

### Task 2: 建立 v03 四段配音清单

**Files:**
- Modify: `tests/test_yi_wu_yi_yuan_qiancheng_configs.py`
- Modify: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json`
- Modify: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/README.md`

**Interfaces:**
- Consumes: Task 1 的逐字合同和现有 `scripts/generate_episode_audio.py`。
- Produces: 独立输出到 `yiwu-yiyuan-qiancheng-01-restart-15s-voice-v03` 的四段 TTS 清单；本任务只做本地配置和免费预览。

- [ ] **Step 1: 先改配置测试**

固定以下断言：

```python
self.assertEqual(raw["audio_slug"],
                 "yiwu-yiyuan-qiancheng-01-restart-15s-voice-v03")
self.assertEqual([line["id"] for line in raw["lines"]],
                 ["01-recipient", "02-situation", "03-blessing", "04-poem"])
self.assertEqual([line["revision"] for line in raw["lines"]], [3, 3, 3, 3])
self.assertEqual({line["speech_rate"] for line in raw["lines"]}, {0})
self.assertEqual([line["gap_before_ms"] for line in raw["lines"]],
                 [0, 650, 750, 850])
self.assertEqual([line["text"].rstrip("。") for line in raw["lines"]],
                 [entry["recipient"], entry["situation"],
                  entry["blessing"], entry["poem"]])
```

测试还要证明第二、第三条为 `theme-outline`，不在本次 TTS 清单中。

- [ ] **Step 2: 运行配置测试并确认红灯**

Run: `python3 -m unittest tests.test_yi_wu_yi_yuan_qiancheng_configs -v`

Expected: FAIL；当前文件仍是 revision 2、`voice-v02`、58 字和 `[0, 180, 240, 350]` 毫秒气口。

- [ ] **Step 3: 修改 v03 清单**

四行固定为：

```json
[
  {"id":"01-recipient","text":"送给重新出发的你。","revision":3,"speech_rate":0,"gap_before_ms":0},
  {"id":"02-situation","text":"这一程或许不轻松，前方也会有风浪。","revision":3,"speech_rate":0,"gap_before_ms":650},
  {"id":"03-blessing","text":"愿你所盼有期，走过的每一步都算数。","revision":3,"speech_rate":0,"gap_before_ms":750},
  {"id":"04-poem","text":"长风破浪会有时，直挂云帆济沧海。","revision":3,"speech_rate":0,"gap_before_ms":850}
]
```

四行 `role` 均为 `zhixia`。`context_texts` 分别要求：

- 对象句：从第一字自然开口，像把一句话稳稳递给具体的人；句号完整落下，不喊栏目名。
- 处境句：理解困难但不渲染苦难；逗号处有轻微呼吸，句号处完整收住，不赶向下一句。
- 祝愿句：温和坚定；“所盼有期”自然落下，“每一步都算数”整体表达，不逐字重读、不甜腻。
- 古诗句：从现代话自然抬起为清朗说诗；逗号清楚，“济沧海”完整收束，不吟唱、不用比赛腔。

- [ ] **Step 4: 补全 README 实验记录**

明确记录：v01 因最后一字仅到 7.441 秒而失败；v02 虽在自动时长门禁内，但句间停顿过小、58 字听感过密，人工验收失败；v03 用 52 字和 650／750／850 毫秒气口测试自然朗诵。旧文件仅作证据，不再是生产输入。

- [ ] **Step 5: 运行配置与 TTS 管线测试**

Run: `python3 -m unittest tests.test_yi_wu_yi_yuan_qiancheng_configs tests.test_zhixia_tts_manifest tests.test_zhixia_tts_pipeline -v`

Expected: PASS；清单与季级合同逐字一致，revision 均为 3，目标目录为 `voice-v03`。

- [ ] **Step 6: 执行免费只读预览**

Run: `python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-01-restart-15s`

Expected: 显示 4 句、预计 4 次豆包 TTS 调用、`voice-v03` 目录，并明确没有调用语音接口。

- [ ] **Step 7: 提交 v03 清单**

```bash
git add tests/test_yi_wu_yi_yuan_qiancheng_configs.py \
  episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json \
  episodes/yiwu-yiyuan-qiancheng-01-restart-15s/README.md
git commit -m "建立重新出发第三版朗诵清单"
```

### Task 3: 经确认后生成并测量 v03 语音

**Files:**
- Local create: `assets/audio/yiwu-yiyuan-qiancheng-01-restart-15s-voice-v03/*.mp3`
- Create: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-v03.json`
- Create: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-v03.json`

**Interfaces:**
- Consumes: Task 2 的免费预览和用户对“4 次豆包 TTS 调用”的当次明确确认。
- Produces: 四段源 MP3、裁切后的有效音频、自然尾试听、精确 15 秒试听、可复核哈希和字幕时间轴。

- [ ] **Step 1: 展示付费调用预览并暂停**

再次运行只读预览，向用户逐句展示文本、音色、`speech_rate=0`、输出目录和“预计 4 次调用”。没有用户在此节点的明确确认，不得执行 `--generate`。

- [ ] **Step 2: 只生成一次四段 v03 音频**

Run: `python3 scripts/generate_episode_audio.py --episode yiwu-yiyuan-qiancheng-01-restart-15s --generate`

交互确认文字使用脚本预览给出的精确短语。Expected: `voice-v03` 目录新增四个 24 kHz 单声道 MP3 和 `audio-metadata.json`；v01、v02 均未被覆盖。

- [ ] **Step 3: 统一裁切并测量有效语音**

四段使用同一静音裁切规则：

```text
silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,
areverse,
silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,
areverse
```

用 FFprobe 记录原始时长和裁切后时长，用 `shasum -a 256` 记录源 MP3 哈希。按 `[0, 650, 750, 850]` 毫秒排布，不修改单段语速和有效时长。

- [ ] **Step 4: 写入 v03 时序和字幕**

`audio-timing-v03.json` 包含每段 `source_duration_ms`、`trimmed_duration_ms`、`gap_before_ms`、`start_ms`、`end_ms`、`sha256`，以及整体 `voice_start_ms`、`voice_end_ms`、`max_gap_ms`、`natural_preview_duration_ms` 和门禁状态。

`subtitle-plan-v03.json` 只含四项；前三项 `kind="modern"`，第四项 `kind="poem"` 且 `attribution="唐·李白《行路难·其一》"`。字幕起止直接取自实测有效语音，不能使用估算值。

- [ ] **Step 5: 合成两份试听但不改变朗诵**

先合成“自然尾试听”，在古诗自然尾音结束后收束。仅当总长不超过 15 秒时，再补尾部静音生成精确 15 秒 WAV；把补静音毫秒数写入时序文件。不得使用 `atempo`、重采样变速、截断或额外段间静音。

- [ ] **Step 6: 执行自动门禁并停止自动重试**

Run: `python3 scripts/validate_yi_wu_yi_yuan.py --subtitle-plan episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-v03.json`

结果处理固定为：

- 最后一字 `14.000—14.800 秒`，且最大气口不超过 900 毫秒：自动时序通过，进入人工试听。
- 最后一字 `14.801—15.000 秒`：提示超出目标，进入人工判断，不自动判成功。
- 最后一字 `<14.000 秒`：覆盖不足；尾部补静音不改变失败结论。
- 最后一字 `>15.000 秒`：超时；不得加速或截断。
- 任一气口 `>900 毫秒`：停顿超门禁；不得靠缩短文字外的静音伪造通过。

无论何种失败，都只报告实测结果并停止。不得自动改稿、自动重试或产生额外 TTS 调用。

- [ ] **Step 7: 交付试听并进行人工门禁**

向用户提供四段源语音、自然尾试听和精确 15 秒试听的本地播放入口，并报告：四段有效时长、三个气口、最后一字时刻、尾部自然余量或补静音量。人工验收重点为：句号是否真正停住、是否赶字、是否像广告祝福、现代话到古诗是否自然、诗句是否有比赛朗诵腔。

- [ ] **Step 8: 仅按真实结果提交证据**

无论通过或失败，时序 JSON 必须如实记录 `automatic_gate` 和 `human_gate`，不得把未试听或人工拒绝写成通过。用户给出人工结论后再执行：

```bash
git add episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-v03.json \
  episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-v03.json \
  episodes/yiwu-yiyuan-qiancheng-01-restart-15s/README.md
git commit -m "记录重新出发第三版朗诵结果"
```

### Task 4: 语音通过后再恢复诗舞设计

**Files:**
- Modify only after approval: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md`
- Modify only after approval: `docs/superpowers/plans/2026-08-31-yi-wu-yi-yuan-qiancheng.md`

- [ ] **Step 1: 等待双重验收**

只有 `automatic_gate` 通过且用户明确确认整体听感自然，才进入视频设计。仅“正好 15 秒”或仅“听起来不错”都不能替代双重门禁。

- [ ] **Step 2: 以 v03 实测节点重做同步**

废弃旧 `prompt.md` 的 v01/v02 节奏映射，用四段真实起止点重新安排舞蹈动作、音乐重音、镜头变化与字幕显隐；朗诵必须从第一帧延续至古诗收束。

- [ ] **Step 3: 单独设计并审批视频生成**

修订总体实施计划后，先向用户展示完整的 Seedance 视频调用预览、费用风险和输入资产；只有再次得到明确确认，才允许生成视频。

---

## Definition of Done

- 合同、测试和 v03 清单逐字一致，固定为 52 字、正常语速、三个完整停顿。
- v01、v02 证据完整保留；v03 使用独立目录和版本文件。
- 没有在用户确认前产生付费 TTS 调用，也没有生成任何视频。
- v03 最后一字、最大气口和人工听感均有真实记录，不用补静音掩盖覆盖不足。
- 只有双重验收通过，才把 v03 时间轴交给舞蹈、音乐、画面和字幕同步设计。
