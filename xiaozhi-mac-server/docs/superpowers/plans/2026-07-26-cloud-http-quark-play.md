# Cloud HTTP Quark Play Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or continue task-by-task. Steps use checkbox syntax.

**Goal:** Cloud xiaozhi.me dialogue + Mac media HTTP (transcoded MP3) + device firmware `play_url`/`stop`.

**Architecture:** Mac `MEDIA_ONLY` HTTP service exposes `/stream/quark/{fid}/device.mp3` and `/api/media/*`; `mcp_pipe` tools return `stream_url`; Atom firmware pulls URL locally. Design: `docs/DESIGN_CLOUD_HTTP_QUARK_PLAY.md`.

**Tech Stack:** Python aiohttp/ffmpeg, FastMCP, ESP-IDF xiaozhi-esp32 board `atoms3r-echo-pyramid` / cam-m12.

## Global Constraints

- No Mode B Opus push as primary path
- Device tools: `self.audio.play_url`, `self.audio.stop`
- Next/resume on Mac only; bare LAN fid URLs
- Mac ffmpeg unified MP3 for device

---

## Phase A — Mac media service

### Task A1: Config + MEDIA_ONLY entry

- [ ] Add `media_only` to `server/config.py` (`MEDIA_ONLY=true`)
- [ ] `server/main.py`: if media_only, skip Whisper preload and WS server
- [ ] Verify: process listens only `:8766`

### Task A2: Device MP3 transcoder route

- [ ] `http_stream.py`: `GET /stream/quark/{fid}/device.mp3` via ffmpeg → mono/stereo 96k MP3 pipe
- [ ] Resolve fid from cache or `QuarkClient.resolve_stream_source` + index hint
- [ ] Manual: `ffplay http://127.0.0.1:8766/stream/quark/<fid>/device.mp3`

### Task A3: Media resolve API

- [ ] New `server/media_api.py`: `POST /api/media/resolve|next|resume`
- [ ] Use `series_maps` / `pick_best_file` / `playback_memory`; return `stream_url` (device.mp3)
- [ ] Register routes in `http_server.py`

### Task A4: MCP tools for URL path

- [ ] Extend `mcp/quark_audio_server.py`: `resolve_quark_stream_url`, `next_quark_audio`, `resume_quark_audio` (keep old play for Mode A)
- [ ] `scripts/run-media-stack.sh` + `.env.example` notes

### Task A5: Smoke

- [ ] resolve 冰雪奇缘第一集 → device.mp3 URL → ffplay hears ep1

---

## Phase B — Firmware

### Task B1: HTTP MP3 player module

- [ ] Add board-local or shared `http_mp3_player` (ESP HTTP + decode to I2S/codec)
- [ ] Disconnect dialogue before play ([#863](https://github.com/78/xiaozhi-esp32/issues/863))

### Task B2: Device MCP tools

- [ ] Register `self.audio.play_url` / `self.audio.stop` on atoms3r pyramid/cam boards
- [ ] Flash + call tool with Mac device.mp3 URL

### Task B3: E2E

- [ ] Cloud: search MCP → play_url → speaker; stop; next via Mac MCP

---

## Out of scope this plan

- SD card, Mode B push, stream URL tokens
