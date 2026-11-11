# 《惊涛》10秒无字幕配音试听版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将两段已确认TTS按真实时长混入《惊涛》Seedance原片，输出10.100秒无字幕配音试听版。

**Architecture:** 新增一个只负责《惊涛》试听版的FFmpeg构建脚本，以用户确认的原片和项目内两段TTS为输入；新增静态与媒体探测测试，先验证脚本参数，再验证实际输出。画面流直接复制，原声在人声区间压低约5dB，人声保持自然速度。

**Tech Stack:** Zsh、FFmpeg、FFprobe、ripgrep

## Global Constraints

- 原片固定为`/Users/huan.yu/Downloads/f549d3fe-072c-4f76-a19a-804f29361f24.mp4`。
- 阿砚从0.000秒开始，时长3.648秒。
- 栀夏从3.950秒开始，时长4.656秒。
- TTS不得使用`atempo`变速。
- 原片声音只在人声区间以`0.562341`系数压低约5dB。
- 视频流直接复制，不加字幕、不缩放、不裁切、不改变24fps帧率。
- 输出固定为`exports/jingtao-voiced-v01.mp4`，时长10.100秒。

---

### Task 1: 建立试听版回归测试

**Files:**
- Create: `tests/test_jingtao_voiced_preview.sh`
- Test: `tests/test_jingtao_voiced_preview.sh`

**Interfaces:**
- Consumes: 设计稿中的输入路径、时间轴、混音和输出规格。
- Produces: 对构建脚本和最终MP4的自动门禁。

- [ ] **Step 1: 写入失败测试**

测试先检查`build_jingtao_voiced_preview.sh`存在且包含两段`adelay`、原声压低系数、`loudnorm`、`-c:v copy`、10.100秒输出和无`atempo`；输出文件存在时再用FFprobe检查H.264、496×864、24fps、AAC、48kHz双声道和10.100秒。

- [ ] **Step 2: 运行测试并确认正确失败**

Run: `zsh tests/test_jingtao_voiced_preview.sh`
Expected: FAIL，提示缺少`build_jingtao_voiced_preview.sh`。

### Task 2: 构建无字幕配音试听版

**Files:**
- Create: `scripts/build_jingtao_voiced_preview.sh`
- Create: `exports/jingtao-voiced-v01.mp4`
- Test: `tests/test_jingtao_voiced_preview.sh`

**Interfaces:**
- Consumes: 原片、`assets/audio/jingtao/01-ayan-ayan-dialogue.mp3`和`02-zhixia-zhixia-poem.mp3`。
- Produces: 一支10.100秒、原画面直拷贝、48kHz双声道混音的试听视频。

- [ ] **Step 1: 写入最小构建脚本**

脚本使用`set -euo pipefail`，验证三个输入文件存在；FFmpeg滤镜将原声在`0—3.648`和`3.950—8.606`秒压低至`0.562341`，两段TTS分别经过48kHz重采样、双声道格式转换和`loudnorm=I=-18:TP=-2:LRA=7`，第二段使用`adelay=3950|3950`，三路混合后以`alimiter=limit=0.891251:level=false`限制峰值。

- [ ] **Step 2: 生成视频**

Run: `zsh scripts/build_jingtao_voiced_preview.sh`
Expected: 创建`exports/jingtao-voiced-v01.mp4`，命令退出码为0。

- [ ] **Step 3: 运行回归测试**

Run: `zsh tests/test_jingtao_voiced_preview.sh`
Expected: `PASS: Jingtao voiced preview is ready`

- [ ] **Step 4: 检查音频峰值**

Run: `ffmpeg -hide_banner -i exports/jingtao-voiced-v01.mp4 -map 0:a:0 -af volumedetect -f null -`
Expected: `max_volume`小于或等于`0.0 dB`，没有削波错误。

### Task 3: 登记试听版并完成验收

**Files:**
- Modify: `episodes/jingtao/README.md`
- Modify: `assets/inventory.csv`
- Test: `tests/test_jingtao_voiced_preview.sh`

**Interfaces:**
- Consumes: 已通过媒体探测的试听视频。
- Produces: 单集状态和资产台账中的可追溯记录。

- [ ] **Step 1: 更新单集状态**

记录试听版路径、画面与音频规格、两段实际时间轴、原声压低约5dB、无字幕和自然语速。

- [ ] **Step 2: 登记资产**

在`assets/inventory.csv`追加`jingtao-voiced-v01`，来源为本地FFmpeg合成，权利说明为项目原创资产，状态为`available`。

- [ ] **Step 3: 运行最终验证**

Run: `zsh tests/test_jingtao_voiced_preview.sh && git diff --check`
Expected: 测试PASS，差异检查无输出，命令退出码为0。

- [ ] **Step 4: 提交本次实现**

Run: `git add zhixia-feihualing/scripts/build_jingtao_voiced_preview.sh zhixia-feihualing/tests/test_jingtao_voiced_preview.sh zhixia-feihualing/episodes/jingtao/README.md zhixia-feihualing/assets/inventory.csv zhixia-feihualing/exports/jingtao-voiced-v01.mp4 zhixia-feihualing/docs/superpowers/plans/2026-08-29-jingtao-voiced-preview.md && git commit -m "合成惊涛无字幕配音试听版"`
Expected: 仅提交《惊涛》试听版相关文件，保留工作区其他改动。
