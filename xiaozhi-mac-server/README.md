# xiaozhi-mac-server

本地 **小智 AI 网关 + Mac 模拟设备**，用于在没有 M5Stack 硬件（或尚未烧录固件）时，验证与小智 ESP32 **相同的 WebSocket 语音协议**。

## 架构

```text
Mac 麦克风/扬声器
       |
  sim_device.py          模拟 AtomS3R + Echo Base（hello / listen / Opus 二进制）
       | ws://LAN:8765
  server/main.py         小智协议网关
       |-- faster-whisper   语音转文字（16 kHz Opus 上行）
       |-- intent_router      DeepSeek 路由：闲聊 / 点播 / 澄清追问
       |-- quark_picker       候选列表二次选型（DeepSeek）
       |-- edge-tts         文字转语音 -> 24 kHz Opus 下行
       |
  HTTP :8766/xiaozhi/ota/  真机 OTA 拉取 websocket.url + token（可选）
```

协议真源：`xiaozhi-atoms3r/firmware/docs/websocket_zh.md`

## 快速开始

```bash
cd xiaozhi-mac-server
bash scripts/install.sh    # 首次：venv + opus + 依赖 + ollama 模型

# 终端 1：启动网关
bash scripts/run-server.sh

# 终端 2：模拟 M5Stack 对话
bash scripts/run-sim.sh
```

或一条命令（前台模拟器，后台服务器）：

```bash
bash scripts/demo.sh
```

## 语音 Demo（模拟 AtomS3R 物理设备）

与真机相同：**WebSocket + Opus + hello/listen**。Mac 麦克风/扬声器代替 Echo Base。

```bash
bash scripts/run-voice-demo.sh
```

| 操作 | 作用 |
|------|------|
| 回车 | 开始录音 |
| 再回车 | 结束发送（ASR -> 夸克点播/LLM -> Opus 下行） |
| `t` + 回车 | 文字输入（跳过麦克风，如「想听儿童故事」） |
| `q` + 回车 | 退出 |

说 **「想听儿童故事」** / **「想听冰雪奇缘」** 会走夸克网盘流式播放，音轨经 Opus 推到扬声器（与真机下行一致）。

真机到货后：OTA 指向 `http://<LAN_IP>:8766/xiaozhi/ota/`，无需改服务端。

## 网页 Demo（文字搜故事 + HTTP 流式播放）

用文字代替语音，从夸克网盘搜索音频并经本机 HTTP Range 代理在浏览器播放：

```bash
bash scripts/run-web-demo.sh
```

浏览器打开：**http://127.0.0.1:8766/demo/**

- 输入「想听儿童故事」等文字指令
- **搜索**：列出网盘音频
- **播放最佳匹配** 或点某一行的 **播放**：走 `/stream/quark/{fid}` 流式播放

API（供调试）：

| 路径 | 说明 |
|------|------|
| `POST /api/story/search` | `{ "text": "想听..." }` 搜索 |
| `POST /api/story/prepare` | `{ "fid": "..." }` 解析 CDN 并缓存 |
| `POST /api/story/play` | 搜索 + 最佳匹配一键播放 |

详见 `docs/QUARK_STREAM_PLAYBACK.md`。

## MCP + 夸克真机播放

真机通过 MCP 工具搜索/播放夸克网盘音频（Opus 仍经本地网关下行）：

| 模式 | 配置 | 说明 |
|------|------|------|
| **A 本地 MCP（推荐）** | `USE_MCP_TOOLS=true` + 本地 OTA | DeepSeek 调 `play_quark_audio` |
| **B 云端 MCP** | `MCP_ENDPOINT` + pipe | xiaozhi.me 触发工具；播放仍要本地 WS |

```bash
bash scripts/run-quark-voice-stack.sh          # 启网关
cd ../xiaozhi-atoms3r && bash scripts/flash-local-ota.sh   # 设备改本地 OTA
bash scripts/check-quark-mcp.sh               # 体检
```

详见 `docs/MCP_QUARK_PLAYBACK.md`。

## 配置

