# Investment Agent

从 QClaw 工作区（`~/.qclaw/workspace`）迁移的投资助手项目，位于 `stock-ai` 仓库内，供 **Cursor IDE / Cursor CLI / wechat-acp** 使用。

## 目录结构

```
investment-agent/
├── .cursor/rules/       # Cursor Agent 行为规范
├── memory/              # 每日记忆日志
├── scripts/             # 止损监控、持仓查询等
├── reports/             # 历史分析报告
├── docs/skills/         # 从 QClaw 复制的技能文档（参考用）
├── MEMORY.md            # 长期记忆
├── 持仓执行卡.md         # 持仓与操作纪律
├── holdings.csv         # → ../../holdings/current.csv（软链接）
└── AGENTS.md / TOOLS.md # OpenClaw 时代的行为规范（保留参考）
```

## 与 stock-ai 的关系

| 资源 | 路径 |
|------|------|
| 行情数据 / MySQL 同步 | `../scripts/` |
| 持仓 CSV | `../holdings/current.csv` |
| 选股输出 | `../output/` |
| DeepSeek 分析 | `../tushare_mcp.py` |

## Cursor 使用

在 Cursor 中打开本目录（或整个 `stock-ai` 仓库）即可。Agent 会自动读取 `.cursor/rules/agent.mdc` 中的规范。

## 微信接入（wechat-acp + Cursor CLI）

桥接配置已迁到 monorepo 根目录 **[wechat-cursor-acp](../../wechat-cursor-acp)**（默认 `AGENT_CWD` 指向本目录）。

```bash
# 1. 确保 Cursor CLI 已登录
agent login

# 2. 启动（需先停掉 QClaw 的 openclaw-weixin，避免 iLink 冲突）
cd ../../wechat-cursor-acp && cp -n .env.example .env && ./scripts/start.sh
```

旧入口 `./scripts/start-wechat-acp.sh` 仍会转发到新项目。

## 从 QClaw 同步最新记忆

```bash
./scripts/sync-from-qclaw.sh
```

## 定时任务（可选，独立于 QClaw）

梅花生物止损监控（交易日 09:31，已由统一持仓监控覆盖）：

```bash
# crontab 示例
31 9 * * 1-5 cd /Users/yolo/dev/yolo/tools-workspace/stock-ai/investment-agent && python3 scripts/check_meihua_stop_loss.py
```

**持仓盘中监控**（交易时段每 5 分钟，触发才推微信）：

```bash
cd ../  # stock-ai 根目录
./scripts/install-holdings-monitor-launchd.sh
uv run python -m scripts.monitor.monitor_holdings_alerts --force   # 试跑
```

规则文件：`config/holdings_alerts.json`（与 `持仓执行卡.md` 同步）
