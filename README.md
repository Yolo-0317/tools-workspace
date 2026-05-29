# tools-workspace

个人工具 **monorepo**（单一 git 仓库）：A 股数据、SideStore 基础设施、Clash 订阅、Docker 自启脚本等。

| 目录 | 说明 |
|------|------|
| [stock-ai](./stock-ai) | A 股数据、选股、Tushare MCP、投资 agent、日线 Docker 定时同步 |
| [sidestore-infra](./sidestore-infra) | SideStore / Caddy / DDNS / 证书 |
| [substore-clash](./substore-clash) | Sub-Store + Clash 订阅生成 |

## 克隆与配置

```bash
git clone <你的 tools-workspace 远程地址>
cd tools-workspace

# 各子项目复制环境变量模板（勿提交真实 .env）
cp stock-ai/.env.example stock-ai/.env
cp sidestore-infra/.env.example sidestore-infra/.env   # 若有
cp substore-clash/.env.example substore-clash/.env
```

## Agent 工作流

- **Superpowers**：设计 / TDD / 计划（`/add-plugin superpowers`）
- **Hermes**：十步循环 + `.cursor/rules/project-memory.mdc` 等

详见 [AGENTS.md](./AGENTS.md)。

## 打开工作空间

```bash
cursor /Users/yolo/dev/yolo/tools-workspace
# 或多根工作区
cursor tools-workspace.code-workspace
```

## Docker 开机自启

```bash
./scripts/install-docker-launchd.sh
./scripts/docker-autostart.sh   # 手动幂等 compose up -d
```

日志：`logs/docker-autostart.log`。`scripts/docker-autostart.sh` 会拉起 MySQL、Jellyfin、sidestore、substore-clash、stock-ai 日线同步等栈。

## 常用命令

### stock-ai

```bash
cd stock-ai
./run_sync_daily.sh
# Docker 定时：stock-ai/docker/daily-sync/README.md
```

### sidestore-infra

```bash
cd sidestore-infra
./scripts/setup.sh
docker compose --env-file .env ps
```

### substore-clash

见 [substore-clash/README.md](./substore-clash/README.md)。

## 目录结构

```
tools-workspace/          # 本仓库根（唯一 git remote）
├── stock-ai/
├── sidestore-infra/
├── substore-clash/
├── scripts/              # 工作空间级 Docker 自启
├── launchd/
└── .cursor/rules/
```

## 兼容路径

- `~/dev/yolo/stock-ai` → `tools-workspace/stock-ai`
- `~/sidestore-infra` → `tools-workspace/sidestore-infra`

## 安全说明

- **勿提交** `.env`、证书私钥、机场订阅 URL、持仓与 agent 记忆目录。
- 原独立仓库 `stock-ai` 可归档；新变更只提交本 monorepo。

## 创建远程仓库（首次）

```bash
cd tools-workspace
gh repo create tools-workspace --private --source=. --remote=origin
git push -u origin master   # 或 main，与本地分支一致即可
```
