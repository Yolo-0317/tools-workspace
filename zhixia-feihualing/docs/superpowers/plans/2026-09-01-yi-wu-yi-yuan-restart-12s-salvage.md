# 一舞一愿·重新出发 12 秒挽救版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户提供的 15.09 秒仙侠舞蹈视频裁去前 3 秒，配上重新生成的三句自然朗诵和同步字幕，输出约 12.09 秒可发布成片。

**Architecture:** 原视频先复制到 episode 本地素材目录，再通过 FFmpeg 从 3.000 秒开始重编码为 1080×1920、24fps。三句朗诵由既有豆包 TTS 管线按固定栀夏音色分别生成，以实测有效时长排定停顿和字幕；最终使用侧链压低原视频音乐，叠加唯一人声与透明字幕卡。

**Tech Stack:** Python 3、豆包 TTS、FFmpeg/FFprobe、Swift/AppKit 字幕卡渲染、JSON、zsh、Git。

## Global Constraints

- 不重新调用 Seedance，不改变现有 3.00 秒之后的舞蹈内容与播放速度。
- 精确删除原片 0.00—3.00 秒，输出时长必须在 12.00—12.15 秒。
- 朗诵固定为三句：“重新出发，或许并不轻松。”“愿你所盼有期，每一步都算数。”“长风破浪会有时，直挂云帆济沧海。”
- 固定使用栀夏现有豆包音色与 `speech_rate=0`，不得通过加速、变调、截字或拖腔硬塞时长。
- 第一句从 0.00 秒开始；两处句间停顿分别不少于 0.55 秒和 0.75 秒。
- 三句最迟在 9.90 秒前结束，结尾至少保留 2.00 秒无朗诵画面。
- 字幕逐句同步；两句现代话使用横排字幕，古诗使用竖排字幕与“唐·李白《行路难·其一》”署名。
- 原视频器乐为底层音乐，新朗诵是唯一人声。
- 不修改或提交工作区中无关的现有改动。

---

### Task 1: 建立 12 秒配音清单并验证预览

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines-12s-v01.json`
- Reference: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines.json`
- Test: `zhixia-feihualing/tests/test_generate_episode_audio.py`

**Interfaces:**
- Consumes: 已确认的三句朗诵、现有栀夏音色配置与 TTS 管线。
- Produces: 三次 TTS 调用的可审计清单，音频目录名固定为 `yiwu-yiyuan-qiancheng-01-restart-12s-voice-v01`。

- [ ] **Step 1: 写入三句配音清单**

  三句的 `speech_rate` 均为 `0`，`revision` 均为 `1`；第二句 `gap_before_ms` 为 `600`，第三句为 `800`。每句 `context_texts` 分别固化平静理解、温柔坚定、清朗打开的情绪要求，并明确“只读给定文本”。

- [ ] **Step 2: 运行管线预览，确认只需三次调用**

  Run:

  ```bash
  python3 scripts/generate_episode_audio.py \
    --episode yiwu-yiyuan-qiancheng-01-restart-15s \
    --manifest episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines-12s-v01.json
  ```

  Expected: 输出三句文本、目标音频目录与“预计产生豆包 TTS 调用：3 次”，且不产生网络调用。

- [ ] **Step 3: 运行相关单元测试**

  Run: `python3 -m unittest tests.test_generate_episode_audio`

  Expected: PASS，0 failures。

- [ ] **Step 4: 提交配音清单**

  ```bash
  git add -- episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines-12s-v01.json
  git commit -m "建立重新出发十二秒配音清单"
  ```

### Task 2: 生成三句朗诵并固化实际时间轴

**Files:**
- Create: `zhixia-feihualing/assets/audio/yiwu-yiyuan-qiancheng-01-restart-12s-voice-v01/*.mp3`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-12s-v01.json`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-12s-v01.json`

**Interfaces:**
- Consumes: Task 1 配音清单与用户已确认的三次外部 TTS 调用授权。
- Produces: 三段原始 MP3、去除首尾静音后的有效时长、最终句间停顿和字幕时间轴。

- [ ] **Step 1: 调用豆包 TTS 三次**

  Run:

  ```bash
  python3 scripts/generate_episode_audio.py \
    --episode yiwu-yiyuan-qiancheng-01-restart-15s \
    --manifest episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines-12s-v01.json \
    --confirm
  ```

  Expected: 三句均生成成功，字幕草稿自动写入 episode 目录。

- [ ] **Step 2: 探测并记录每句有效语音时长**

  使用 FFmpeg `silencedetect` 或现有管线探测数据，按统一首尾静音阈值记录三句有效起止点与有效时长。

