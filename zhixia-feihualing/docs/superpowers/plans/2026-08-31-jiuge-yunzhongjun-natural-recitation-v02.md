# 《九歌·云中君》自然慢诵 v02 修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 废弃失去自然人声感的 0.5 倍速 v01，以四段正常声速原生人声和自然气口制作《云中君》v02 无字幕试听版与正式字幕版。

**Architecture:** 将两句诗拆成四个独立 TTS 短段，全部固定 `speech_rate=0`，逐段测量真实首尾静音后直接排入 15.093 秒时间轴，构建阶段不使用任何变速或时间拉伸。复用两张完整诗句字幕卡和原片轻度音乐避让，输出独立 v02 文件；测试同时锁定正常语速参数、禁止变速、媒体规格与两版音轨一致性。

**Tech Stack:** JSON、Python `unittest`、豆包 TTS、Zsh、FFmpeg/FFprobe、Swift/AppKit、jq、Git。

## Global Constraints

- v01 配音和成片判定为不可用失败样本，不覆盖、不发布。
- v02 四段固定为“灵皇皇兮”“既降”“猋远举兮”“云中”，字幕仍显示两句完整原文。
- 四段均使用 `speech_rate=0`；禁止 `speech_rate=-50`、0.5 倍速及任何低于正常速度的合成参数。
- 构建脚本禁止 `atempo`、变调、时间拉伸和为了填满字幕窗而拉长音素。
- 舒缓感只来自自然吐字、四段之间约 0.700—1.000 秒气口、两组之间留白和句尾余韵。
- “猋”必须读作 `biāo`，由 TTS 上下文锁定并交由用户试听确认。
- 第一组约 1.000 秒进入，第二组约 7.700 秒进入；具体后段起点依据正常声速音频真实时长确定。
- 字幕仍为右侧“灵皇皇兮既降”加题署、左侧“猋远举兮云中”，不遮挡人物和右下角标识。
- 输出 `exports/jiuge-yunzhongjun-15s-voiced-v02.mp4` 与 `exports/jiuge-yunzhongjun-15s-subtitled-v02.mp4`。

---

### Task 1: 建立四段正常声速配音契约

**Files:**
- Modify: `zhixia-feihualing/tests/test_yunzhongjun_recitation_manifest.py`
- Modify: `zhixia-feihualing/episodes/jiuge-yunzhongjun-15s/voice-lines.json`

**Interfaces:**
- Consumes: 已确认的四段文本、栀夏固定音色和现有 TTS 清单格式。
- Produces: `audio_slug=jiuge-yunzhongjun-15s-natural-v02` 的四段正常声速生成计划。

- [ ] **Step 1: 先修改测试要求四段自然人声**

