# tools-workspace

个人工具 monorepo：A 股数据、SideStore 基础设施、Clash 订阅等。子项目 `stock-ai`、`sidestore-infra` 有**独立 git**，本仓库只跟踪工作空间壳层与共享脚本。

| 项目 | 说明 | 路径 | Git |
|------|------|------|-----|
| [stock-ai](./stock-ai) | A 股数据、选股、Tushare MCP、投资 agent | `stock-ai/` | 独立仓库 |
| [sidestore-infra](./sidestore-infra) | SideStore / Caddy / DDNS / 证书 | `sidestore-infra/` | 独立仓库 |
| [substore-clash](./substore-clash) | Sub-Store + Clash 订阅生成 | `substore-clash/` | 本仓库 |

## Agent 工作流

- **Superpowers**：设计 / TDD / 计划（`/add-plugin superpowers`）
- **Hermes**：十步循环 + `project-memory.mdc` 等记忆文件

详见 [AGENTS.md](./AGENTS.md)。

## 打开工作空间

```bash
cursor /Users/yolo/dev/yolo/tools-workspace
# 或多根工作区
cursor /Users/yolo/dev/yolo/tools-workspace/tools-workspace.code-workspace
```

## Docker 开机自启

登录 macOS 后自动启动 Docker，并拉起常用 compose 栈：

```bash
./scripts/install-docker-launchd.sh   # Docker Desktop AutoStart + launchd
./scripts/docker-autostart.sh         # 手动幂等 compose up -d
```

日志：`logs/docker-autostart.log`。各 compose 内服务建议 `restart: unless-stopped`。

**本脚本会拉起的栈**（路径见 `scripts/docker-autostart.sh`）：

| 栈 | 说明 |
|----|------|
| `~/dev/docker/mysql` | 宿主机 MySQL（stock-ai 等依赖） |
| `~/docker/jellyfin-stack` | Jellyfin + 媒资 |
| `sidestore-infra` | SideStore / Caddy |
| `substore-clash` | 订阅与 Sub-Store |
| `stock-ai/docker/daily-sync` | 工作日 17:00 Tushare 日线同步 |
| `stock-ai/stock_analysis` | 分析前后端 |

## 常用命令

### stock-ai（在子仓库内操作）

```bash
cd stock-ai
cp .env.example .env   # 填写 TUSHARE_TOKEN、MYSQL_URL
./run_sync_daily.sh
# 或 Docker 定时：见 stock-ai/docker/daily-sync/README.md
```

### sidestore-infra

```bash
cd sidestore-infra
./scripts/setup.sh
./scripts/healthcheck.sh
docker compose --env-file .env ps
```

### substore-clash

```bash
cd substore-clash
cp .env.example .env
docker compose --env-file .env up -d --build
```

说明与 URL 见 [substore-clash/README.md](./substore-clash/README.md)。

## 目录结构

```
tools-workspace/
├── README.md
├── AGENTS.md
├── scripts/                 # docker-autostart、install-docker-launchd
├── launchd/                 # com.user.docker-stacks.plist
├── substore-clash/          # Clash 订阅（git 跟踪）
├── .cursor/rules/           # Hermes、Superpowers、记忆
├── stock-ai/                # → 独立 git（本仓库 .gitignore）
└── sidestore-infra/         # → 独立 git（本仓库 .gitignore）
```

## 兼容路径

旧路径保留符号链接，避免外部脚本中断：

- `~/dev/yolo/stock-ai` → `tools-workspace/stock-ai`
- `~/sidestore-infra` → `tools-workspace/sidestore-infra`

新配置请统一使用 `tools-workspace/` 下路径。

## 安全说明

- **勿提交** `.env`、密钥、证书私钥；仓库内仅保留 `.env.example` 占位。
- `stock-ai`、`sidestore-infra` 请在各自仓库内单独 `git push`。
