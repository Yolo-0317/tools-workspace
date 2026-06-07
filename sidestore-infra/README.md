# sidestore-infra

Mac 上的 **SideStore 自托管基础设施**：Anisette 服务、HTTPS 反代、阿里云 DDNS、Let's Encrypt 证书；并统一对外暴露 Alist/Jellyfin、Clash 订阅等宿主机服务。

| 项 | 值 |
|----|-----|
| 项目路径 | `tools-workspace/sidestore-infra` |
| 兼容链接 | `~/sidestore-infra` → 本目录（勿随意删除） |
| 域名 | `yoloworld.site` |
| 外网 HTTPS | `:8883`（路由器映射） |
| 内网 HTTPS | `:8443` |

---

## 一句话

Docker 跑 **anisette** + **Caddy**；证书用 **acme.sh DNS-01（阿里云）** 签发，无需映射 80/443；DDNS 把子域指到家庭公网 IP；Caddy 按子域反代 SideStore、Alist、Jellyfin、clash-gen 等。

---

## 架构

```
                    阿里云 DDNS（每 5 分钟）
                    ani / config / alist / www / sub
                              │
                              ▼
路由器  外网 :8883 ──► Mac :8443 ──► sidestore-caddy (443)
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  ani.* → anisette      config.* → servers.json   alist.* → Jellyfin :8096
  :6969 (容器内)         (public/)                  + /jellyfin → :8096
                                                    sub.* → clash :8787
                                                          + Sub-Store :3001
```

**Docker 服务**

| 容器 | 端口 | 作用 |
|------|------|------|
| `sidestore-anisette` | 127.0.0.1:6969 | SideStore Anisette v3 |
| `sidestore-caddy` | 8443、8883 → 443 | HTTPS 反代与静态文件 |

**宿主机服务（Caddy 经 `host.docker.internal` 访问）**

| 服务 | 端口 | 反代路径 |
|------|------|----------|
| clash-gen | 8787 | `sub.*/clash.yaml` |
| Sub-Store | 3001 | `sub.*/sub-store/*` |
| Jellyfin | 8096 | `alist.*/jellyfin` |

clash-gen / Sub-Store 由 [substore-clash](../substore-clash/README.md) 维护；Jellyfin 在 `~/docker/jellyfin-stack`（仓库外）。

---

## 链接速查

路由器须映射 **外网 TCP 8883 → 本机 8443**（`EXTERNAL_HTTPS_PORT` → `INTERNAL_HTTPS_PORT`）。

### SideStore（iPhone）

| 说明 | 外网 `:8883` | 内网 `:8443` |
|------|-------------|-------------|
| Anisette | https://ani.yoloworld.site:8883/ | 端口改 8443 |
| 服务器列表 | https://config.yoloworld.site:8883/servers.json | 同上 |

SideStore 设置 → Anisette List URL 填 **servers.json 外网地址** → 选 **Yolo Home Anisette** → 启用 **LocalDevVPN**。

### 其他子域

| 子域 | 外网示例 | 说明 |
|------|----------|------|
| **alist** | https://alist.yoloworld.site:8883/jellyfin | Jellyfin（根路径重定向至此） |
| **sub** | https://sub.yoloworld.site:8883/clash.yaml | Clash 订阅 |
| | https://sub.yoloworld.site:8883/clash.yaml?verge=1 | Verge 轻量订阅 |
| | https://sub.yoloworld.site:8883/sub-store/… | Sub-Store 管理 |

本机调试 Anisette：`curl http://127.0.0.1:6969/` 应含 `X-Apple-I-MD`。

---

## 配置

```bash
cp .env.example .env
# 编辑 ACME_EMAIL、端口、DDNS_SUBDOMAINS 等
```

创建 `.env.secrets`（**勿提交 git**）：

```bash
ALIBABA_CLOUD_ACCESS_KEY_ID=你的KeyId
ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的KeySecret
```

也可写入 `~/.zshrc`，首次 `issue-certs.sh` 会自动同步到 `.env.secrets`。

| 变量 | 说明 |
|------|------|
| `DOMAIN` | 主域名，默认 `yoloworld.site` |
| `*_SUBDOMAIN` | 各子域前缀（ani / config / alist / www / sub） |
| `INTERNAL_HTTPS_PORT` | 本机 Caddy HTTPS，默认 `8443` |
| `EXTERNAL_HTTPS_PORT` | 路由器外网端口，默认 `8883` |
| `DDNS_SUBDOMAINS` | DDNS 同步列表，须含证书 SAN 中所有子域 |
| `ACME_EMAIL` | Let's Encrypt 注册邮箱 |

---

## 快速开始

```bash
cd sidestore-infra
cp .env.example .env
# 配置 .env + .env.secrets
bash scripts/setup.sh
```

