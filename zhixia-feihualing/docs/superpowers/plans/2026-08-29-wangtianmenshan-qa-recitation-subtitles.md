# 《望天门山》偏差优化与朗诵字幕 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 固化本集四项生成偏差，并将已验收原片制作成带栀夏全诗朗诵和竖排字幕的正式成片。

**Architecture:** 通用规则和本集复盘记录生成偏差；原片归档后，通过现有 TTS 清单生成四句音频，按有效语音裁切并生成竖排透明字幕卡，最后由 FFmpeg 完成画面放大、字幕叠加、背景压低和人声混合。

**Tech Stack:** Markdown、CSV、JSON、Python TTS、Swift/AppKit、FFmpeg、FFprobe、Zsh、jq

## Global Constraints

- 不重新生成、裁切或重绘当前 Seedance 画面。
- 栀夏独诵全诗，四句间至少约 0.7 秒留白，第四句在 14.6 秒前结束。
- 首句附“唐·李白”，字幕避开栀夏、阿砚和孤帆。
- 输出 1080×1920、24fps、H.264/AAC、15.0—15.2 秒。
- 偏差优化必须进入通用规则、本集复盘和舞蹈台账。

---

### Task 1: 偏差规则与失败门禁

**Files:**
- Modify: `docs/zhixia-poetry-dance-composer.md`
- Modify: `docs/realistic-visual-style.md`
- Modify: `operations/dance-design-history.csv`
- Create: `episodes/wangtianmenshan-15s/qa-notes.md`
- Create: `tests/test_wangtianmenshan_15s_final.sh`
- Create: `episodes/wangtianmenshan-15s/assets/video/content-seedance-v01.mp4`

**Interfaces:** Consumes the accepted source video and QA findings; produces reusable rules, one accepted ledger row and a final-output gate.

- [ ] Write a failing shell test that requires the source video, four-line voice manifest, subtitle plan, executable build script and final H.264/AAC 1080×1920 output.
- [ ] Run `zsh tests/test_wangtianmenshan_15s_final.sh`; expect failure for missing `voice-lines.json`.
- [ ] Add four exact rules: two continuing body changes in the final three seconds; delayed reveal objects cannot be fully established at opening; replace unnecessary “回身” with stepped weight-shift facing change; re-anchor Ayan after occlusion or distance changes.
- [ ] Copy the source video to the episode, record QA notes, and update the existing CSV row to `accepted` with actual deviations.

### Task 2: Voice, subtitles and final build

**Files:**
- Create: `episodes/wangtianmenshan-15s/voice-lines.json`
- Create: `assets/audio/wangtianmenshan-15s-paced-v01/*.mp3`
- Create: `episodes/wangtianmenshan-15s/subtitle-plan.json`
- Create: `episodes/wangtianmenshan-15s/subtitles-wangtianmenshan-15s.json`
- Create: `scripts/build_wangtianmenshan_15s_final.sh`
- Create: `assets/subtitles/wangtianmenshan-15s/*.png`
- Create: `exports/wangtianmenshan-15s-subtitled-v01.mp4`
- Modify: `episodes/wangtianmenshan-15s/README.md`

**Interfaces:** Consumes the archived source and four TTS MP3s; produces the subtitle timing, reusable build script and final video.

- [ ] Create a four-line `zhixia` manifest for “天门中断楚江开。/碧水东流至此回。/两岸青山相对出。/孤帆一片日边来。” with fixed youthful voice contexts and 900 ms target gaps.
- [ ] Run `python3 scripts/generate_episode_audio.py --episode wangtianmenshan-15s --generate`, measure each MP3 with `silencedetect`, and derive real start/end windows inside 0.25—14.6 seconds.
- [ ] Create the four-record subtitle plan with first attribution `唐·李白`; render cards with `render_story_subtitle_cards.swift`.
- [ ] Build the final video with Lanczos scaling, left-safe subtitle overlays, per-line voice timing, sidechain background reduction, loudness normalization and peak limiting.
- [ ] Run `zsh tests/test_wangtianmenshan_15s_final.sh`, inspect a contact sheet, check audio peaks and run all related rule tests.
- [ ] Commit only this episode's rules, assets, scripts, tests and plan with Chinese commit messages.
