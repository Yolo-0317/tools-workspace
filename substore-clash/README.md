# substore-clash

将 **Sub-Store** 或机场订阅（西部世界、一元机场等）合并为 **Mihomo / Clash Meta** 配置，经 Caddy 对外发布。

| 项 | 值 |
|----|-----|
| 项目路径 | `tools-workspace/substore-clash` |
| 订阅域名 | `sub.yoloworld.site` |
| 本机 clash-gen | http://127.0.0.1:8787 |
| 外网订阅 | https://sub.yoloworld.site:8883/clash.yaml |
| 内网订阅 | https://sub.yoloworld.site:8443/clash.yaml |

---

## 一句话

`clash-gen` 定时拉取 `.env` 里的机场订阅 → 合并节点 → 生成带 Loyalsoldier 规则的 `clash.yaml` → 客户端订阅更新。

---

## 架构

```
机场订阅（西部世界 | 一元机场）
        │
        ▼
  clash-gen :8787          Sub-Store :3001（可选，合并订阅）
        │                        │
        └──────── merge ─────────┘
                    │
                    ▼
            内存缓存 clash.yaml
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
 127.0.0.1:8787          Caddy sub.yoloworld.site
 /clash.yaml             :8883 外网 / :8443 内网
 /clash-verge.yaml
```

**Docker 服务**

| 服务 | 端口 | 作用 |
|------|------|------|
| `substore-clash-store` | 127.0.0.1:3001 | Sub-Store 管理（可选） |
| `substore-clash-gen` | 127.0.0.1:8787 | 订阅生成与 HTTP 分发 |

---

## 订阅地址

`SUB_STORE_FRONTEND_BACKEND_PATH` 见 `.env`；重装或更换后以 `.env` 为准。

### 客户端导入（推荐）

| 场景 | URL |
|------|-----|
| **外网 Clash 订阅** | https://sub.yoloworld.site:8883/clash.yaml |
| **内网 Clash 订阅** | https://sub.yoloworld.site:8443/clash.yaml |
| 带 token | 上述 URL 加 `?token=<CLASH_SUB_TOKEN>` |
| **Verge 轻量订阅** | https://sub.yoloworld.site:8883/clash-verge.yaml |
| 本机调试 | http://127.0.0.1:8787/clash.yaml |

路由器须映射 **8883** → 本机（`sidestore-infra` 的 `EXTERNAL_HTTPS_PORT`）。

### 管理与其他

| 说明 | 外网 `:8883` | 内网 `:8443` |
|------|-------------|-------------|
| Sub-Store | `https://sub.yoloworld.site:8883/sub-store/?api=…` | 端口改 8443 |
| clash-gen 健康检查 | — | http://127.0.0.1:8787/health |
| 手动刷新缓存 | — | http://127.0.0.1:8787/refresh |

同域其他服务（Anisette、Alist/Jellyfin 等）见 `sidestore-infra` 文档。

**客户端内核**：Clash Verge / Mihomo Party / ClashMi / Stash 选 **Clash Meta**（Stash 内核亦可）。

---

## 两种配置

| | **完整版** `clash.yaml` | **轻量版** `clash-verge.yaml` |
|--|-------------------------|--------------------------------|
| 路径 | `/clash.yaml` | `/clash-verge.yaml` 或 `?verge=1` |
| 规则集 | 12 个在线 rule-providers | 无，内联 GEOIP + OpenAI |
| 节点数 | 全部（自动选择最多 80） | 50 个优先节点 |
| 适用 | Stash / 日常完整分流 | Verge 首次导入（避免长时间转圈） |

---

## 策略组

| 策略组 | 类型 | 说明 |
|--------|------|------|
| **自动选择** | url-test | **单组**，含各区域节点；空闲 → 均衡 → 默认 → 爆满 排序，最多 80 个 |
| **ChatGPT** | select | 节点名含 `chatgpt` + OpenAI 规则 |
| **PROXY** | select | 通用代理 |
| **GLOBAL** | select | 全局 |
| Loyalsoldier 组 | select | applications / google / direct / …（见规则表） |

> 已无 `自动选择-港/日/美/台/其他` 等分区子组。

**节点过滤**（生成时自动剔除）：

- 名称含 `商务`、`游戏`
- 占位节点（127.0.0.x、剩余流量提示等）
- Stash 不支持的 `xhttp` 传输

多机场节点加前缀：`[西部世界]`、`[一元机场]`（`SUB_SOURCE_LABELS`）。

---

## 规则分流

| 规则集 | 策略组 |
|--------|--------|
| applications / private / icloud / apple / direct / lancidr / cncidr | DIRECT |
| reject | REJECT |
| OpenAI | **ChatGPT** |
| Claude | AI-优选 |
| google / proxy / telegramcidr | PROXY |
| 未命中 | **自动选择** |

规则 CDN（客户端运行时拉取）：

- https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/proxy.txt
- https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI.yaml

---

## 配置（`.env`）

