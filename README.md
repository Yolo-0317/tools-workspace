# tools-workspace

个人工具 **monorepo**（单一 git 仓库）：A 股投资自动化、微信 ↔ Cursor、SideStore 基础设施、Clash 订阅合并、Docker 登录自启等。

---

## 子项目一览

| 目录 | 能力摘要 | 详细文档 |
|------|----------|----------|
| [stock-ai](./stock-ai) | 行情入库、选股、回测、MCP、盘中/持仓监控、战报推送 | [stock-ai/README.md](./stock-ai/README.md) |
| [investment-agent](./stock-ai/investment-agent) | 持仓执行卡、投资助手 Agent、OpenCLI 东财 SOP | [investment-agent/README.md](./stock-ai/investment-agent/README.md) |
| [wechat-cursor-acp](./wechat-cursor-acp) | 微信私聊 ↔ Cursor CLI（`agent acp`） | [wechat-cursor-acp/README.md](./wechat-cursor-acp/README.md) |
| [sidestore-infra](./sidestore-infra) | SideStore、Caddy、阿里云 DDNS、Let's Encrypt | [sidestore-infra/scripts/setup.sh](./sidestore-infra/scripts/setup.sh) |
| [substore-clash](./substore-clash) | 双机场订阅合并 → Mihomo/Stash/Verge 配置 | [substore-clash/README.md](./substore-clash/README.md) |

工作空间外（Docker 自启会拉起，非本 repo 子目录）：`~/docker/jellyfin-stack`（Jellyfin NAS/迅雷/夸克）。

---

## stock-ai 能力

### 数据层

| 能力 | 说明 |
|------|------|
| **Tushare → MySQL** | 全市场日线同步（主方案），`scripts/sync/sync_tushare_daily_to_mysql.py` |
| **东财 → MySQL** | 历史补齐、盘中 upsert、分钟快照 |
| **Docker 定时同步** | 工作日收盘后自动入库，`stock-ai/docker/daily-sync/` |
| **Tushare MCP** | Cursor MCP 工具：`tushare_mcp.py`（均线信号、DeepSeek 盘中分析等） |

### 选股与分析

| 能力 | 说明 |
|------|------|
| **多策略选股** | 量价突破、MA5 回踩、底部突破、长期核心等，`scripts/selection/` |
| **每日综合选股** | Top5 + DeepSeek 简评，17:30 launchd 推送微信 |
| **东财 SOP 采集** | Playwright / OpenCLI 八维度个股数据，`scripts/analysis/eastmoney_sop_extract.py` |
| **盘前/午盘/盘后** | `run_premarket_analysis.py` 等分析脚本 |
| **回测** | `scripts/backtest/` |

### 监控与推送（微信 via wechat-acp）

| 脚本 / 任务 | 频率 | 内容 |
|-------------|------|------|
| `push_holdings_monitor.sh` | 交易时段每 **5 分钟** | 持仓执行卡条件监控（OpenCLI 东财现价 → 触发推微信） |
| `push_daily_briefing_wechat.sh` | **09 / 12 / 15 / 20** 点 | 大盘 + 东财快讯 + 国际 + 持仓 + DeepSeek 解读 |
| `push_selection_wechat.sh` | 工作日 **17:30** | 每日选股 Top5 + AI 简评 |
| `push_macro_news_wechat.sh` | 按需 | 东财 7×24 宏观快讯 |
| `push_stock_watch_reminder_wechat.sh` | 一次性 / 按需 | 个股关注提醒 |
| `monitor_intraday_signals.py` | 常驻 / cron | 盘中买卖信号（可选飞书） |

### investment-agent

- **持仓执行卡** `持仓执行卡.md`：P0～P4 操作纪律与价位
- **监控规则** `config/holdings_alerts.json`：与执行卡同步
- **长期记忆** `MEMORY.md`、`memory/YYYY-MM-DD.md`
- **Agent 规范** `.cursor/rules/agent.mdc`（红线：禁补梅花、禁追高等）

---

## wechat-cursor-acp

| 能力 | 说明 |
|------|------|
| 微信 ↔ Cursor | 私聊消息经 `wechat-acp` 交给 `agent acp`，工作区默认 `investment-agent` |
| 登录自启 | `com.user.wechat-cursor-acp` launchd，有 token 时自动重连 |
| 正在输入 | `typing-watcher` 脉冲，减少 Agent 响应前空白 |
| 文本推送 | `stock-ai/scripts/tools/wechat_acp_push_text.py`（战报/监控/选股共用） |

**前置**：Cursor CLI 已 `agent login`；与 QClaw 微信通道互斥（避免 iLink 冲突）。

---

## sidestore-infra

| 能力 | 说明 |
|------|------|
| SideStore | Anisette、服务器列表（`ani.*` / `config.*`） |
| Caddy 反向代理 | 多子域 HTTPS（8443 内网 / 8883 外网） |
| 阿里云 DDNS | 子域自动解析 |
| 证书 | `issue-certs.sh`（含 `sub.yoloworld.site` SAN） |
| 健康检查 | `healthcheck.sh`（含 clash.yaml HTTPS 探测） |

