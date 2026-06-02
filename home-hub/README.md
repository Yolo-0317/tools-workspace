# Home Hub

个人运维与投资看板：**Vue 3** 前端 + FastAPI 后端，**单服务** `127.0.0.1:8780`（launchd 登录自启）。

## 导航结构

| 分组 | 页面 |
|------|------|
| **投资** | 总览、持仓、选股、监控 |
| **系统** | 任务、服务、聊天 |

H5 底部：**投资**（展开子菜单）｜**聊天**｜**更多**（任务、服务）。桌面顶栏：**投资** 下拉 + 任务 / 服务 / 聊天。

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

2. **登录账号**（在 `home-hub/.env` 配置，Caddy 仅反代不再做 Basic Auth）  
   ```bash
   HUB_REQUIRE_AUTH=1
   HUB_ADMIN_USER=admin
   HUB_ADMIN_PASSWORD='管理员密码'
   HUB_SHARE_USER=share
   HUB_SHARE_PASSWORD='分享密码'
   # 公网 HTTPS 建议开启 Secure Cookie
   HUB_SESSION_COOKIE_SECURE=1
   ```

   改 `.env` 后：`cd home-hub && ./scripts/restart.sh`

3. 访问 `https://hub.yoloworld.site:8883` → 登录页  
   - **admin**：全部页面与 API  
   - **share**：仅 `/selection`（选股 + K 线 + SOP，无持仓标记）  
   - **公开**：`/news`、`/m/news` 及 `/api/dashboard/news/*` 无需登录（AI 解读为公开版，不含持仓/P0～P4 操作提示）  
   - **公开 API 防护**（默认开启）：IP 限流 + 短窗口 burst；无 `X-Hub-Client: home-hub` 更严；拦截 curl/python 等 UA；`limit` 上限见 `HUB_NEWS_MAX_LIMIT`

由 Caddy 反代 `127.0.0.1:8780`；鉴权由 Home Hub 会话 Cookie 负责。

## API

- 聊天：`/api/chat/*`
- 看板：`/api/dashboard/summary|portfolio|monitor/*|jobs`
- 服务：`/api/services/catalog|jellyfin|health-summary`

详见 [docs/chat-design.md](docs/chat-design.md)、[TOOLS.md](TOOLS.md)

**聊天**：本机 `agent login` 后可用（`agent acp`，同 wechat-acp）。  
**页面测试**：一律用 OpenCLI（见 TOOLS.md），打开 `http://127.0.0.1:8780`。
