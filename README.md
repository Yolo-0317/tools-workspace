# tools-workspace

个人工具工作空间，统一操作以下两个项目：

| 项目 | 说明 | 实际路径 |
|------|------|----------|
| [stock-ai](./stock-ai) | A 股数据分析、选股、MCP、投资 agent | `/Users/yolo/dev/yolo/stock-ai` |
| [sidestore-infra](./sidestore-infra) | SideStore / Caddy / DDNS / 证书等基础设施 | `/Users/yolo/sidestore-infra` |

两个子目录是**符号链接**，指向原有位置。这样可以在本工作空间统一浏览和操作，同时不破坏 sidestore-infra 的 launchd、Docker 等已有绝对路径配置。

## 打开工作空间

在 Cursor / VS Code 中打开：

```bash
cursor /Users/yolo/dev/yolo/tools-workspace/tools-workspace.code-workspace
```

或直接打开本目录作为根工作区。

## 常用命令

### stock-ai

```bash
cd stock-ai
source .venv/bin/activate
python scripts/sync_tushare_daily_to_mysql.py   # 同步日线数据
```

### sidestore-infra

```bash
cd sidestore-infra
./scripts/setup.sh          # 首次/完整 setup
./scripts/healthcheck.sh    # 健康检查
docker compose --env-file .env ps
```

## 目录结构

```
tools-workspace/
├── README.md
├── tools-workspace.code-workspace   # 多根工作区配置
├── stock-ai/          -> /Users/yolo/dev/yolo/stock-ai
└── sidestore-infra/   -> /Users/yolo/sidestore-infra
```

## 说明

- `stock-ai` 是独立 git 仓库（GitHub: Yolo-0317/stock-ai）
- `sidestore-infra` 目前无 git，位于 `$HOME/sidestore-infra`
- 本仓库只管理工作空间本身的配置（README、Cursor 规则、code-workspace 文件）