测试固定断言四段文本、四项 `speech_rate=0`、四项 `revision=1`、角色均为 `zhixia`；字幕清单仍只有两项完整诗句。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd zhixia-feihualing && python3 -m unittest tests.test_yunzhongjun_recitation_manifest -v`

Expected: FAIL，显示当前清单仍是两段慢速 v01/v04 方案。

- [ ] **Step 3: 写入四段正常声速清单**

清单使用 `format=one-poem-story`、`audio_slug=jiuge-yunzhongjun-15s-natural-v02`。四项 ID 为 `01-zhixia-line-one-a`、`02-zhixia-line-one-b`、`03-zhixia-line-two-a`、`04-zhixia-line-two-b`；文本依次为“灵皇皇兮。”“既降。”“猋远举兮。”“云中。”，全部 `speech_rate=0`、`revision=1`。上下文逐项要求正常人声、不刻意放慢、不拖字、不吟唱；第三项明确“猋读 biāo”。

- [ ] **Step 4: 运行测试和付费预览**

Run:

```zsh
cd zhixia-feihualing
python3 -m unittest tests.test_yunzhongjun_recitation_manifest -v
python3 scripts/generate_episode_audio.py --episode jiuge-yunzhongjun-15s
```

Expected: 测试 PASS；预览显示 4 句、4 次调用、自然人声 v02 输出目录。

### Task 2: 生成并测量四段自然人声

**Files:**
- Generate: `zhixia-feihualing/assets/audio/jiuge-yunzhongjun-15s-natural-v02/*.mp3`
- Inspect: `zhixia-feihualing/assets/audio/jiuge-yunzhongjun-15s-natural-v02/audio-metadata.json`

**Interfaces:**
- Consumes: Task 1 四段清单与项目豆包凭证。
- Produces: 四段不经变速即可直接排入时间轴的自然人声 MP3。

- [ ] **Step 1: 生成四段音频**

Run: `cd zhixia-feihualing && python3 scripts/generate_episode_audio.py --episode jiuge-yunzhongjun-15s --generate`

交互确认固定为 `GENERATE jiuge-yunzhongjun-15s`，预计调用 4 次。

- [ ] **Step 2: 测量有效语音边界**

对四条 MP3 运行 `silencedetect=noise=-42dB:d=0.05`，记录每段不截字的 `atrim start/end`。构建时只允许裁掉头尾静音，禁止添加 `atempo`。

- [ ] **Step 3: 计算自然时间轴**

第一段从 1.000 秒开始；第二段起点等于第一段实际有效结束时间加 0.700—1.000 秒。第三段从 7.700 秒开始；第四段起点等于第三段实际有效结束时间加 0.700—1.000 秒。四段均须在 13.300 秒前结束。

### Task 3: 构建并验证 v02 成片

**Files:**
- Modify: `zhixia-feihualing/tests/test_yunzhongjun_15s_final.sh`
- Modify: `zhixia-feihualing/scripts/build_yunzhongjun_15s_final.sh`
- Generate: `zhixia-feihualing/exports/jiuge-yunzhongjun-15s-voiced-v02.mp4`
- Generate: `zhixia-feihualing/exports/jiuge-yunzhongjun-15s-subtitled-v02.mp4`

**Interfaces:**
- Consumes: Task 2 的四段实际裁切边界与延迟、现有两张字幕卡。
- Produces: 共享同一自然人声音轨的两份 v02 成片。

- [ ] **Step 1: 先修改成片门禁**

门禁改为要求四段自然人声 MP3、v02 两份输出和两张字幕卡；断言构建脚本不包含 `atempo`、`speech_rate=-50` 或 v01/v03/v04 慢速音频名。继续验证 H.264、1080×1920、24 fps、15.0—15.2 秒、AAC、48 kHz、双声道、完整解码与两版音轨哈希一致。

- [ ] **Step 2: 运行门禁确认失败**

Run: `cd zhixia-feihualing && zsh tests/test_yunzhongjun_15s_final.sh`

Expected: FAIL，提示缺少 v02 构建结果或仍命中旧变速链路。

- [ ] **Step 3: 修改构建脚本**

替换为四段正常声速音频；每段只做 `atrim`、`asetpts`、淡入淡出、48 kHz 双声道规范化和 `adelay`，不得出现 `atempo`。人声处理、约 3 dB 音乐避让、视频高清路径和两张字幕卡样式保持不变；输出文件名改为 v02。

- [ ] **Step 4: 构建并运行门禁**

Run:

```zsh
cd zhixia-feihualing
zsh scripts/build_yunzhongjun_15s_final.sh
zsh tests/test_yunzhongjun_15s_final.sh
```

Expected: `PASS: Yunzhongjun natural recitation v02 finals are ready`。

### Task 4: 视觉复核、规则固化与交付

**Files:**
- Modify: `zhixia-feihualing/episodes/jiuge-yunzhongjun-15s/qa-notes.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`
- Modify: `zhixia-feihualing/docs/jiuge-dance-research-and-design.md`

**Interfaces:**
- Consumes: Task 3 v02 两份成片和用户对 v01 的失败反馈。
- Produces: 可追溯失败原因、自然慢诵门禁和 v02 交付记录。

- [ ] **Step 1: 抽帧检查两张字幕**

在第一、第二字幕时间窗各抽一帧，确认版式与 v01 一致且“猋”正常显示，不遮挡安全区。

- [ ] **Step 2: 运行最终验证**

Run:

```zsh
cd zhixia-feihualing
python3 -m unittest tests.test_yunzhongjun_recitation_manifest tests.test_zhixia_tts_manifest tests.test_zhixia_tts_client tests.test_zhixia_tts_pipeline -q
zsh tests/test_yunzhongjun_15s_final.sh
ffmpeg -v error -i exports/jiuge-yunzhongjun-15s-subtitled-v02.mp4 -f null -
```

- [ ] **Step 3: 固化全局门禁**

记录 v01 因 `speech_rate=-50` 叠加后期变速而失去自然人声感，永久禁止文化诗舞使用 0.5 倍速或强拉伸。短句优先正常声速分段录制和自然气口，不再用 82%—90% 占窗比例强迫拉长人声。

- [ ] **Step 4: 更新单片 QA 并提交**

记录四段实际边界、自然气口、无变速证据、两份 v02 路径、媒体规格和试听门禁。只提交本任务相关文件，提交前确认暂存区没有其他文件。

- [ ] **Step 5: 交付**

最终优先提供 v02 无字幕试听版，提醒用户确认自然人声、整体舒缓感与“猋（biāo）”读音；正式字幕版使用同一音轨同步提供。v01 明确不再使用。
