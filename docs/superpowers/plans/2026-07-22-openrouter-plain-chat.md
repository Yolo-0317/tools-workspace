# OpenRouter Plain Chat Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkboxes track progress.

**Goal:** 本机最小流式纯聊天页，接 OpenRouter NSFW 模型。

**Architecture:** Python stdlib 服务代理 OpenRouter SSE；前端单页内存会话。

**Tech Stack:** Python 3 stdlib、HTML/CSS/JS、OpenRouter Chat Completions API

## Global Constraints

- 绑定仅 `127.0.0.1`；默认端口 `8795`
- 无 emoji；Key 不进前端
- 无落盘聊天记录

---

### Task 1: Server + static UI + start script

**Files:**
- Create: `openrouter-chat/server.py`
- Create: `openrouter-chat/static/index.html`
- Create: `openrouter-chat/start.sh`
- Create: `openrouter-chat/.env.example`
- Create: `openrouter-chat/README.md`
- Create: `openrouter-chat/.gitignore`

- [x] Implement server (key resolve, `/`, `/api/chat` SSE proxy)
- [x] Implement chat UI (model select, stream render)
- [x] `start.sh` + README
- [x] Smoke: start + curl stream or browser