`setup.sh` 依次：DDNS 同步 → 签发证书（若无）→ `docker compose up -d` → 健康检查。

仅重启栈：

```bash
docker compose --env-file .env up -d
bash scripts/healthcheck.sh
```

---

## 运维

### 健康检查

```bash
bash scripts/healthcheck.sh
```

检查项：Docker 容器、证书文件、Anisette 本地/HTTPS、servers.json、clash.yaml、公网可达性（WARN 不致命）、可选 Jellyfin 播放验证。

### 证书

| 操作 | 命令 |
|------|------|
| 首次签发 | `bash scripts/issue-certs.sh` |
| 强制重签（增子域后） | 同上（含 `--force`） |
| 手动续期 | `bash scripts/renew-certs.sh` |
| 自动续期 | launchd 每周一 04:00 |

证书 SAN：`ani`、`config`、`alist`、`www`、`sub` 五个子域。新增子域须同时改 `issue-certs.sh` 调用、`DDNS_SUBDOMAINS` 和 `caddy/Caddyfile`。

### DDNS

```bash
bash scripts/run-ddns.sh
```

launchd 每 **5 分钟** 自动运行（`com.user.aliyun-ddns`）。

### 更新镜像

```bash
bash scripts/update.sh
```

### launchd 自启

```bash
bash scripts/install-launchd.sh
```

| Label | 作用 |
|-------|------|
| `com.user.sidestore-infra` | 登录后 Docker compose `up -d`（每 10 分钟兜底） |
| `com.user.aliyun-ddns` | DDNS 同步 |
| `com.user.sidestore-certs` | 证书续期 |

改 plist 路径后**必须重跑** `install-launchd.sh`。

---

## Caddy 路由（`caddy/Caddyfile`）

| 域名块 | 行为 |
|--------|------|
| `ani.yoloworld.site` | → `anisette:6969` |
| `config.yoloworld.site` | `/servers.json` 静态文件 |
| `alist.yoloworld.site` | `/jellyfin` → Jellyfin |
| `www.yoloworld.site` | → 重定向 `hub` |
| `sub.yoloworld.site` | `/clash.yaml` → clash-gen；`/sub-store/*` → Sub-Store |

Caddy 使用 `auto_https off`，证书来自 `certs/fullchain.cer` + `certs/key.key`（acme.sh 安装，非 Caddy 自动 ACME）。

---

## 目录结构

```text
sidestore-infra/
├── README.md
├── docker-compose.yml
├── .env.example / .env / .env.secrets
├── caddy/Caddyfile
├── certs/                  # TLS（git 忽略）
├── public/
│   └── servers.json        # SideStore 服务器列表
├── anisette/data/          # Anisette 持久化（git 忽略）
├── scripts/
│   ├── setup.sh            # 一键部署
│   ├── healthcheck.sh
│   ├── issue-certs.sh / renew-certs.sh
│   ├── run-ddns.sh / aliyun_ddns.py
│   ├── install-launchd.sh
│   └── lib/env.sh          # 加载阿里云密钥
└── launchd/*.plist
```

---

## 常见问题

**SideStore 连不上 Anisette**

- iPhone 开 LocalDevVPN
- 确认路由器 `8883 → 8443` 已映射
- `bash scripts/run-ddns.sh` 后 DNS 是否指向当前公网 IP
- `bash scripts/healthcheck.sh`

**clash.yaml 404 / 证书错误**

- 确认 `substore-clash` 的 clash-gen 在跑：`curl http://127.0.0.1:8787/health`
- 证书 SAN 须含 `sub.yoloworld.site`（重签后 `docker compose restart caddy`）

**launchd 找不到目录**

- plist 已指向 `tools-workspace/sidestore-infra`；勿删 `~/sidestore-infra` 符号链接除非已更新 plist

**增子域（例：新服务 `foo.yoloworld.site`）**

1. `.env` + `DDNS_SUBDOMAINS` 加 `foo`
2. `issue-certs.sh` 加 `-d foo.yoloworld.site`
3. `Caddyfile` 新增站点块
4. `run-ddns.sh` + `docker compose restart caddy`

---

## 安全建议

- 勿提交 `.env`、`.env.secrets`、`certs/`
- 阿里云密钥最小权限（AliDNS 读写）
- Sub-Store 管理页仅自用；外网可配 `CLASH_SUB_TOKEN`（见 substore-clash）

---

## 相关项目

| 项目 | 关系 |
|------|------|
| [substore-clash](../substore-clash/README.md) | clash-gen + Sub-Store，Caddy `sub.*` 反代 |
| [stock-ai](../stock-ai/README.md) | 部分脚本读 `sidestore-infra/.env` 的 TMDB 等 |
| `~/docker/jellyfin-stack` | Jellyfin，Caddy `alist.*/jellyfin` 反代 |
