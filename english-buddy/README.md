# English Buddy — 英语老师带读通话

类似豆包「打电话」：**AI 英语老师**语音带读，**4 岁中国小朋友**跟读；**实时语音**、本地 Whisper、慢速 TTS、说话可打断。

详细专题见 [`docs/`](docs/README.md)（登录、课文库、TTS）。

## 架构

```text
浏览器麦克风 → 16kHz PCM (WebSocket 二进制)
        ↓
faster-whisper (本地 STT，离线)
        ↓
Ollama qwen2.5:3b → 老师英文短句（面向 4 岁跟读）
        ↓
edge-tts / Piper → WAV → WebSocket 二进制
        ↓
浏览器播放（检测到用户说话 → interrupt 打断）
```

| 组件 | 说明 |
|------|------|
| 前端 | Vue 3，`/ws/call`，PCM + VAD + 流式播放 |
| 后端 | FastAPI `:18787`，`ws_call.py` |
| STT | **faster-whisper** `small`（可改 `.env`） |
| LLM | **qwen2.5:3b** |
| TTS | 默认 **edge** 微软神经音（`.env` `TTS_ENGINE=edge`）；离线改 `piper` |

## 前置条件

1. **Ollama** + 模型：

   ```bash
   ollama pull qwen2.5:3b
   ```

2. **Python 3.10+**、**Node 18+**

   ```bash
   cd english-buddy
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

   首次使用前下载 Whisper（约 461MB）：

   ```bash
   ./scripts/download_whisper.sh
   ```

   说明：请让 **hf-mirror 直连**（不要对镜像走代理，易 SSL 失败）。下完后可在 `.env` 设 `WHISPER_MODEL=$HOME/.cache/faster-whisper-small`。

3. **Chrome** + 麦克风（localhost 即可）。

## 快速启动

```bash
cd english-buddy
cp .env.example .env
cp frontend/.env.example frontend/.env   # 本地 dev：VITE_BASE_PATH=/

# 本地 dev 请在 .env 设 ENGLISH_BUDDY_COOKIE_PATH=/

./scripts/dev-backend.sh   # :18787
./scripts/dev-frontend.sh  # :5173
```

打开 **http://127.0.0.1:5173**（开发）

本机直连（launchd）：**http://127.0.0.1:18787/english/** 或局域网 **http://192.168.x.x:18787/english/**（`.env` 设 `ENGLISH_BUDDY_HOST=0.0.0.0`）

### 使用流程

1. **首页**：选老师（艾莎 / 奥特曼）→ 年级 → 课文 → 语速 →「开始带读」
2. **内置课文**：免登录；启动后后台**并发**预热；**未预热的课文不在首页展示**
3. **自定义课文**：须登录（右上角）；登录后在首页「选课文」可选自己的课文；在「自定义课文」页管理并预热
4. 允许麦克风；老师开场并带读第一句
5. 孩子可**说话**（停顿约 0.85s 自动识别）或点 **「我说完啦」**
6. 带读中可点课文任意一句 **按句重读**
7. 一篇读完不自动下一课；换课请结束通话后重选

**若一直重复同一句**：多半是外放被麦克风拾取；请用耳机或降低音量。

更多说明：[docs/AUTH.md](docs/AUTH.md) · [docs/CURRICULUM.md](docs/CURRICULUM.md)

## 公网（Home Hub 同域）

| 环境 | URL |
|------|-----|
| 外网 | **https://hub.yoloworld.site:8883/english/** |
| 内网（域名） | **https://hub.yoloworld.site:8443/english/** |
| 内网（仅 IP，需 mkcert） | **https://192.168.1.13:8443/english/** — 见下 |

**手机 WiFi 只能填 IP、不能解析域名时**：必须用 **HTTPS + IP**，否则浏览器不给麦克风。

```bash
cd english-buddy
chmod +x scripts/setup-lan-https.sh
./scripts/setup-lan-https.sh   # mkcert 证书 + Caddy :8443 + 更新 .env CORS
```

手机打开 **`https://<局域网IP>:8443/english/`**。  
首次须把 mkcert 的 `rootCA.pem` 装到 iPhone 并开启「证书信任」（见 [docs/LAN_HTTPS.md](docs/LAN_HTTPS.md)）。  
Mac IP 变了重跑脚本即可。

Caddy 将 `/english/*` 反代到 `127.0.0.1:18787`（`handle_path` 剥前缀）。

```bash
cd english-buddy
cp .env.example .env          # ENGLISH_BUDDY_COOKIE_PATH=/english/
./scripts/install-launchd.sh

cd ../sidestore-infra
docker compose restart caddy
```

