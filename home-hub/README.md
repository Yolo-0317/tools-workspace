# Home Hub

个人运维与投资看板：**Vue 3** 前端 + FastAPI 后端，**单服务** `127.0.0.1:8780`（launchd 登录自启）。

## 模块

| 页面 | 路径 | 数据 |
|------|------|------|
| 总览 | `/` | MySQL 快照 + 选股 + SOP |
| 持仓 | `/portfolio` | 执行卡 sync + 每日快照 |
| 选股 | `/selection` | `selection_daily_results` + SOP |
| 监控 | `/monitor` | `alert_rules` + 触发状态 |
| 任务 | `/jobs` | launchd plist（含 host-jobs；Docker scheduler cron 见 [stock-ai/docs/SCHEDULING.md](../stock-ai/docs/SCHEDULING.md)） |
| **服务** | `/services` | 本地服务目录 + 健康探针 + Jellyfin 映射 |
| 聊天 | `/chat` | Cursor CLI（`agent login`，同 wechat-acp） |

## 快速开始

```bash
cd home-hub
cp .env.example .env   # 本机 agent login 即可，无需 API Key

cd frontend && npm install && npm run build
./scripts/install-launchd.sh    # 登录自启，仅 :8780
```

改前端或后端后：

```bash
./scripts/restart.sh --build   # 构建 + 重启
# 或仅重启
./scripts/restart.sh
```

未装 launchd 时前台启动：`./scripts/start.sh`（同样 :8780）。

访问：**http://127.0.0.1:8780**

## 公网 HTTPS

1. **证书**（新增 `hub` 子域 SAN）  
   ```bash
   cd sidestore-infra
   # .env 中 DDNS_SUBDOMAINS 含 hub
   ./scripts/issue-certs.sh
   ```

2. **Basic Auth**  
   ```bash
   export HUB_BASIC_AUTH_USER=hub
   export HUB_BASIC_AUTH_PASSWORD='你的强密码'
   ./scripts/setup-home-hub-auth.sh
   docker compose restart caddy
   ```

3. 访问：`https://hub.yoloworld.site:8883`（外网端口见 sidestore `.env`）

由 Caddy 反代 `127.0.0.1:8780` + Basic Auth。

## API

- 聊天：`/api/chat/*`
- 看板：`/api/dashboard/summary|portfolio|monitor/*|jobs`
- 服务：`/api/services/catalog|jellyfin|health-summary`

详见 [docs/chat-design.md](docs/chat-design.md)、[TOOLS.md](TOOLS.md)

**聊天**：本机 `agent login` 后可用（与 wechat-acp 相同，模型 `auto`）。  
**页面测试**：一律用 OpenCLI（见 TOOLS.md），打开 `http://127.0.0.1:8780`。
