# OpenRouter Plain Chat — Design

**Date:** 2026-07-22  
**Status:** Approved

## Goal

本机最小纯聊天页：流式调用 OpenRouter NSFW 向模型；无角色卡、无会话落盘。

## Decisions

| 项 | 选择 |
|----|------|
| 持久化 | 无（刷新清空） |
| 栈 | Python stdlib HTTP + 静态 HTML |
| 流式 | 是（SSE） |
| 绑定 | `127.0.0.1:8795` |
| Key | `OPENROUTER_API_KEY` 或复用 SillyTavern `secrets.json` |
| 默认模型 | `sao10k/l3.1-euryale-70b` |

## Architecture

- `openrouter-chat/server.py`：静态页 + `POST /api/chat` 流式代理 OpenRouter
- `openrouter-chat/static/index.html`：前端内存 `messages[]`，SSE 渲染
- `openrouter-chat/start.sh`：启动入口

## Out of scope

落盘、多会话、角色卡、世界书、公网反代、鉴权、emoji UI。

## Success

`bash start.sh` → 打开 `http://127.0.0.1:8795/` → 发消息可见流式回复。
（勿用 8793：易与旧 Open WebUI Service Worker 冲突，表现为 `500: Internal Error`。）