launchd：`com.user.sidestore-infra`、`com.user.sidestore-certs`、`com.user.aliyun-ddns`（见子目录 `launchd/`）。

---

## substore-clash

| 能力 | 说明 |
|------|------|
| Sub-Store | 西部世界 + 一元机场订阅合并管理 |
| clash-gen | 生成 Mihomo/Stash/ClashMi 兼容 `clash.yaml` |
| Stash 适配 | 过滤占位节点、xhttp、VLESS 无效字段 |
| Verge 轻量 | `/clash-verge.yaml` 少规则集，避免导入转圈 |
| 订阅缓存 | 默认 6 小时后台刷新机场节点 |

外网订阅：`https://sub.yoloworld.site:8883/clash.yaml`；局域网：`https://sub.yoloworld.site:8443/clash.yaml`。

---

## 自动化（launchd）

| 标签 | 安装方式 | 作用 |
|------|----------|------|
| `com.user.docker-stacks` | `./scripts/install-docker-launchd.sh` | 登录后 Docker compose 幂等 `up -d` |
| `com.user.wechat-cursor-acp` | `wechat-cursor-acp/scripts/install-launchd.sh` | 微信桥自启 |
| `com.user.stock-holdings-monitor` | `stock-ai/scripts/install-holdings-monitor-launchd.sh` | 持仓监控每 5 分钟 |
| `com.user.stock-ai-daily-selection` | `stock-ai/scripts/install-daily-selection-launchd.sh` | 每日选股 17:30 |
| `com.user.stock-watch-reminder-*` | `stock-ai/scripts/install-stock-watch-reminder-launchd.sh` | 一次性个股提醒 |

Docker 自启栈（`scripts/docker-autostart.sh`）：MySQL、Jellyfin、sidestore-infra、substore-clash、stock-ai 日线同步、stock_analysis。

日志：

- Docker：`logs/docker-autostart.log`
- 微信桥：`wechat-cursor-acp/logs/launchd-autostart.{out,err}.log`
- 持仓监控：`stock-ai/logs/launchd-holdings-monitor.{out,err}.log`

---

## Agent 开发工作流

| 机制 | 说明 |
|------|------|
| **Superpowers** | Cursor 插件：设计 / TDD / 计划 / 调试（`/add-plugin superpowers`） |
| **Hermes** | 十步循环 + 跨会话记忆（`.cursor/rules/project-memory.mdc` 等） |
| **规则** | `.cursor/rules/workspace.mdc`、`superpowers.mdc`、`hermes-protocol.mdc` |

详见 [AGENTS.md](./AGENTS.md)。

---

## 克隆与配置

```bash
git clone <你的 tools-workspace 远程地址>
cd tools-workspace

cp stock-ai/.env.example stock-ai/.env          # TUSHARE_TOKEN、MYSQL_URL、DEEPSEEK_API_KEY
cp sidestore-infra/.env.example sidestore-infra/.env   # 若有
cp substore-clash/.env.example substore-clash/.env
cp wechat-cursor-acp/.env.example wechat-cursor-acp/.env
```

**勿提交** `.env`、证书私钥、机场订阅 URL、持仓与 agent 个人记忆目录。

---

## 打开工作空间

```bash
cursor /Users/yolo/dev/yolo/tools-workspace
# 或多根工作区
cursor tools-workspace.code-workspace
```

---

## 常用命令速查

```bash
# 登录自启（首次）
./scripts/install-docker-launchd.sh
./wechat-cursor-acp/scripts/install-launchd.sh
./stock-ai/scripts/install-holdings-monitor-launchd.sh
./stock-ai/scripts/install-daily-selection-launchd.sh

# stock-ai
cd stock-ai && ./run_sync_daily.sh
cd stock-ai && ./push_holdings_monitor.sh          # 手动持仓监控
cd stock-ai && ./push_daily_briefing_wechat.sh 09:00

# sidestore-infra
cd sidestore-infra && ./scripts/setup.sh && docker compose --env-file .env ps

# substore-clash
cd substore-clash && docker compose up -d --build
```

---

## 目录结构

```
tools-workspace/              # 本仓库根（唯一 git remote）
├── stock-ai/                 # A 股数据、脚本、MCP、investment-agent
├── wechat-cursor-acp/        # 微信 ↔ Cursor CLI
├── sidestore-infra/          # SideStore + Caddy + DDNS
├── substore-clash/           # Sub-Store + clash-gen
├── scripts/                  # 工作空间级 Docker 自启
├── launchd/                  # 根级 launchd plist
├── logs/                     # docker-autostart 等
└── .cursor/rules/            # Agent 规则与项目记忆
```

---

## 兼容路径

| 符号链接 | 指向 |
|----------|------|
| `~/dev/yolo/stock-ai` | `tools-workspace/stock-ai` |
| `~/sidestore-infra` | `tools-workspace/sidestore-infra` |

新变更只提交本 monorepo；原独立 `stock-ai` 远程可归档。