复制并编辑 `.env`（安装脚本会从 `.env.example` 生成）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `WS_PORT` | 8765 | WebSocket 端口 |
| `HTTP_PORT` | 8766 | OTA HTTP 端口 |
| `TOKEN` | demo-token | 设备 Bearer token |
| `LLM_BACKEND` | ollama | 保留字段；**意图路由与点播选型固定走 DeepSeek API** |
| `DEEPSEEK_API_KEY` | （读 `stock-ai/.env`） | **必需**（路由 + 夸克选型） |
| `DEEPSEEK_MODEL` | deepseek-v4-flash | DeepSeek 模型 |
| `LLM_MAX_TOKENS` | 150 | 单次回复上限 |
| `LLM_HISTORY_TURNS` | 8 | 会话记忆轮数（仅闲聊） |
| `OLLAMA_MODEL` | qwen2.5:0.5b | 本地 LLM（`LLM_BACKEND=ollama`） |
| `WHISPER_PROFILE` | balanced | `fast`(tiny) / `balanced`(base) / `accurate`(small) |
| `WHISPER_PRELOAD` | true | 启动时预加载 ASR，避免首句卡顿 |
| `ASR_BACKEND` | tencent | `tencent`（一句话识别）或 `local`（Whisper） |
| `ASR_FALLBACK_LOCAL` | true | 腾讯云失败时回退本地 Whisper |
| `TENCENT_SECRET_ID` | — | 腾讯云 API 密钥 |
| `TENCENT_SECRET_KEY` | — | 腾讯云 API 密钥 |
| `TENCENT_ASR_ENGINE` | 16k_zh | 识别引擎（16k 中文） |
| `QUARK_PICK_LLM` | true | 点播时用 DeepSeek 从夸克候选中选文件 |
| `QUARK_PICK_TOP` | 20 | 交给 LLM 的候选数量上限 |
| `TTS_VOICE` | zh-CN-XiaoxiaoNeural | edge-tts 音色 |
| `STREAMING_ASR` | true | `listen.mode=auto/realtime` 时服务端按静音切轮 |
| `STREAM_SILENCE_MS` | 900 | 判定一句结束的静音时长 |
| `STREAM_MIN_SPEECH_MS` | 500 | 最短有效语音 |
| `USE_MCP_TOOLS` | false | 真机语音走 MCP 工具（search/play Quark） |
| `MCP_ENDPOINT` | — | xiaozhi.me MCP WebSocket（`run-quark-mcp-pipe.sh`） |
| `XIAOZHI_GATEWAY` | 自动 LAN:8766 | MCP 服务回调的 HTTP 网关地址 |

## 夸克库存索引（点播加速）

别名表 `data/quark_content_aliases.json` 仅提供搜索词；**文件清单**在 `data/quark_media_index.json`（按系列预扫 mp3 fid）。

```bash
python3 scripts/build_quark_media_index.py   # 首次或网盘更新后重跑
```

命中 catalog 时优先走索引（跳过实时搜索），下一集/续播也查索引。可问「有什么可以听」。

## 真机连续对话（auto 模式）

固件 `listen.mode=auto` 时会 **持续推 Opus 帧**，不再等 `listen.stop` 才处理一整包。

服务端流程（`server/streaming_uplink.py` + `ws_server.py`）：

```text
listen.start(mode=auto)
  -> 每收到 60ms Opus 帧解码算 RMS
  -> 连续有声帧开始累积一句
  -> 静音 >= STREAM_SILENCE_MS 且有效语音 >= STREAM_MIN_SPEECH_MS
  -> 切出一轮 -> Whisper ASR -> intent_router -> TTS
  -> 固件 TTS 播完后自动回到 Listening，继续推流（无需再次唤醒）
```

`manual` 模式行为不变：仍缓冲到 `listen.stop` 再 ASR。

调参：环境吵时增大 `STREAM_SILENCE_MS` / `STREAM_MIN_RMS`；截断太快则略增 `STREAM_SILENCE_MS`。

## 腾讯云 ASR（推荐）

1. 登录 [腾讯云语音识别控制台](https://console.cloud.tencent.com/asr)，开通 **一句话识别**（商用版，每月 **5000 次免费**）
2. [API 密钥管理](https://console.cloud.tencent.com/cam/capi) 创建 `SecretId` / `SecretKey`
3. 写入 `.env`：

```bash
ASR_BACKEND=tencent
TENCENT_SECRET_ID=AKID...
TENCENT_SECRET_KEY=...
TENCENT_ASR_ENGINE=16k_zh
ASR_FALLBACK_LOCAL=true   # 密钥未配或 API 失败时用本地 Whisper
```

4. 安装依赖并重启：`pip install -r requirements.txt && bash scripts/run-server.sh`

`/api/status` 会返回 `tencent_asr: true/false` 表示密钥是否已配置。

## 真机接入（AtomS3R）

1. 确保 Mac 与设备在同一局域网
2. 启动 `run-server.sh`，记下日志里的 **LAN IP** 与 `ws://` 地址
3. 将设备 OTA URL 指向 `http://<LAN_IP>:8766/xiaozhi/ota/`（需在固件 / NVS 配置 `ota_url`）
4. OTA 响应会下发 `websocket.url` 与 `token`，与模拟客户端相同

## 目录

```text
xiaozhi-mac-server/
├── server/           # WebSocket + HTTP OTA + ASR/LLM/TTS 管线
├── client/
│   └── sim_device.py # Mac 麦克风模拟 ESP32
├── scripts/
│   ├── install.sh
│   ├── run-server.sh
│   ├── run-sim.sh
│   └── demo.sh
└── requirements.txt
```

## 依赖

- Python 3.12（Homebrew `python@3.12`）
- `brew install opus ffmpeg`
- [Ollama](https://ollama.com)（可选，无模型时用固定 fallback 回复）
- Mac 麦克风 / 扬声器权限（首次运行时系统会询问）

## 后续

- ~~对接夸克网盘 Skill：小朋友说「想听故事」-> search -> download -> 推 Opus 播放~~（已实现 HTTP 流式版，见 `docs/QUARK_STREAM_PLAYBACK.md`）
- ~~唤醒词 / 自动模式（当前为手动按回车，对应协议 `listen.mode=manual`）~~（WebSocket 已支持 `auto` 流式切轮；Mac 模拟器仍为 manual）
- 百度网盘同源链路、播放控制（暂停/续播/队列）

## 相关

- 硬件固件开发：`../xiaozhi-atoms3r/`
- 上游协议：[78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
