# 设计草案：云端小智 + Mac 夸克 HTTP 转播 + 固件 URL 播放

- **状态**：实现中 — Mac Phase A 已通；固件 Phase B 见 `xiaozhi-atoms3r/docs/FIRMWARE_HTTP_MP3_PLAY.md`
- **日期**：2026-07-26（拍板修订同日）
- **相关**：`QUARK_STREAM_PLAYBACK.md`（已有 HTTP 代理）· `MCP_QUARK_PLAYBACK.md`（Mode A 本地推 Opus，当前在用）
- **硬件**：M5Stack AtomS3R CAM + Echo / Pyramid
- **目标**：对话走 **xiaozhi.me 云端模型**；长音频（夸克故事）由设备 **HTTP 拉流本地解码**，Mac 只做搜库、转码代理与续播记忆。

---

## 1. 背景与问题

| 路径 | 结论 |
|------|------|
| 原机官方云端 | 只有对话 TTS + 设备端 MCP（音量等）；**无**播本地库 / 网盘故事 |
| 板载 SD / USB 硬盘 | AtomS3R **无 SD**；USB 不适合作挂盘；官方固件也不用 SD（[#1053](https://github.com/78/xiaozhi-esp32/issues/1053)） |
| Mode B（云 MCP + 本地 WS 推 Opus） | 设备若只连云，本地网关找不到会话，长音频推不进喇叭；已弃用 |
| Mode A（全本地网关） | 可用（ASR/意图/`/stream` + WS Opus），但不用云端对话模型 |

需要一条：**云端对话大脑 + 不依赖「云→本地 WS 推 Opus」** 的点播路径。

---

## 2. 方案摘要

```text
用户语音
    │
    ▼
AtomS3R ──WS──► xiaozhi.me（ASR / LLM / TTS 短回复）
                    │
                    │ ① 云端 MCP（Mac）：search_quark → fid + stream_url
                    │ ② 设备端 MCP：play_http_url(stream_url)
                    ▼
              Atom 主动 HTTP GET
              http://<Mac-LAN>:8766/stream/quark/{fid}
                    │
                    ▼
              Mac 代理：夸克鉴权 CDN → HTTP Range（已有）
                    │
                    ▼
              固件解码（MP3 等）→ ES8311 → 喇叭
```

**分工**

| 角色 | 职责 |
|------|------|
| xiaozhi.me | 对话、意图、编排工具调用 |
| Mac `xiaozhi-mac-server` | 夸克搜索、集数映射、暴露 `GET /stream/quark/{fid}` |
| 固件（需改） | 注册 `play_http_url`（或社区 `self.music.play_song`），拉 URL 并本地解码 |
| 夸克网盘 | 音频真源（玥玥目录 / `quark_series_maps`） |

Mac **不再**承担「经设备 WebSocket 推长 Opus」；设备是 HTTP 客户端。

---

## 3. 已有能力（可复用）

| 组件 | 路径 / 说明 |
|------|-------------|
| HTTP 流代理 | `GET /stream/quark/{fid}` · `server/http_stream.py` · 文档 `QUARK_STREAM_PLAYBACK.md` |
| 搜索 / 选片 | `quark_client` · `media_index` · `series_maps`（如 frozen 第一集） |
| 云端 MCP 桥 | 控制台 MCP 接入点 + `scripts/mcp_pipe.py`（可挂 search / 返回 URL 的工具） |
| LAN | 例：`http://192.168.1.13:8766/stream/quark/{fid}` |

设备侧用 `ffplay` / 浏览器验证代理即可，无需等固件完成再测 Mac。

---

## 4. 两类 MCP：不能互相替代

| | **设备端 MCP** | **云端 MCP 接入点（URL）** |
|--|----------------|---------------------------|
| 跑在哪 | **ESP 固件内**注册的工具 | **Mac/PC** 上的 MCP Server，经 `wss://api.xiaozhi.me/mcp/?token=...` 接到云 |
| 怎么「提供」 | 必须 **烧录/OTA 固件**（或用已含该工具的社区固件） | 控制台贴接入点 URL + 本机跑 `mcp_pipe`，**不用改喇叭解码代码** |
| 云端怎么调到 | 设备连上 xiaozhi.me 后，后端对设备做 `tools/list` / `tools/call` | 云端对接入点后的本地工具做调用 |
| 典型能力 | `set_volume`、**`play_url`（要自己写进固件）**、摄像头 | `search_quark`、计算器、搜网页——返回 JSON/文字 |
| 能否让喇叭播长音频 | **可以**（工具在板子上执行拉流/解码） | **不能单独完成**：URL 方案里 Mac 只返回 `stream_url`，真正出声仍靠设备端 `play_url` |

**结论（本草案）**

- 「搜夸克、拼 `http://Mac/stream/quark/{fid}`」→ 用 **云端 MCP URL**，Mac 上实现即可，**不必**为此改固件。
- 「设备去拉这个 URL 并出声」→ 必须是 **设备端 MCP + 固件里的播放器**，**不能**只靠再提供一个 MCP URL 代替烧录。
- 官方原机固件只有音量等常见设备工具，**没有** `play_url`；要 URL 播放就必须刷带该能力的固件（自研或社区音乐分支）。

虾哥原文要点：按 URL 播 MP3 的代码要加在**固件里**，且播放前先断开语音对话（[#863](https://github.com/78/xiaozhi-esp32/issues/863)）。

### 4.1 常见误解：能不能把「设备端 MCP」也做成 Mac 上的 URL？

**不能把「设备端 MCP」挪到 Mac 用接入点 URL 代替。** 原因不是协议名字，而是**代码在哪台机器上跑**：

```text
云端 MCP 接入点（URL）
  → 工具进程在 Mac 上执行
  → 可以 search_quark、返回 stream_url
  → 若工具叫 play_http_url 但写在 Mac 上：
        · 在 Mac 喇叭播？→ 不是 Atom
        · 再经本地 WS 推 Opus 给 Atom？→ 又回到 Mode B（设备还得连本地网关）
        · 远程让 Atom「自己去拉 URL」？→ Atom 固件里仍要有播放器/命令入口（还是要烧录）

设备端 MCP
  → 工具在 ESP 固件里执行
  → play_http_url 才能在板子上 HTTP GET → 解码 → ES8311
```

因此图中的 ② **若要坚持「设备自己拉 HTTP」**：播放逻辑必须在固件里（烧录社区音乐固件或自研），**没有**「只在 Mac 挂一个 MCP URL、设备零改动」的官方接法。

若坚持 **设备零改固件**：只能放弃「设备 HTTP 拉流」，改回 Mac 推 Opus（Mode A/B），或 Mac/外接音箱出声。

---

## 5. 缺口（待实现）

### 5.1 固件（已拍板：本仓库自研）

- 在 `xiaozhi-atoms3r/firmware`（上游小智树）上 **自研** URL 播放 + 设备端 MCP；社区音乐分支仅作实现参考，不作为主线依赖。
- 板型：`atoms3r-cam-m12-echo-base` / Pyramid 变体。
- 播前断开语音对话（[#863](https://github.com/78/xiaozhi-esp32/issues/863)）。
- 设备端 MCP 契约（MVP）：

| 工具 | 作用 |
|------|------|
| `self.audio.play_url` | 参数 `url`；HTTP 拉流解码播放 |
| `self.audio.stop` | 停播，恢复可对话 |
| `self.audio.next` | 可选薄封装：向云/本地约定「下一集」由 **Mac 记忆** 解析后再次 `play_url`；或设备只 stop，由云端再 search→play。**推荐：下一集逻辑全在 Mac MCP，设备只提供 play_url + stop**（实现更简单） |

> 拍板补充：产品要「下一集 / 续播」能力；**状态与选片在 Mac**，设备最少实现 `play_url` + `stop`。若固件顺便做 `next` 也只需回调「请主机给下一集 URL」类语义，仍以 Mac 为准。

- 拉流：**局域网 HTTP**；编码见下（Mac 转码后的统一 MP3）。

### 5.2 Mac / 云端 MCP 工具（已拍板）

| 工具 | 作用 | 返回 |
|------|------|------|
| `search_quark_audio` | 关键词 + `series_maps` | `{ title, fid, stream_url, catalog_key }` |
| `play_quark_resolve`（可与 search 合并） | 开播时写入 Mac `playback_state` | 同上 |
| `next_quark_audio` | 按 Mac 记忆 + 索引找下一集 | `{ stream_url, … }` |
| `resume_quark_audio` | 续播当前未听完 | `{ stream_url, … }`（进度若代理暂不支持 Range 续播，MVP 可重头或后续加） |

角色提示词：听故事 → Mac 出 `stream_url` → 设备 `self.audio.play_url`；停 → `self.audio.stop`；下一集 → Mac `next` 再 `play_url`。

**流格式（已拍板）**：Mac ffmpeg **统一转码**为固定规格可流式 MP3（如 64–128 kbps mono/stereo），设备只认这一种；不透传夸克原始封装差异。

**续播记忆（已拍板）**：复用 / 扩展 `data/playback_state/`，只在 Mac。

**安全（已拍板）**：内网裸 `fid` URL，不加 token。

### 5.3 运维前提

- Mac 开机、与设备同 Wi‑Fi；`stream_url` 使用 **LAN IP**。
- 设备 OTA/WS 指向 **xiaozhi.me**；与 Mode A 全本地网关 **互斥切换**（见 §9 Mac 进程）。

---

## 6. 与现有模式对比

| | Mode A（当前） | Mode B（已弃用） | 本方案（草案） |
|--|----------------|------------------|----------------|
| 对话 | 本地网关 | 云端 | **云端** |
| 点播决策 | 本地 intent / 可选本地 MCP tools | 云 MCP → 本地 play API | 云 MCP search + **设备 play_url** |
| 长音频进喇叭 | 本地 WS 推 Opus | 本地 WS 推 Opus（易断） | **设备 HTTP 拉流** |
| Mac 角色 | 网关全家桶 | 推流 + pipe | **搜库 + HTTP 代理** |
| 固件 | 原协议即可 | 原协议 + 本地 WS | **需 URL 播放能力** |

---

## 7. 风险与约束

1. **固件维护**：跟上游小智版本合入成本；OTA 可能覆盖自定义固件（控制台需关自动升级或固定渠道）。
2. **播放与对话互斥**：长播期间需停听/停 TTS；唤醒打断要定义清楚（停播 vs 暂停）。
3. **格式与卡顿**：Wi‑Fi 弱时 HTTP 拉流可能卡；代理转码增加 Mac CPU。
4. **双工具编排**：依赖云端 LLM 正确先后调用 search → play_url；提示词与工具描述要写清楚。
5. **安全**：已接受内网裸 fid；同网可扫到流（家庭局域网可接受）。

---

## 8. 落地进度

1. **Mac（已完成）**：`MEDIA_ONLY`；`/stream/quark/{fid}/device.mp3`（ffmpeg 统一 MP3）；`/api/media/resolve|next|resume`；MCP `resolve_quark_stream_url` / `next_quark_audio` / `resume_quark_audio`；`scripts/run-media-stack.sh`；launchd `com.user.xiaozhi-media`。
2. **固件（进行中）**：见 `xiaozhi-atoms3r/docs/FIRMWARE_HTTP_MP3_PLAY.md` — `play_url` / `stop` + HTTP 解码。
3. **联调**：云端角色提示词 + mcp_pipe `--with-mcp` + 设备刷自定义固件。
4. **体验**：停播 / 下一集 / 与 frozen 映射（Mac 侧已对齐第一集）。

---

## 9. 已拍板 vs 仍可后定

### 9.1 已拍板（2026-07-26）

| # | 项 | 决定 |
|---|-----|------|
| D1 | 固件 | **本仓库自研**（参考社区实现，不绑死某 fork） |
| D2 | 设备 MCP | 至少 **`play_url` + `stop`**；下一集/续播由 **Mac MCP** 出新 URL 再 `play_url` |
| D3 | 流格式 | **Mac ffmpeg 统一转码**为固定 MP3 再给设备 |
| D5 | 续播记忆 | **仅 Mac**（`playback_state` + `series_maps`） |
| D6 | URL 安全 | **内网裸 fid** |
| D7 | Mac 进程 | 见下方 **推荐形态** |

### 9.2 Mac 进程形态（推荐）

本方案 **不需要** 全量 Mode A 对话网关（无需设备连本地 `:8765` 做 ASR/TTS）。推荐拆成 **两个常驻进程**，与 Mode A **互斥**：

```text
┌─────────────────────────────────────────────────────────┐
│  A. xiaozhi-media（launchd: com.user.xiaozhi-media）     │
│     · 基于现有 server，开「瘦模式」：只起 HTTP :8766       │
│     · /stream/quark/{fid} → 拉夸克 → ffmpeg → 统一 MP3    │
│     · 内部 API：search / next / resume（供 MCP 调）       │
│     · 读写 data/playback_state、series_maps               │
│     · 不起 WebSocket 对话（或不起 :8765）                 │
└─────────────────────────────────────────────────────────┘
                          ▲ localhost HTTP
┌─────────────────────────────────────────────────────────┐
│  B. xiaozhi-mcp-pipe（launchd 或 login 常驻）            │
│     · MCP_ENDPOINT → 云端                                │
│     · 工具：search / next / resume → 调 A 的 localhost   │
│     · 不推 Opus、不持有设备 WS 会话                       │
└─────────────────────────────────────────────────────────┘

设备：OTA → xiaozhi.me；固件自带 play_url/stop
```

| 模式 | 启用 | 停用 |
|------|------|------|
| **云端+HTTP（本方案）** | media + mcp_pipe；设备官方云 | Mode A 全量 `com.user.xiaozhi-mac-server`（含 :8765 对话） |
| **Mode A 全本地** | 现有全量网关 launchd；设备本地 OTA | mcp_pipe 可关；media 瘦模式不必并行 |

**为何不合成一个进程：** 云端 MCP pipe 是连 `wss://api.xiaozhi.me/mcp` 的长连接，与 HTTP 代理生命周期不同；分开崩溃互不影响，也符合现有 `mcp_pipe.py` 结构。

**为何不用现在的全量 `main.py` 当 A：** 可以先复用同一代码库加 `MEDIA_ONLY=true`（只绑 HTTP），避免再维护第二套夸克逻辑；launchd 与 Mode A 用不同 Label，切模式时 `bootout` / `bootstrap` 其一即可。

### 9.3 仍可后定（不挡开工）

| # | 项 | 建议默认（可改） |
|---|-----|------------------|
| D4 | 播期打断 | 唤醒 → 设备 **stop** 当前 HTTP 播 → 恢复听云端对话；不做复杂 pause |
| D8 | 失败话术 | search 失败 / Mac 不可达：云端短 TTS「现在播不了，稍后再试」 |
| D9 | 验收 | 「冰雪奇缘第一集」→ `0001-…神奇的冰雪魔法`；可 stop；可 next |
| D10 | 切换 runbook | 另写一页：刷官方云 OTA vs `flash-local-ota` + 启停哪个 launchd |

---


## 10. 明确不做（本草案范围外）

- 设备挂 USB 硬盘 / 板载 SD 存整库（硬件不具备或不优先）。
- 恢复 Mode B「云对话 + 本地 WS 灌长 Opus」作为主路径。
- 修改夸克官方客户端；音频仍走现有 Open API + 本机代理。
- 用「Mac 上的 MCP URL」冒充设备端 `play_url`（见 §4.1）。

---

## 11. 参考链接

- 虾哥：固件需实现 URL 播 MP3，播前断开对话 — [78/xiaozhi-esp32#863](https://github.com/78/xiaozhi-esp32/issues/863)
- SD 非官方能力 — [78/xiaozhi-esp32#1053](https://github.com/78/xiaozhi-esp32/issues/1053)
- 设备端 MCP 用法 — [docs/mcp-usage.md](https://github.com/78/xiaozhi-esp32/blob/main/docs/mcp-usage.md)
- 云端 MCP 接入点 — [飞书说明](https://ccnphfhqs21z.feishu.cn/wiki/HiPEwZ37XiitnwktX13cEM5KnSb) · [Seeed Wiki](https://wiki.seeedstudio.com/cn/mcp_endpoint/)
- 本仓库 HTTP 代理 — `docs/QUARK_STREAM_PLAYBACK.md`
