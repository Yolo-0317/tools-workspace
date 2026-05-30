# stock-ai 文档索引

> **生产环境唯一入口**：[CAPABILITIES.md](CAPABILITIES.md) — 定时任务、17:30、DeepSeek、监控、配置。

---

## 在用（维护中）

| 文档 | 用途 |
|------|------|
| [CAPABILITIES.md](CAPABILITIES.md) | **能力总览**（launchd、链路、工具、配置） |
| [../README.md](../README.md) | 快速开始：同步、选股、推送命令 |
| [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md) | 目录结构 |
| [pipelines/daily_stock_deepseek_pipeline.md](pipelines/daily_stock_deepseek_pipeline.md) | 手动盘后：日线 → 选股 → DeepSeek |
| [SELECTION_STRATEGIES.md](SELECTION_STRATEGIES.md) | 单策略筛选条件 |
| [DEEPSEEK_USAGE.md](DEEPSEEK_USAGE.md) | MCP DeepSeek 信号 + `deepseek_client` |
| [CURSOR_MCP_SETUP.md](CURSOR_MCP_SETUP.md) | Cursor 挂载 `tushare_mcp.py` |
| [TUSHARE_SYNC_GUIDE.md](TUSHARE_SYNC_GUIDE.md) | Tushare 同步细节 |
| [NO_STOCK_BASIC_GUIDE.md](NO_STOCK_BASIC_GUIDE.md) | 无需 stock_basic 的 by_date 模式 |
| [RATE_LIMIT_GUIDE.md](RATE_LIMIT_GUIDE.md) | Tushare 限流 |
| [pipelines/strategy.md](pipelines/strategy.md) | 五因子策略说明 |
| [../investment-agent/持仓执行卡.md](../investment-agent/持仓执行卡.md) | P0～P4 权威纪律 |
| [../investment-agent/memory/trading-strategies.md](../investment-agent/memory/trading-strategies.md) | 通用操盘策略（git 副本） |
| [../wechat-cursor-acp/README.md](../../wechat-cursor-acp/README.md) | 微信 ↔ Cursor CLI 桥接 |

### Agent Skill 以哪份为准

| Skill | 权威副本 | 说明 |
|-------|----------|------|
| 东财 SOP | `investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md` | Cursor Agent 读本目录 |
| 选股工作台 | `investment-agent/docs/skills/stock-strategy-selector/SKILL.md` | 同上 |
| 用户级副本 | `~/.codex/skills/` | 与 repo 不一致时 **以 investment-agent/docs 为准**，必要时同步 |

---

## 维护约定

1. 新增自动化能力 → 先更新 **CAPABILITIES.md**，再视需要更新 README / pipeline。
2. 新增 `docs/*.md` → 在本索引「在用」中登记。
3. 过时文档直接删除或合并进在用文档，避免「遗留」堆积。

*最后更新：2026-05-30*
