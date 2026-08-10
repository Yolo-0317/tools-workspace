# 百度网盘 MCP 操作指南

> **现状（2026-07）**：本仓库 **尚未实现** `baidu-audio` MCP。本地已接通的是夸克：`mcp_config.json` → `quark-audio`。  
> 本文说明：官方怎么开权限、拿到 token 后怎么测、以及将来如何挂进与夸克相同的小智 MCP 管线。

相关文档：

- 夸克现网：[MCP_QUARK_PLAYBACK.md](./MCP_QUARK_PLAYBACK.md)
- 设计对照：[QUARK_STREAM_PLAYBACK.md](./QUARK_STREAM_PLAYBACK.md)（文中写明百度可复用同一模式）
- 开放平台：[使用准备](https://pan.baidu.com/union/doc/Wm9sl0i0j) · [接入流程](https://pan.baidu.com/union/doc/%E5%B9%B3%E5%8F%B0%E7%AE%80%E4%BB%8B/%E6%8E%A5%E5%85%A5%E6%B5%81%E7%A8%8B/)

---

## 1. 先搞清两套「MCP」

| 类型 | 是什么 | 百度要做的事 |
|------|--------|----------------|
| **云端 MCP 接入点** | Mac 上的工具经 `MCP_ENDPOINT` 接到 xiaozhi.me | 搜网盘、返回 `stream_url` |
| **设备端 MCP** | 固件里的 `self.audio.play_url` 等 | 设备拉 URL 出声（已有则可复用） |

播有声书到 Pyramid：云端/本地工具负责「找百度文件 + 拼本机代理 URL」；设备仍用现有 `play_url` / 或 Mode A 推 Opus。

---

## 2. 开放平台准入（必须先做）

### 2.1 注册与认证

1. 打开 [百度网盘开放平台](https://pan.baidu.com/union)  
2. 百度账号登录  
3. 申请接入 → 同意协议  
4. 完成 **个人实名**（若要企业能力再做企业认证）

### 2.2 创建应用

1. 控制台 → 创建应用（类别选网盘相关）  
2. 记下：

| 字段 | 含义 |
|------|------|
| AppId | 应用 ID |
| AppKey (AK) | OAuth `client_id` |
| SecretKey (SK) | OAuth `client_secret` |
| SignKey | 部分签名接口用 |

3. **安全设置** → 配置 **OAuth 回调地址** `redirect_uri`  
   - 有本机服务：例如 `http://127.0.0.1:8766/oauth/baidu/callback`  
   - 无服务端试玩：可用文档中的 `oob`（简化模式）

### 2.3 获取 Access Token

`scope` 固定传：`basic,netdisk`

**本机推荐：授权码模式（可刷新）**

```text
1) 浏览器打开授权页（替换 YOUR_*）：
http://openapi.baidu.com/oauth/2.0/authorize
  ?response_type=code
  &client_id=YOUR_APP_KEY
  &redirect_uri=YOUR_REDIRECT_URI
  &scope=basic,netdisk
  &display=popup

2) 同意后回调带 ?code=CODE

3) 换 token：
GET https://openapi.baidu.com/oauth/2.0/token
  ?grant_type=authorization_code
  &code=CODE
  &client_id=YOUR_APP_KEY
  &client_secret=YOUR_SECRET_KEY
  &redirect_uri=YOUR_REDIRECT_URI

4) 保存返回的：
   - access_token   （约 30 天）
   - refresh_token  （约 10 年）
```

**刷新：**

```text
GET https://openapi.baidu.com/oauth/2.0/token
  ?grant_type=refresh_token
  &refresh_token=YOUR_REFRESH_TOKEN
  &client_id=YOUR_APP_KEY
  &client_secret=YOUR_SECRET_KEY
```

**纯本地临时试（简化模式）**：`response_type=token`，从回调 URL 的 `#access_token=...` 里抄；**不能 refresh**，过期要重登。

建议写入 `xiaozhi-mac-server/.env`：

```bash
BAIDU_APP_ID=...          # 应用 ID；硬件/设备码等场景会用到
BAIDU_APP_KEY=...         # OAuth client_id（必需）
BAIDU_SECRET_KEY=...      # OAuth client_secret（必需）
BAIDU_SIGN_KEY=...        # 部分签名/STS 接口；常规 list/search/dlink 一般不用
BAIDU_ACCESS_TOKEN=...
BAIDU_REFRESH_TOKEN=...
BAIDU_REDIRECT_URI=http://127.0.0.1:8766/oauth/baidu/callback
```

---

## 3. 接口自测清单（不依赖 MCP）

拿到 `access_token` 后，用 curl / 脚本按序验证：

### 3.1 用户信息

```bash
curl -sS "https://pan.baidu.com/rest/2.0/xpan/nas?method=uinfo&access_token=$BAIDU_ACCESS_TOKEN"
```

应返回 `baidu_name` / `uk` 等。

### 3.2 列目录

```bash
curl -sS "https://pan.baidu.com/rest/2.0/xpan/file?method=list&access_token=$BAIDU_ACCESS_TOKEN&dir=/&limit=100"
```

记下目标音频的 `fs_id`。

### 3.3 搜索

```bash
curl -sS "https://pan.baidu.com/rest/2.0/xpan/file?method=search&access_token=$BAIDU_ACCESS_TOKEN&key=冰雪奇缘&dir=/&num=20"
```

### 3.4 取下载地址 dlink

```bash
# fsids 为 JSON 数组，注意 URL 编码
curl -sS "https://pan.baidu.com/rest/2.0/xpan/multimedia?method=filemetas&access_token=$BAIDU_ACCESS_TOKEN&fsids=%5B你的fs_id%5D&dlink=1"
```

### 3.5 下载试听

- `dlink` 有效约 **8 小时**  
- 请求必须带：`User-Agent: pan.baidu.com`  
- 会有 **302**，客户端需跟随跳转  

```bash
curl -L -A "pan.baidu.com" -o /tmp/baidu_test.mp3 \
  "${DLINK}&access_token=${BAIDU_ACCESS_TOKEN}"
ffplay /tmp/baidu_test.mp3
```

以上四步通了，才具备做 MCP / 流媒体代理的条件。

---

## 4. 挂进本仓库小智 MCP（规划操作，代码未合入）

对照夸克现状：

| 夸克（已有） | 百度（待做） |
|--------------|--------------|
| `mcp/quark_audio_server.py` | `mcp/baidu_audio_server.py` |
| `server/quark_client.py` | `server/baidu_client.py` |
| `GET /stream/quark/{fid}` | `GET /stream/baidu/{fsid}` |
| `mcp_config.json` → `quark-audio` | 增加 `baidu-audio` |
| `mcp_pipe.py quark-audio` | `mcp_pipe.py baidu-audio` |

### 4.1 计划中的 `mcp_config.json`

```json
{
  "mcpServers": {
    "quark-audio": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["mcp/quark_audio_server.py"],
      "env": {}
    },
    "baidu-audio": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["mcp/baidu_audio_server.py"],
      "env": {
        "BAIDU_ACCESS_TOKEN": "${BAIDU_ACCESS_TOKEN}"
      }
    }
  }
}
```

### 4.2 计划中的工具名

| Tool | 作用 |
|------|------|
| `search_baidu_audio` | 搜网盘音频 |
| `resolve_baidu_stream_url` | 返回本机 `http://LAN:8766/stream/baidu/{fsid}` |
| `play_baidu_audio` | Mode A：推到已连接设备；或返回 URL 再 `play_url` |
| `baidu_playback_status` | token / 网关 / 设备状态 |

### 4.3 Mode B（云端智能体）日常操作（实现后）

```bash
cd xiaozhi-mac-server
# .env 已有 MCP_ENDPOINT + BAIDU_* 

# 1) 网关（媒体 + 可选本地工具）
bash scripts/run-media-stack.sh

# 2) 把百度 MCP 接到云端（实现后脚本名可能是 run-baidu-mcp-pipe.sh）
python scripts/mcp_pipe.py baidu-audio

# 3) 设备仍需能播（本地 WS 或固件 play_url，与夸克相同约束）
```

xiaozhi.me → 智能体 → 配置角色：提示词增加「听百度网盘内容时调用 `play_baidu_audio` / `resolve_baidu_stream_url`」。

### 4.4 Mode A（全本地）

`USE_MCP_TOOLS=true` 时，在本地 DeepSeek 工具列表中注册百度工具（与 `quark_mcp_tools` 并列），流程同夸克体检脚本思路。

---

## 5. 第三方百度 MCP（可选捷径）

社区有独立「百度网盘 MCP」（列表 / 搜索 / 下载链接等），可：

1. 按其 README 安装并配置 AppKey / Token  
2. 把启动命令写入 `mcp_config.json`  
3. `python scripts/mcp_pipe.py <该 server 名>`  

**局限：** 通常只有文件管理工具，**不会**自动对接本仓库的 Opus 推流或 `/stream/...` 代理。要播到 Pyramid，仍需把返回的 dlink 接到本机代理（或先下载再播）。

---

## 6. 日常排错

| 现象 | 排查 |
|------|------|
| 授权失败 | 回调地址是否与控制台完全一致；`scope` 是否为 `basic,netdisk`（英文逗号） |
| `uinfo` 401 | token 过期 → refresh；或简化模式需重登 |
| 有 dlink 但 403 | 是否设置 `User-Agent: pan.baidu.com`；是否跟 302 |
| 能搜不能播 | 与夸克相同：设备是否在本地网关 / 是否有 `play_url`；代理 URL 是否 LAN 可达 |
| MCP pipe 断线 | `MCP_ENDPOINT` token；本机 `baidu-audio` 进程是否崩溃 |

---

## 7. 建议实施顺序

1. 开放平台建应用 + 本机拿到可 refresh 的 token  
2. curl 跑通 list → search → filemetas → dlink 下载  
3. 实现 `BaiduClient` + `/stream/baidu/{fsid}`  
4. 实现 `baidu_audio_server.py` 并写入 `mcp_config.json`  
5. `mcp_pipe.py baidu-audio` + 改智能体提示词  
6. 用一句「播放百度网盘里的 xxx」做端到端验收  

当前仓库停在第 0 步（无百度代码）。需要开工时从第 1～2 步开始即可。
