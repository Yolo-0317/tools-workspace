# MCP + Quark playback for Xiaozhi devices

Two deployment modes share the same Quark search/play logic (`server/quark_mcp_tools.py`).

> **设计草案（未实现）**：云端对话 + Mac 夸克 HTTP 转播 + 固件 URL 拉流 — 见 [DESIGN_CLOUD_HTTP_QUARK_PLAY.md](./DESIGN_CLOUD_HTTP_QUARK_PLAY.md)。与下文 Mode B（本地 WS 推 Opus）不同，草案由设备 HTTP 拉 `/stream/quark/{fid}`。

## Quick start (Mode B — cloud agent MCP + local play)

对话走 **xiaozhi.me** 智能体；点播夸克时云端调本地 MCP，由本机网关推 Opus。

**硬性条件：** 播放时设备必须已连上本地 `ws://<LAN>:8765`（OTA 指本地）。只连官方云、不连本地网关 → 能搜不能播。

```bash
# 1) .env 写入 MCP 接入点（控制台 → 配置角色 → MCP 接入点）
#    MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...
#    USE_MCP_TOOLS=false

# 2) 启动网关 + MCP pipe
cd xiaozhi-mac-server
bash scripts/run-mode-b-stack.sh

# 3) 设备改本地 OTA（否则 play 报「没有已连接的小智设备」）
cd ../xiaozhi-atoms3r
bash scripts/flash-local-ota.sh

# 4) 体检
cd ../xiaozhi-mac-server
bash scripts/check-quark-mcp.sh
```

对设备说「想听儿童故事」——云端智能体应调用 `play_quark_audio`。

> 说明：刷成本地 OTA 后，设备语音上行也走本地网关；云端 MCP 仍可用于该智能体上的工具调用。若设备继续只用官方云 OTA、不刷本地，则 Mode B 推流无法完成。

## Quick start (Mode A — fully local)

Device talks to **local** `xiaozhi-mac-server`; DeepSeek calls `play_quark_audio`; Opus streams to Pyramid/Atom.

```bash
# Terminal 1 — gateway
cd xiaozhi-mac-server
# USE_MCP_TOOLS=true in .env
bash scripts/run-quark-voice-stack.sh

# Terminal 2 — local OTA flash
cd ../xiaozhi-atoms3r
bash scripts/flash-local-ota.sh

bash scripts/check-quark-mcp.sh
```

## Architecture

```text
Mode A — local gateway (recommended)

AtomS3R  --WS Opus-->  xiaozhi-mac-server (:8765)
                              |
                              | USE_MCP_TOOLS=true
                              v
                         DeepSeek tool calling
                         search_quark_audio / play_quark_audio
                              |
                              v
                         quark_client -> ffmpeg -> Opus downlink


Mode B — xiaozhi.me cloud MCP + local play bridge

AtomS3R  --WS-->  xiaozhi.me cloud LLM
                         |
                         | MCP over WebSocket
                         v
                   scripts/mcp_pipe.py
                         |
                         v
                   mcp/quark_audio_server.py (stdio FastMCP)
                         |
                         | HTTP POST /api/mcp/play
                         v
                   xiaozhi-mac-server (device must also connect WS here)
                         |
                         v
                   Opus downlink to AtomS3R
```

**Important:** Quark long-form playback goes through the Mac gateway (`quark_playback.py`). The device does not pull Quark CDN directly. For Mode B, AtomS3R must **also** connect to local `ws://<LAN>:8765` (OTA → mac-server). If the device only stays on xiaozhi.me cloud WS, MCP can search but cannot play.

## Mode A

1. `bash scripts/run-quark-voice-stack.sh`
2. `.env`: `USE_MCP_TOOLS=true`, Quark logged in, DeepSeek key available
3. `cd ../xiaozhi-atoms3r && bash scripts/flash-local-ota.sh`
4. Power from Pyramid bottom USB; `check-quark-mcp.sh` should show `connected>=1`
5. Say「想听冰雪奇缘」

## Mode B

Reference: [小智 MCP 接入说明](https://my.feishu.cn/wiki/HiPEwZ37XiitnwktX13cEM5KnSb)

1. Gateway: `bash scripts/run-quark-voice-stack.sh`
2. `.env`: `MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...`
3. Pipe: `bash scripts/run-quark-mcp-pipe.sh`
4. Device OTA still local (`flash-local-ota.sh`) so play WS works. Cloud MCP only triggers tools.

## MCP tools

| Tool | Description |
|------|-------------|
| `search_quark_audio` | Search Quark drive |
| `play_quark_audio` | Play on connected device |
| `quark_playback_status` | Gateway + device status |

## HTTP bridge

| Path | Purpose |
|------|---------|
| `GET /api/mcp/status` | Connected devices |
| `POST /api/mcp/search` | Search |
| `POST /api/mcp/play` | Play on active WS session |
| `POST /api/mcp/resolve` | LAN stream URL preview |

## Troubleshooting

- **没有已连接的小智设备**: not on local WS — `flash-local-ota.sh`, Pyramid bottom power, `check-quark-mcp.sh`
- **Search OK, play fails**: `ffmpeg`; Quark login
- **Still on xiaozhi.me**: `CONFIG_OTA_URL` still tenclass — re-run `flash-local-ota.sh`
- **MCP pipe disconnects**: check `MCP_ENDPOINT` token

## Scripts

```text
scripts/run-quark-voice-stack.sh   Mode A gateway
scripts/check-quark-mcp.sh         Doctor
scripts/run-quark-mcp-pipe.sh      Mode B pipe
../xiaozhi-atoms3r/scripts/flash-local-ota.sh
```
