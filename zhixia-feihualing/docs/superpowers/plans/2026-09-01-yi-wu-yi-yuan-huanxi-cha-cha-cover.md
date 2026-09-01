# Heavenly Cha-Cha “欢喜” Cover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one 1080×1920 PNG cover for the confirmed 10-second heavenly cha-cha video, with “欢喜” as the only large title.

**Architecture:** Extract a small set of clean frames from the no-subtitle voiced master, visually select the strongest front-facing dance pose, then render typography deterministically with Swift/AppKit. A shell builder owns frame extraction and output paths; a focused renderer owns crop, tonal treatment, and text layout.

**Tech Stack:** zsh, FFmpeg/ffprobe, Swift, AppKit, CoreText.

## Global Constraints

- Output is exactly 1080×1920 PNG in 9:16.
- Preserve the original face, body, costume, and heavenly-palace scene; do not use generative redraw.
- Main title is exactly `欢喜`; supporting label is exactly `栀夏｜一舞一愿`.
- Do not add a full poem, author attribution, long blessing, sharing prompt, English title, watermark, sticker, block, thick outline, or decorative border.
- Do not modify the existing video, narration, subtitles, or publishing copy.

---

### Task 1: Select and lock the cover frame

**Files:**
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/assets/cover/frame-selection.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/assets/cover/cover-reference-v01.png`

**Interfaces:**
- Consumes: `zhixia-feihualing/exports/yiwu-yiyuan-huanxi-cha-cha-10s-voiced-v01.mp4`.
- Produces: one full-resolution 1080×1920 reference frame and a text record containing its exact timestamp.

- [ ] **Step 1: Extract candidates at strong dance beats**

Run:

```bash
mkdir -p /private/tmp/zhixia-cha-cha-cover-candidates
for t in 0.8 2.5 4.4 5.5 7.5 9.9; do
  ffmpeg -hide_banner -loglevel error -y -ss "$t" -i zhixia-feihualing/exports/yiwu-yiyuan-huanxi-cha-cha-10s-voiced-v01.mp4 -frames:v 1 "/private/tmp/zhixia-cha-cha-cover-candidates/${t}.png"
done
```

Expected: six readable 1080×1920 PNG candidates.

- [ ] **Step 2: Build and inspect a contact sheet**

Run:

```bash
ffmpeg -hide_banner -loglevel error -y -pattern_type glob -i '/private/tmp/zhixia-cha-cha-cover-candidates/*.png' -vf 'scale=270:480,tile=3x2' /private/tmp/zhixia-cha-cha-cover-contact.png
```

Select the frame with a clear front-facing expression, extended limbs, natural proportions, a readable palace axis, and no motion blur or body-part clipping.

- [ ] **Step 3: Persist the selected reference non-destructively**

Copy the selected candidate to:

```text
zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/assets/cover/cover-reference-v01.png
```

Write `frame-selection.md` with the source master, exact timestamp, and the five visual reasons used for selection.

- [ ] **Step 4: Verify the reference**

Run:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height -of default=nw=1 zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/assets/cover/cover-reference-v01.png
```

Expected: `codec_name=png`, `width=1080`, and `height=1920`.

- [ ] **Step 5: Commit the selected reference**

```bash
git add zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/assets/cover/frame-selection.md zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/assets/cover/cover-reference-v01.png
git commit -m "选定天宫恰恰欢喜封面画面"
```

### Task 2: Render and verify the formal cover

**Files:**
- Create: `zhixia-feihualing/tests/test_yiwu_yiyuan_huanxi_cha_cha_cover.sh`
- Create: `zhixia-feihualing/scripts/render_yiwu_yiyuan_huanxi_cha_cha_cover.swift`
- Create: `zhixia-feihualing/scripts/build_yiwu_yiyuan_huanxi_cha_cha_cover.sh`
- Create: `zhixia-feihualing/exports/yiwu-yiyuan-huanxi-cha-cha-10s-cover-v01.png`

**Interfaces:**
- Consumes: `cover-reference-v01.png` from Task 1.
- Produces: a deterministic formal cover at `exports/yiwu-yiyuan-huanxi-cha-cha-10s-cover-v01.png`.

- [ ] **Step 1: Write the failing cover test**

The test must require executable builder and renderer files, run the builder, verify PNG decoding and exact dimensions, and verify both text literals are present in the renderer source:

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
builder="$project_dir/scripts/build_yiwu_yiyuan_huanxi_cha_cha_cover.sh"
renderer="$project_dir/scripts/render_yiwu_yiyuan_huanxi_cha_cha_cover.swift"
output="$project_dir/exports/yiwu-yiyuan-huanxi-cha-cha-10s-cover-v01.png"
[[ -x "$builder" && -x "$renderer" ]]
"$builder" >/dev/null
ffmpeg -v error -i "$output" -f null -
[[ "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$output")" == "1080x1920" ]]
rg -q '欢喜' "$renderer"
rg -q '栀夏｜一舞一愿' "$renderer"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_huanxi_cha_cha_cover.sh
```

Expected: FAIL because the builder and renderer do not exist.

- [ ] **Step 3: Implement the renderer and builder**

The renderer must use AppKit/CoreText, register the local Xingkai and Kaiti fonts, aspect-fill the selected reference without stretching, apply only restrained contrast/brightness treatment, draw `欢喜` in warm-gold Xingkai as the only large title, and draw `栀夏｜一舞一愿` in smaller quiet-gold Kaiti. Position both in a stable negative-space region selected after viewing the reference, with a soft dark shadow and no panel or border.

The builder must validate the reference and renderer, render into a temporary directory with isolated Swift module caches, and atomically produce:

```text
zhixia-feihualing/exports/yiwu-yiyuan-huanxi-cha-cha-10s-cover-v01.png
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
zsh zhixia-feihualing/tests/test_yiwu_yiyuan_huanxi_cha_cha_cover.sh
```

Expected: PASS with a fully decodable 1080×1920 PNG.

- [ ] **Step 5: Perform visual QA at full and thumbnail sizes**

Inspect the formal cover at 1080×1920 and a 270×480 downscale. Confirm the face is clear, the person remains the primary subject, the palace depth is readable, “欢喜” is legible at thumbnail size, the support label is subordinate, and neither text block overlaps the face, shoulders, arms, or main pose.

- [ ] **Step 6: Commit the renderer and verification**

```bash
git add zhixia-feihualing/tests/test_yiwu_yiyuan_huanxi_cha_cha_cover.sh zhixia-feihualing/scripts/render_yiwu_yiyuan_huanxi_cha_cha_cover.swift zhixia-feihualing/scripts/build_yiwu_yiyuan_huanxi_cha_cha_cover.sh
git commit -m "完成天宫恰恰欢喜正式封面"
```
