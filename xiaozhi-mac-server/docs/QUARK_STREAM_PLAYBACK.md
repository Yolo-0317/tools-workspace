# Quark HTTP 流式播放链路

在已有 **夸克网盘 skill** 之上，为 `xiaozhi-mac-server` 增加「语音点播 -> HTTP Range 流式播放」能力。无需整文件下载到本地后再播放。

## 架构

```text
用户：「播放西游记」/「想听故事」
        |
   xiaozhi-mac-server (ASR)
        |
   audio_intent.parse_play_intent()
        |
   quark_client.search_audio(keyword)     ← quark-drive.cjs search
        |
   quark_client.resolve_stream_source()   ← Open API get_download_url
        |
   +------------------+------------------+
   |                                     |
   A. WebSocket 下行                      B. HTTP Range 代理（可选）
   ffmpeg 读 CDN URL                     GET /stream/quark/{fid}
   -> PCM -> Opus -> 小智扬声器            ffplay / mpv / 浏览器
```

## 与夸克 skill 的分工

| 步骤 | 使用 skill CLI？ | 说明 |
|------|------------------|------|
| 搜索 | 是 | `quark-drive.cjs search --category 2` |
| 取 CDN URL | 否（直连 Open API） | skill 未暴露 `stream-url`；网关内实现签名调用 |
| 播放 | 网关内 ffmpeg | 带 Cookie 的 HTTP Range，边拉边解码 |

Open API 签名算法与 `quark-drive.cjs` 内嵌常量一致：

```text
x-pan-token = sha256("POST&/open/v1/file/get_download_url&{timestamp_ms}&{signKey}")
Cookie: x_pan_client_id=third_party_agent;x_pan_access_token={token}
```

CDN 实测支持 `206 Partial Content`（`bytes 0-8191/536702`）。

## 新增模块

| 文件 | 作用 |
|------|------|
| `server/quark_client.py` | 搜索 + 解析 CDN 流地址 |
| `server/audio_intent.py` | 「播放/想听 xxx」意图识别 |
| `server/http_stream.py` | Range 代理 + ffmpeg 流式解码为 Opus |
| `server/quark_playback.py` | WebSocket 会话内触发播放 |

## 配置

`.env`（见 `.env.example`）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `QUARK_STREAM_ENABLED` | `true` | 关闭后不拦截播放意图 |
| `HERMES_SESSION_ID` | 自动读 config | 夸克 CLI 所需 Agent 环境 |
| `QUARK_DRIVE_CLI` | workspace skill 路径 | `quark-drive.cjs` |
| `QUARK_HERMES_CONFIG` | skill `hermes/config.json` | 读取 accessToken |

依赖：`node`（夸克 CLI）、`ffmpeg`（`brew install ffmpeg`）。

## 试跑

```bash
cd xiaozhi-mac-server
bash scripts/test-quark-stream.sh 故事
```

启动网关后，模拟设备文字模式（`t` + 回车）输入：

```text
想听故事
```

## HTTP 代理用法

语音点播成功后，网关会把 `QuarkStreamSource` 缓存在内存，可通过 LAN 访问：

```text
http://<LAN_IP>:8766/stream/quark/{fid}
```

支持 `Range` 头，可用 `ffplay` / `mpv` 直接播：

```bash
ffplay -headers "Range: bytes=0-" "http://127.0.0.1:8766/stream/quark/{fid}"
```

注意：代理仅在网关进程存活期间有效；`fid` 为夸克文件 ID。

## 局限与后续

- **仅夸克**：百度网盘可复用同一模式（搜索 skill + 取 URL + Range 代理）。
- **单路播放**：当前未做播放队列、暂停、续播。
- **URL 有效期**：夸克 CDN 链接会过期；长音频播放中若 403 需重新 resolve。
- **西游记**：玥玥目录 `04.【完结】西游记儿童广播剧`；catalog `journey_west`；默认第一集 `002.第一回 美猴王横空出世！.mp3`（无 001 文件属正常）。

## 相关

- 夸克 skill：`.cursor/skills/quarkclouddrive/`
- 小智网关：`xiaozhi-mac-server/README.md`