- [ ] **Step 3: 计算最终时间轴**

  第一句从 0.000 秒开始；在不改变语速的前提下，使第一处停顿至少 0.550 秒、第二处至少 0.750 秒，并确保第三句结束不晚于 9.900 秒。将结果写入 `audio-timing-12s-v01.json` 与 `subtitle-plan-12s-v01.json`。

- [ ] **Step 4: 人工试听门禁**

  合成一份仅含三句与目标停顿的 12.093 秒试听 WAV。确认无赶读、吞字、断尾、过长首静音或情绪跳变后，才进入成片构建。

### Task 3: 编写可重复构建脚本并生成成片

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/assets/video/content-seedance-xianxia-v01.mp4`
- Create: `zhixia-feihualing/scripts/build_yiwu_yiyuan_restart_12s_final.sh`
- Create: `zhixia-feihualing/assets/subtitles/yiwu-yiyuan-qiancheng-01-restart-12s/*.png`
- Create: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: 用户源视频、Task 2 三句语音、最终时间轴与既有 `render_story_subtitle_cards.swift`。
- Produces: 一条 1080×1920、24fps、约 12.09 秒、含配音和字幕的 H.264/AAC 成片。

- [ ] **Step 1: 非破坏性复制源视频到 episode 素材目录**

  源文件保持不变；项目本地副本命名为 `content-seedance-xianxia-v01.mp4`。

- [ ] **Step 2: 编写构建脚本的输入门禁**

  脚本对源视频、三句 MP3、字幕计划和字幕渲染器逐一执行非空检查；任何输入缺失立即退出。

- [ ] **Step 3: 渲染三张透明字幕卡**

  使用 `render_story_subtitle_cards.swift`；清理时只删除本 episode 字幕目录中的旧 PNG，不操作其他目录。

- [ ] **Step 4: 裁切、混音并叠加字幕**

  FFmpeg 从源视频 `3.000` 秒开始，保留剩余全部时长；画面等比放大并居中裁切为 1080×1920、24fps。三句语音按 Task 2 时间轴延迟混合；原音乐在朗诵期间通过侧链压缩让位，最终进行限幅。字幕卡按同一时间轴淡入淡出。

- [ ] **Step 5: 生成成片**

  Run: `zsh scripts/build_yiwu_yiyuan_restart_12s_final.sh`

  Expected: 输出 `exports/yiwu-yiyuan-qiancheng-01-restart-12s-subtitled-v01.mp4`。

### Task 4: 验证成片并提交可复现文件

**Files:**
- Verify: `zhixia-feihualing/exports/yiwu-yiyuan-qiancheng-01-restart-12s-subtitled-v01.mp4`
- Commit: 配音清单、时间轴、字幕计划、构建脚本；媒体资产按项目忽略规则保留本地，需要版本化时精确强制暂存。

**Interfaces:**
- Consumes: Task 3 成片。
- Produces: 通过时长、流媒体参数、首帧动作、字幕和音频检查的可发布文件。

- [ ] **Step 1: 验证媒体参数**

  Run: `ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,sample_rate,channels -of json exports/yiwu-yiyuan-qiancheng-01-restart-12s-subtitled-v01.mp4`

  Expected: 时长 12.00—12.15 秒；视频 H.264、1080×1920、24fps；音频 AAC、48kHz、双声道。

- [ ] **Step 2: 验证朗诵与尾段门禁**

  核对 `audio-timing-12s-v01.json`：两处停顿达标，第三句不晚于 9.900 秒结束，尾部无朗诵不少于 2.000 秒。

- [ ] **Step 3: 生成首中尾接触表并目视检查**

  抽取新成片 0、2、4、6、8、10、12 秒画面；确认首帧已进入舞蹈，字幕无裁切、无重叠，结尾没有冻结或黑帧。

- [ ] **Step 4: 试听最终成片**

  确认朗诵清晰自然，音乐未盖住人声，句间停顿可感，第三句结束后音乐自然展开，结尾无爆音或硬切。

- [ ] **Step 5: 精确暂存并提交实现文件**

  ```bash
  git add -- \
    episodes/yiwu-yiyuan-qiancheng-01-restart-15s/voice-lines-12s-v01.json \
    episodes/yiwu-yiyuan-qiancheng-01-restart-15s/audio-timing-12s-v01.json \
    episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-12s-v01.json \
    scripts/build_yiwu_yiyuan_restart_12s_final.sh
  git diff --cached --check
  git commit -m "制作重新出发十二秒配音字幕成片"
  ```