```bash
cp .env.example .env
```

| 变量 | 说明 |
|------|------|
| `SUBSCRIPTION_URLS` | 机场订阅 URL，多个用 `\|` 分隔（**当前主方式**） |
| `SUB_SOURCE_LABELS` | 节点前缀，与 URL 顺序对应，如 `西部世界\|一元机场` |
| `SUBSTORE_COLLECTION_URL` | 可选；Sub-Store collection 地址，**优先于** SUBSCRIPTION_URLS |
| `SUB_STORE_FRONTEND_BACKEND_PATH` | Sub-Store API 随机路径前缀 |
| `SUBSCRIPTION_REFRESH_SECONDS` | 后台刷新间隔，默认 `21600`（6h）；`0` = 每次请求现拉 |
| `CLASH_SUB_TOKEN` | 订阅访问 token，外网建议设置 |
| `CLASH_GEN_PORT` | 默认 `8787` |

生成随机 Sub-Store 路径：

```bash
echo "/$(openssl rand -hex 12)"
```

**勿提交 `.env`**（含机场 token）。

---

## 快速开始

```bash
cd substore-clash
cp .env.example .env
# 编辑 SUBSCRIPTION_URLS、SUB_STORE_FRONTEND_BACKEND_PATH 等
docker compose up -d --build
curl -s http://127.0.0.1:8787/health
curl -s http://127.0.0.1:8787/clash.yaml | head
```

代码变更后需重建容器才生效：

```bash
docker compose up -d --build clash-gen
curl -s http://127.0.0.1:8787/refresh
```

---

## 运维

### 缓存刷新

`clash-gen` 默认每 **6 小时** 后台拉取机场并更新内存缓存；客户端读缓存，响应快。

```bash
curl -s http://127.0.0.1:8787/refresh          # 立即刷新
curl -s http://127.0.0.1:8787/health           # 含 cache_age_sec
curl -s "http://127.0.0.1:8787/clash.yaml?force=1"  # 强制刷新并返回
```

建议客户端「订阅更新间隔」与 `SUBSCRIPTION_REFRESH_SECONDS` 对齐（6 小时）。

### HTTP 端点

| 路径 | 方法 | 说明 |
|------|------|------|
| `/clash.yaml` | GET/HEAD | 完整配置 |
| `/clash-verge.yaml` | GET/HEAD | 轻量配置 |
| `/clash.yaml?verge=1` | GET | 轻量配置（别名） |
| `/refresh` | GET | 刷新缓存 |
| `/health` | GET | 健康检查 |

配置了 `CLASH_SUB_TOKEN` 时，以上 URL 须带 `?token=`。

### Sub-Store 合并（可选）

1. 打开 Sub-Store 管理页，添加西部世界、一元机场
2. 新建 collection（如 `all`）
3. 将 collection 的 ClashMeta 下载地址写入 `SUBSTORE_COLLECTION_URL`

不配置 Sub-Store 时，直接用 `SUBSCRIPTION_URLS` 即可。

---

## Clash Verge 导入

完整版含 12 个在线规则集，首次激活会转圈很久 → **请用轻量地址**：

```text
https://sub.yoloworld.site:8883/clash-verge.yaml
# 或本机
http://127.0.0.1:8787/clash-verge.yaml
```

步骤：

1. `curl -s http://127.0.0.1:8787/health` 确认服务在跑
2. `curl -sI http://127.0.0.1:8787/clash-verge.yaml` 应返回 `200`（支持 HEAD）
3. Verge → **配置** → 粘贴订阅链接 → **导入** → 激活
4. **设置** → 内核 **Mihomo** → 系统代理 → 模式 **规则**

若 `Connect` 失败，本地文件导入：

```bash
curl -o ~/Downloads/clash.yaml http://127.0.0.1:8787/clash-verge.yaml
```

---

## 域名部署

Caddy 配置在 `sidestore-infra/caddy/Caddyfile`；`DDNS_SUBDOMAINS` 需含 `sub`。

```bash
cd sidestore-infra
bash scripts/run-ddns.sh
docker compose restart caddy
```

片段备份：`caddy/Caddyfile.snippet`。

---

## 目录结构

```text
substore-clash/
├── README.md
├── docker-compose.yml
├── .env.example
├── clash-gen/
│   ├── main.py              # 合并订阅、生成 YAML、HTTP 服务
│   ├── rules_order.yaml     # 规则顺序
│   ├── rule_providers.yaml  # Loyalsoldier 规则集
│   └── Dockerfile
├── caddy/Caddyfile.snippet  # 反代片段（已合并进 sidestore-infra）
└── data/sub-store/          # Sub-Store 数据（git 忽略）
```

---

## 安全建议

- 勿提交 `.env`、勿对外分享机场订阅 URL
- 外网启用 `CLASH_SUB_TOKEN`
- `SUB_STORE_FRONTEND_BACKEND_PATH` 保持随机、足够长
- Sub-Store 管理页建议仅自用
