# stock-mysql

**stock-ai 专用 MySQL 服务**：行情日线 + 持仓/监控等业务表（已替代 scattered JSON/CSV）。

| 项 | 值 |
|----|-----|
| 项目路径 | `tools-workspace/stock-mysql` |
| 容器 | `mysql8` |
| 端口 | `127.0.0.1:3306` |
| 默认库 | `stock_data` |

---

## 一句话

Docker 跑 MySQL 8，复用现有 `~/dev/docker/mysql/data` 数据目录；`stock_daily` 继续服务行情同步，新增 `portfolio_*` / `alert_rules` 等表承接持仓与监控配置。

---

## 架构

```
stock-ai/scripts/sync/*  ──►  stock_daily（已有）
持仓执行卡.md  ──sync──►  portfolio_positions / portfolio_account / alert_rules
selection_watchlist --sync  ──►  selection_watch_picks + alert_rules（selection）
```

**阶段规划**

| 阶段 | 内容 | 状态 |
|------|------|------|
| 1 | MySQL 栈迁入 monorepo + 建表 | ✅ 本项目 |
| 2 | 历史 CSV/JSON 一次性导入 | ✅ 已弃用，改 sync |
| 3 | `holdings_context.py` / 监控脚本读 DB | ✅ |
| 4 | 执行卡 ↔ DB 同步 CLI | ✅ `sync_portfolio_from_card` |

---

## 数据表

| 表 | 用途 | 数据源 |
|----|------|--------|
| `stock_daily` | A 股日线 | Tushare sync |
| `portfolio_positions` | 当前持仓 | `持仓执行卡.md` → sync |
| `portfolio_account` | 账户快照 | 执行卡「账户概览」→ sync |
| `alert_rules` | 盘中监控规则 | 执行卡 P0～P4 → sync；选股 `--sync` |
| `selection_watch_picks` | 选股池次日标的 | `selection_watchlist --sync` |
| `selection_daily_results` | 选股全量结果（按 `strategy` 分桶） | `combined` / `five_factor` 脚本 |
| `portfolio_account_daily` | 账户每日快照（看板） | 17:30 `eod`；改卡 `sync` |
| `portfolio_positions_daily` | 持仓每日快照（含现价/盈亏） | 同上 |
| `sop_review_daily` / `sop_review_items` | SOP+DeepSeek 审查 | 17:30 SOP 链路；`dashboard_data backfill-sop` |
| `emotion_cycle_daily` / `emotion_cycle_dragon_watch` | 游资轨情绪周期日检 | `emotion_cycle_checklist save/show`；Agent 读 `load_emotion_cycle_checklist` |
| `limit_up_research_*` | 东财涨停全量事实、前日选股归因与 T+1/T+3/T+5 标签 | `sync_limit_up_research` 手动触发 |
| `macro_news_items` | 东财 7×24 快讯（含 `sentiment` 利好/利空/中性） | `sync_macro_news`（每 15min） |
| `macro_news_fetch_runs` | 快讯同步批次 | 同上 |
| `briefing_snapshots` | Cursor AI 财经解读 | `sync_macro_news`（每 15min） |

**已删除（2026-05-31）**：`capital_flow`、`stock_intraday_snapshot`、`stock_orderbook_snapshot` — 东财 HTTP 遗留，DDL 归档于 `sql/archived/`。

看板 JSON 导出：`uv run python -m scripts.tools.dashboard_data export -o output/dashboard.json`

---

## 快速开始

### 从现有 MySQL 迁移（推荐）

若已在用 `~/dev/docker/mysql`：

```bash
cd stock-mysql
cp .env.example .env
# 编辑 MYSQL_ROOT_PASSWORD 等与现网一致
# MYSQL_DATA_DIR 默认指向 ~/dev/docker/mysql/data

docker compose up -d
bash scripts/init-db.sh          # 已有库：只补新表
```

### 全新安装

```bash
cp .env.example .env
mkdir -p data conf.d logs
docker compose up -d               # 空 data/ 时自动跑 sql/*.sql
```

### 从执行卡同步（推荐）

```bash
cd ../stock-ai
uv run python -m scripts.tools.sync_portfolio_from_card
uv run python -m scripts.tools.sync_portfolio_from_card --dry-run   # 仅解析
```

---

## 配置（`.env`）

| 变量 | 说明 |
|------|------|
| `MYSQL_ROOT_PASSWORD` | root 密码 |
| `MYSQL_DATABASE` | 默认 `stock_data` |
| `MYSQL_USER` / `MYSQL_PASSWORD` | 应用账号 |
| `MYSQL_DATA_DIR` | 数据目录（可指向旧路径） |
| `MYSQL_CONF_DIR` | my.cnf 目录 |

**stock-ai 连接串**（`.env`）：

```text
MYSQL_URL=mysql+pymysql://stock:密码@127.0.0.1:3306/stock_data
```

Docker 内定时任务用 `host.docker.internal`；本机脚本会自动替换为 `127.0.0.1`。

---

## 运维

```bash
docker compose up -d
docker compose ps
bash scripts/init-db.sh
bash scripts/healthcheck.sh   # 若有

# 连接
docker exec -it mysql8 mysql -ustock -p stock_data
```

**launchd / 开机自启**：由 workspace 根目录 `scripts/docker-autostart.sh` 拉起（已指向本目录）。

---

## 目录结构

```text
stock-mysql/
├── README.md
├── docker-compose.yml
├── .env.example
├── sql/
│   ├── 001_stock_daily.sql
│   └── 002_portfolio.sql
└── scripts/
    ├── init-db.sh
    └── healthcheck.sh
```

---

## 相关项目

| 项目 | 关系 |
|------|------|
| [stock-ai](../stock-ai/README.md) | 行情同步、选股、监控脚本 |
| [investment-agent](../stock-ai/investment-agent/README.md) | 执行卡 → MySQL 同步 |

---

## 安全

- 勿提交 `.env`
- MySQL 仅绑定 `127.0.0.1:3306`
- 生产密码勿写入 compose 文件