改代码：`./scripts/restart.sh --build`  
验证：`curl -s http://127.0.0.1:18787/api/health`

## 配置 (.env)

### 语音与模型

| 变量 | 默认 | 说明 |
|------|------|------|
| `OLLAMA_MODEL` | `qwen2.5:3b` | 英语老师 LLM |
| `TTS_ENGINE` | `edge` | `edge` 联网；`piper` 离线 |
| `ELSA_EDGE_VOICE` / `ULTRA_EDGE_VOICE` | 见 `.env.example` | 两位老师 edge 音色 |
| `PIPER_LENGTH_SCALE` | `1.0` | 仅 piper |
| `WHISPER_MODEL` | `small` | `base` 更快、`medium` 更准 |
| `WHISPER_DEVICE` | `cpu` | M 系列可试 `auto` |
| `WHISPER_WORKERS` | `2` | 并行 STT 路数（每路独立模型，约 +500MB 内存/路） |
| `MAX_READ_ALONG_SESSIONS` | 同 `WHISPER_WORKERS` | 同时带读人数上限，满员后拒绝新开带读 |
| `ENGLISH_BUDDY_STT_USERS` | 空=不限 | 仅列出的用户名启用语音识别；其他只听老师带读 |
| `ENGLISH_BUDDY_FREE_CHAT_USERS` | 空=关闭 | 仅列出的用户名显示「自由聊天」入口 |
| `TEACHING_GUIDE` | `1` | 注入 `backend/teaching/playbook_age4_read_along.md` |

### 课文与预热

| 变量 | 默认 | 说明 |
|------|------|------|
| `BUILTIN_PREWARM` | `1` | 后台并发预热全部内置课文；`0` 关闭 |
| `BUILTIN_PREWARM_CONCURRENCY` | `4` | 并发预热路数（edge TTS 建议 3～6） |

### 登录（自定义课文）

| 变量 | 默认 | 说明 |
|------|------|------|
| `ENGLISH_BUDDY_USERS` | — | `user:pass,user2:pass2`，家庭账号，**不开放注册** |
| `ENGLISH_BUDDY_REQUIRE_AUTH` | `1` | `0` 关闭登录 UI |
| `ENGLISH_BUDDY_SESSION_TTL_HOURS` | `720` | 会话有效期（约 30 天） |
| `ENGLISH_BUDDY_COOKIE_PATH` | `/english/` | 本地 dev 改为 `/` |

详见 [docs/AUTH.md](docs/AUTH.md)。

## 功能摘要

| 功能 | 说明 |
|------|------|
| **语速** | 首页与通话中：慢 `0.85` / 标准 `1.0` / 快 `1.15`；存 `localStorage` |
| **按句重读** | 点课文行，或「老师再说一遍」「回到上一句」 |
| **课文库** | 沪教牛津六三制上下册 + 幼儿园；见 [docs/CURRICULUM.md](docs/CURRICULUM.md) |
| **自定义课文** | 登录后隔离；须预热后带读 |

## WebSocket 协议（摘要）

| 方向 | 消息 |
|------|------|
| C→S | 二进制 PCM int16 16kHz |
| C→S | `start_call`：`lesson_id`、`mode`、`program`、`tts_speed` |
| C→S | `update_tts_speed` / `reread_line` / `text_message` / `utterance_end` / `interrupt` |
| S→C | `transcript` / `assistant_text` / `lesson_complete` / `reread_line` |
| S→C | 二进制音频分片 + `tts_end` |

REST `POST /api/reply` 保留作调试。课文 REST：`/api/lessons`、`/api/grades`、`/api/programs`。

## 目录

```text
english-buddy/
  backend/
    routers/       auth_api.py, lessons_api.py
    services/      stt, llm, tts, lesson_store, user_store, builtin_prewarm
    teaching/      lessons.json, build_lessons_v5.py, playbook
    ws_call.py
    data/          english_buddy.db
  frontend/
    src/auth/      session.ts
    src/composables/ useVoiceCallWs.ts, useAuth.ts
    src/views/     CallView.vue
  docs/            AUTH, CURRICULUM, TTS
  scripts/         dev-*, restart.sh, install-launchd.sh
```

## 注意

- 默认 edge TTS 需联网；STT + LLM 本地。`TTS_ENGINE=piper` 可全离线 TTS。
- 无家长端审核；请陪同使用。
- 健康检查：`GET /api/health` → `teaching_guide.loaded` 等。
