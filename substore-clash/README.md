# substore-clash

将 **Sub-Store** 或机场订阅（西部世界、一元机场等）合并为 **Mihomo / Clash Meta** 配置，经 `sub.yoloworld.site` 对外发布。

---

## 链接速查

`SUB_STORE_FRONTEND_BACKEND_PATH` 见 `.env`（示例占位：`<your-backend-path>`）；重装或更换后以 `.env` 为准。

### 外网（`8883`）

路由器须映射 **`8883`** → 本机（`sidestore-infra` 的 `EXTERNAL_HTTPS_PORT`）。Clash 客户端导入订阅请用本节地址。

| 说明 | URL |
|------|-----|
| **Clash 订阅** | https://sub.yoloworld.site:8883/clash.yaml |
| Clash 订阅（带 token） | `https://sub.yoloworld.site:8883/clash.yaml?token=<CLASH_SUB_TOKEN>` |
| **Sub-Store 管理** | `https://sub.yoloworld.site:8883/sub-store/?api=https://sub.yoloworld.site:8883/<SUB_STORE_FRONTEND_BACKEND_PATH>` |
| SideStore Anisette | https://ani.yoloworld.site:8883 |
| SideStore 服务器列表 | https://config.yoloworld.site:8883/servers.json |
| Alist / Jellyfin | https://alist.yoloworld.site:8883 |

### 内网（`8443` / 本机直连）

同一台 Mac 上、或局域网内访问 Caddy 时用 **`8443`**（`INTERNAL_HTTPS_PORT`）。域名仍解析到本机公网 IP 时，需在同网或 hosts 指向该 Mac。

| 说明 | URL |
|------|-----|
| **Clash 订阅** | https://sub.yoloworld.site:8443/clash.yaml |
| Clash 订阅（带 token） | `https://sub.yoloworld.site:8443/clash.yaml?token=<CLASH_SUB_TOKEN>` |
| **Sub-Store 管理** | `https://sub.yoloworld.site:8443/sub-store/?api=https://sub.yoloworld.site:8443/<SUB_STORE_FRONTEND_BACKEND_PATH>` |
| SideStore Anisette | https://ani.yoloworld.site:8443 |
| SideStore 服务器列表 | https://config.yoloworld.site:8443/servers.json |
| Alist / Jellyfin | https://alist.yoloworld.site:8443 |

**本机直连（不经 Caddy、仅 loopback）**

| 说明 | URL |
|------|-----|
| clash-gen 订阅 | http://127.0.0.1:8787/clash.yaml |
| clash-gen 健康检查 | http://127.0.0.1:8787/health |
| Sub-Store 管理 | `http://127.0.0.1:3001/?api=http://127.0.0.1:3001/<SUB_STORE_FRONTEND_BACKEND_PATH>` |

在 Clash Verge / Mihomo Party 中选择 **Clash Meta** 内核；外网用 `8883` 订阅，仅本机调试可用 `127.0.0.1:8787`。

### 机场源订阅（仅服务端 `.env`，勿写入客户端）

配置在 `substore-clash/.env` 的 `SUBSCRIPTION_URLS`，当前为 **西部世界** + **一元机场** 两条，由 `clash-gen` 拉取合并；勿对外分享或提交 git。

---

## 功能

- Docker：[Sub-Store](https://github.com/sub-store-org/Sub-Store) + `clash-gen`
- 规则：[Loyalsoldier/clash-rules](https://github.com/Loyalsoldier/clash-rules) 白名单 + [blackmatrix7](https://github.com/blackmatrix7/ios_rule_script) OpenAI/Claude
- **OpenAI** → 策略组 `ChatGPT`（节点名须含 `chatgpt`，不区分大小写）

## 快速开始

```bash
cd /Users/yolo/dev/yolo/tools-workspace/substore-clash
cp .env.example .env
# 编辑 .env：SUB_STORE_FRONTEND_BACKEND_PATH、SUBSCRIPTION_URLS
docker compose up -d --build
```

生成随机 Sub-Store API 路径：

```bash
echo "/$(openssl rand -hex 12)"
```

### Sub-Store 合并订阅（可选）

1. 打开上表「Sub-Store 管理」中的外网或本地地址
2. 添加西部世界、一元机场订阅 → 新建 collection（如 `all`）
3. 将 collection 的 ClashMeta 地址写入 `.env` 的 `SUBSTORE_COLLECTION_URL`（容器内 host 为 `sub-store`）

不配置 Sub-Store 时，可直接用 `.env` 中的 `SUBSCRIPTION_URLS`（当前默认方式）。

## 规则说明

| 规则集 | 策略组 |
|--------|--------|
| applications / private / icloud / apple / direct / lancidr / cncidr | DIRECT |
| reject | REJECT |
| OpenAI | **ChatGPT** |
| Claude | AI-优选 |
| google / proxy / telegramcidr | PROXY |
| 未命中 | **PROXY**（默认走「自动选择」） |

规则 CDN（客户端运行时拉取）示例：

- https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/proxy.txt
- https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI.yaml

## 域名部署

Caddy 配置已合并进 `sidestore-infra/caddy/Caddyfile`；`DDNS_SUBDOMAINS` 需含 `sub`。

```bash
cd /Users/yolo/dev/yolo/tools-workspace/sidestore-infra
bash scripts/run-ddns.sh
docker compose restart caddy
```

片段备份：`substore-clash/caddy/Caddyfile.snippet`。

## 目录结构

```
substore-clash/
├── docker-compose.yml
├── clash-gen/              # 合并订阅 + 生成 YAML
├── caddy/Caddyfile.snippet
└── data/sub-store/         # git 忽略
```

## 安全建议

- 勿提交 `.env`（含机场 token）
- 外网建议设置 `CLASH_SUB_TOKEN`，订阅 URL 带 `?token=`
- `SUB_STORE_FRONTEND_BACKEND_PATH` 保持随机、足够长
