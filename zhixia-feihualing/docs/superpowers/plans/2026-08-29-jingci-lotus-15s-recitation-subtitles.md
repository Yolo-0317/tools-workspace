# 《晓出净慈寺送林子方》15 秒朗诵字幕 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已确认的 15.093 秒 Seedance 成片加入栀夏四句全诗朗诵、随真实语音出现的竖排字幕，并输出可发布的 1080×1920 成片。

**Architecture:** 复用项目豆包 TTS 清单生成四句独立音频，按实际有效语音区间去除首尾静音并排入 15 秒时间轴；复用透明 PNG 字幕卡渲染器生成四张竖排诗句卡，再用单个 FFmpeg 构建脚本完成画面放大、字幕叠加、原声压低、人声混合与响度保护。独立 Zsh 门禁验证清单、字幕时间轴、构建产物的时长、分辨率和音视频编码。

**Tech Stack:** JSON、Python 豆包 TTS、Swift/AppKit 字幕渲染、FFmpeg、FFprobe、Zsh、jq

## Global Constraints

- 栀夏独诵杨万里《晓出净慈寺送林子方》四句，不增加阿砚对白、标题或作者口播。
- 四句之间保留自然留白，第一句从片头开始，第四句接近片尾结束，使朗诵覆盖完整 15 秒。
- 字幕使用现有米白色行楷竖排诗句模板，逐句随真实有效语音出现；首句附“宋·杨万里”题署，其余句不重复题署。
- 保留 Seedance 原音乐与环境声，人声区间将原声压低约 5 dB，不整体替换原声。
- 输出 1080×1920、24fps、H.264/AAC、15.0—15.2 秒，不修改原视频 AI 生成标识。
- 只处理本集文件，不带入工作区中其他未提交资产。

---

### Task 1: 建立本集后期成片失败门禁

**Files:**
- Create: `tests/test_jingci_lotus_15s_final.sh`
- Test: `episodes/jingci-lotus-15s/voice-lines.json`
- Test: `episodes/jingci-lotus-15s/subtitle-plan.json`
- Test: `scripts/build_jingci_lotus_15s_final.sh`
- Test: `exports/jingci-lotus-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: 四句诗文、字幕时间轴、构建脚本和最终成片。
- Produces: 缺少任一输入、四句顺序错误、时间轴越界、构建失败或成片规格错误时退出非零的门禁。

- [x] **Step 1: 写入失败门禁**

门禁检查四句文本恰为“毕竟西湖六月中”“风光不与四时同”“接天莲叶无穷碧”“映日荷花别样红”，字幕起止单调递增、相互不重叠、第一句在 0.5 秒内开始、第四句在 14.0—15.1 秒结束，并在运行构建脚本后检查 1080×1920、24fps、H.264/AAC 和 15.0—15.2 秒时长。

- [x] **Step 2: 运行门禁确认红灯**

Run: `zsh tests/test_jingci_lotus_15s_final.sh`

Expected: FAIL，首先报告缺少本集可执行构建脚本或字幕计划。

### Task 2: 生成四句栀夏朗诵

**Files:**
- Create: `episodes/jingci-lotus-15s/voice-lines.json`
- Create: `assets/audio/jingci-lotus-15s-paced-v01/*.mp3`
- Create: `assets/audio/jingci-lotus-15s-paced-v01/audio-metadata.json`

**Interfaces:**
- Consumes: 固定 `zhixia` 声音配置和四句诗文。
- Produces: 四个独立 MP3 音频及生成元数据，供混音脚本按句裁切。

- [x] **Step 1: 写入配音清单**

四句均使用 `zhixia`，语境依次为西湖六月开篇、四时不同的发现、接天碧叶的展开、映日红荷的明亮高潮；固定要求清透自然、书卷气、非播音腔、不念标题作者。

- [x] **Step 2: 预览生成计划**

Run: `python3 scripts/generate_episode_audio.py --episode jingci-lotus-15s`

Expected: 四句待生成、四次 TTS 调用、输出目录为 `assets/audio/jingci-lotus-15s-paced-v01`。

- [x] **Step 3: 生成并测量音频**

Run: `python3 scripts/generate_episode_audio.py --episode jingci-lotus-15s --generate`

输入确认文字：`GENERATE jingci-lotus-15s`

Expected: 四句 MP3 和 `audio-metadata.json` 生成完成；用 FFmpeg `silencedetect` 获取每句实际有效语音首尾位置。

### Task 3: 编排字幕时间轴并构建成片

**Files:**
- Create: `episodes/jingci-lotus-15s/subtitle-plan.json`
- Create: `episodes/jingci-lotus-15s/subtitles-jingci-lotus-15s.json`
- Create: `scripts/build_jingci_lotus_15s_final.sh`
- Create: `assets/subtitles/jingci-lotus-15s/*.png`
- Create: `exports/jingci-lotus-15s-subtitled-v01.mp4`
- Modify: `episodes/jingci-lotus-15s/README.md`

**Interfaces:**
- Consumes: 源视频、四句 MP3、实际语音有效区间和透明字幕卡渲染器。
- Produces: 固定可重跑的混音字幕脚本、四张字幕卡和最终成片。

- [x] **Step 1: 写入真实时间轴**

以约 0.2、4.1、8.1、12.1 秒作为四句入点，根据有效语音时长微调语速，使每句自然完整，句间至少保留 0.7 秒留白，第四句在 14.0—15.0 秒之间结束。字幕起止与处理后的有效语音严格一致。

- [x] **Step 2: 写入构建脚本**

脚本检查源视频、四句音频、字幕计划与渲染器，渲染四张透明字幕卡；将源画面升格为 1080×1920/24fps，按时间轴叠加字幕，并在人声区间将原声降至约 `0.562341` 后与 `-18 LUFS` 人声混合，最终以限制器保护峰值。

- [x] **Step 3: 运行门禁确认绿灯**

Run: `zsh tests/test_jingci_lotus_15s_final.sh`

Expected: `PASS: Jingci lotus 15s recitation mix and burned subtitles are ready`

- [x] **Step 4: 视觉抽帧核对**

从四句字幕区间各抽一帧，确认竖排字幕没有遮挡栀夏面部、阿砚和关键荷花；同时核对末句字幕在片尾前完整退场或自然保持至朗诵结束。

- [x] **Step 5: 更新单集状态并提交**

README 记录源视频、四句时间轴、最终成片路径和技术规格；只提交本集清单、构建脚本、测试、计划和必要资产索引，不提交本地密钥或其他未关联修改。
