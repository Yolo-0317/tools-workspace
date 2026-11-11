# 《惊涛》10秒正式字幕版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为《惊涛》无字幕配音试听版加入一段横排对白和三段按真实语音停顿切换的竖排诗句，输出1080×1920正式字幕版。

**Architecture:** 复用现有`render_story_subtitle_cards.swift`将字幕清单渲染成四张720×1280透明PNG；构建脚本把已确认的配音试听版放大到1080×1920，并按四个时间区间叠加字幕卡。音频直接复制，避免再次混音或改变TTS与原声关系。

**Tech Stack:** JSON、Swift/AppKit、Zsh、FFmpeg、FFprobe

## Global Constraints

- 阿砚字幕为“哇，这浪一拍，江水都成雪啦！”，0.000—3.648秒底部单行横排。
- 3.950—4.391秒不显示诗句。
- “乱石穿空”在4.391—5.676秒左侧竖排，并显示小字题署“宋·苏轼”。
- “惊涛拍岸”在5.676—6.851秒左侧竖排。
- “卷起千堆雪”在6.851—8.606秒左侧竖排。
- 8.606—10.100秒无字幕。
- 输出为`exports/jingtao-subtitled-v01.mp4`，1080×1920、24fps、10.100秒。
- 音频直接复用`exports/jingtao-voiced-v01.mp4`中的48kHz双声道AAC，不重新生成或变速。

---

### Task 1: 建立正式字幕版媒体回归测试

**Files:**
- Create: `tests/test_jingtao_subtitled_final.sh`
- Test: `tests/test_jingtao_subtitled_final.sh`

**Interfaces:**
- Consumes: 正式字幕版输出规格。
- Produces: 对构建流程、字幕卡和最终媒体规格的自动门禁。

- [x] **Step 1: 写入失败测试**

测试执行`build_jingtao_subtitled_final.sh`，要求四张透明字幕卡和最终MP4存在；用FFprobe检查H.264、1080×1920、24fps、AAC、48kHz双声道、10.100秒及无独立字幕流。

- [x] **Step 2: 运行测试并确认正确失败**

Run: `zsh tests/test_jingtao_subtitled_final.sh`
Expected: FAIL，提示缺少正式字幕版构建脚本。

### Task 2: 生成字幕卡并合成正式视频

**Files:**
- Create: `episodes/jingtao/subtitle-plan.json`
- Create: `scripts/build_jingtao_subtitled_final.sh`
- Create: `assets/subtitles/jingtao/01-ayan-dialogue.png`
- Create: `assets/subtitles/jingtao/02-poem-one.png`
- Create: `assets/subtitles/jingtao/03-poem-two.png`
- Create: `assets/subtitles/jingtao/04-poem-three.png`
- Create: `exports/jingtao-subtitled-v01.mp4`
- Test: `tests/test_jingtao_subtitled_final.sh`

**Interfaces:**
- Consumes: `exports/jingtao-voiced-v01.mp4`和现有透明字幕卡渲染器。
- Produces: 带烧录字幕的1080×1920正式视频。

- [x] **Step 1: 写入字幕清单**

清单包含一项`dialogue`和三项`poem`；第一项诗句题署为“宋·苏轼”，其余题署为空。诗句文本不含标点，确保每张卡只有一列竖排文字。

- [x] **Step 2: 写入构建脚本**

脚本先用Swift渲染四张透明卡，再用FFmpeg将试听版放大为1080×1920；对白卡整体向下偏移120像素后在0.000—3.648秒叠加，三张诗句卡分别在4.391—5.676、5.676—6.851、6.851—8.606秒叠加；音频流直接复制。

- [x] **Step 3: 生成正式字幕版**

Run: `zsh scripts/build_jingtao_subtitled_final.sh`
Expected: 创建四张字幕卡与`exports/jingtao-subtitled-v01.mp4`，命令退出码为0。

- [x] **Step 4: 运行回归测试**

Run: `zsh tests/test_jingtao_subtitled_final.sh`
Expected: `PASS: Jingtao subtitled final is ready`

- [x] **Step 5: 视觉抽检**

分别截取1.5、4.8、6.1、7.4和9.3秒画面组成联系表，确认对白未遮脸、诗句位于左侧、题署弱于诗句、结尾无字幕。

### Task 3: 登记正式字幕版并完成验收

**Files:**
- Modify: `episodes/jingtao/README.md`
- Modify: `assets/inventory.csv`
- Test: `tests/test_jingtao_subtitled_final.sh`

**Interfaces:**
- Consumes: 已完成视觉抽检和媒体探测的字幕版。
- Produces: 单集事实源和资产台账中的最终成片记录。

- [x] **Step 1: 更新单集状态**

记录正式字幕版路径、1080×1920规格、横排对白、分段竖排诗句、8.606秒退场和音频沿用试听版。

- [x] **Step 2: 登记资产**

在`assets/inventory.csv`追加`jingtao-subtitled-v01`，状态为`final`，来源为本地FFmpeg与Swift合成，权利说明为项目原创资产。

- [x] **Step 3: 运行最终验证**

Run: `zsh tests/test_jingtao_subtitled_final.sh && git diff --check`
Expected: 测试PASS，差异检查无输出，命令退出码为0。

- [x] **Step 4: 提交实现**

Run: `git add zhixia-feihualing/episodes/jingtao/subtitle-plan.json zhixia-feihualing/scripts/build_jingtao_subtitled_final.sh zhixia-feihualing/tests/test_jingtao_subtitled_final.sh zhixia-feihualing/episodes/jingtao/README.md zhixia-feihualing/assets/inventory.csv zhixia-feihualing/docs/superpowers/plans/2026-08-29-jingtao-subtitled-final.md && git commit -m "制作惊涛正式字幕版"`
Expected: 只提交《惊涛》字幕版相关文本与脚本；忽略规则覆盖的PNG与MP4保留在本地资产目录。
