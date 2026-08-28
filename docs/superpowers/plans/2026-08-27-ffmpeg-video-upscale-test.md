# FFmpeg Video Upscale Test Implementation Plan

> **For agentic workers:** Execute the steps inline and verify every media property before delivery.

**Goal:** Produce a conservative 1080×1920 comparison sample from the supplied Seedance video using only the already-installed FFmpeg, without modifying the source.

**Architecture:** Probe the source first, then apply a single deterministic filter chain: mild temporal/spatial denoise, aspect-ratio-preserving Lanczos enlargement, centered crop to 9:16, and low-strength luma sharpening. Encode a delivery MP4 with H.265 while copying compatible source audio, then verify metadata and inspect matched keyframes.

**Tech Stack:** FFmpeg 8.0.1, ffprobe, H.265/libx265, shell read-only media inspection.

## Global Constraints

- Source remains unchanged at `/Users/huan.yu/Downloads/5f638562-0c43-47a8-8492-28bd6a27bf35.mp4`.
- Output is written under `/Users/huan.yu/dev/tools-workspace/artifacts/video-upscale-test/`.
- No AI super-resolution, frame interpolation, face restoration, or added grain.
- Preserve original duration, frame rate, audio timing, and display orientation.
- Target display resolution is exactly 1080×1920 with square pixels.
- Denoise and sharpening stay deliberately mild to protect faces, hair, cloud texture, and the creature's markings.

---

### Task 1: Probe and derive the scaling geometry

**Files:**
- Read: `/Users/huan.yu/Downloads/5f638562-0c43-47a8-8492-28bd6a27bf35.mp4`
- Create: `/Users/huan.yu/dev/tools-workspace/artifacts/video-upscale-test/source-metadata.json`

- [ ] Record container, coded and display dimensions, sample aspect ratio, frame rate, duration, codec, pixel format, color tags, rotation metadata, and audio stream properties with `ffprobe`.
- [ ] Confirm the source can be decoded without reported errors.
- [ ] Preserve aspect ratio by scaling to cover 1080×1920, then crop only the minimal excess from the center.

### Task 2: Render the conservative HD sample

**Files:**
- Create: `/Users/huan.yu/dev/tools-workspace/artifacts/video-upscale-test/5f638562-ffmpeg-1080p.mp4`

- [ ] Apply `hqdn3d=0.8:0.6:2.4:1.8` before enlargement to reduce compression noise without smearing motion.
- [ ] Apply aspect-preserving Lanczos enlargement using `scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos`.
- [ ] Apply centered `crop=1080:1920` to avoid stretching characters.
- [ ] Apply low-strength luma sharpening with `unsharp=5:5:0.35:5:5:0`.
- [ ] Encode H.265 with `libx265`, `preset=medium`, `crf=18`, tag `hvc1`, fast-start metadata, and preserve compatible source audio.

### Task 3: Verify and visually compare

**Files:**
- Create: `/Users/huan.yu/dev/tools-workspace/artifacts/video-upscale-test/output-metadata.json`
- Create: `/Users/huan.yu/dev/tools-workspace/artifacts/video-upscale-test/source-contact-sheet.jpg`
- Create: `/Users/huan.yu/dev/tools-workspace/artifacts/video-upscale-test/upscaled-contact-sheet.jpg`

- [ ] Confirm exact 1080×1920 dimensions, square pixels, unchanged frame rate, matching duration, expected video codec, and an audio stream.
- [ ] Decode the complete output to a null sink and require a zero exit status.
- [ ] Extract matched frames from the beginning, middle, and end of both videos.
- [ ] Inspect for halos, oversharpened eyes and hair, smeared cloud texture, crushed shadows, new banding, face changes, or temporal glitches.
- [ ] Report the measured file sizes and any limitations visible in the comparison.
