# stock-ai 项目结构

## 目录一览

```
stock-ai/
├── stock_ai/              # 共享库（含 buy_point_selection 买点优先纯函数核心）
├── tushare_mcp.py         # MCP 服务主程序
├── core_v2/               # 选股 / 分析核心逻辑（v2 策略）
├── core_v3/               # 五因子选股 + DeepSeek 流水线（v3）
├── scripts/               # 可执行脚本（按职责分子目录）
│   ├── sync/              # 数据同步入库
│   ├── selection/         # 选股
│   ├── analysis/          # 持仓分析、盘前/盘中/盘后
│   ├── monitor/           # 持仓 + 选股池监控
│   └── tools/             # 校验、推送、战报等工具
├── tests/manual/          # 手动测试脚本
├── docs/                  # 文档（**CAPABILITIES.md** 为能力总览）
├── sql/                   # 建表 SQL
├── output/                # 选股/分析输出（gitignore）
├── logs/                  # 运行日志（gitignore）
├── investment-agent/      # 投资 Agent 工作区
```

## 常用入口

| 用途 | 命令 / 文档 |
|------|------|
| **能力总览** | [docs/CAPABILITIES.md](../docs/CAPABILITIES.md) |
| Tushare 日线同步 | `uv run python scripts/sync/sync_tushare_daily_to_mysql.py` |
| 五因子选股 | `uv run python core_v3/stock_selection_five_factor_mysql.py` |
| 综合选股 (v2) | `uv run python core_v2/stock_selection_combined.py` |
| 买点优先手动选股 V1.3 | `PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/select_short_term_candidates.py --output text` |
| 点时参考数据显式刷新 | 默认巨潮资讯 + BaoStock：`PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python stock-ai/scripts/sync/sync_buy_point_reference_data.py --start 2024-01-02 --end latest`；Tushare 回退追加 `--provider tushare` |
| 定时同步 | `./run_sync_daily.sh` 或 `docker/scheduler`（工作日 17:00，见 [SCHEDULING.md](SCHEDULING.md)） |

旧路径 `scripts/sync_tushare_daily_to_mysql.py` 仍保留兼容包装，会转发到 `scripts/sync/`。

普通选股不刷新参考数据，点时同步命令也不会安装定时任务。买点优先入口没有定时安装项。旧四轨仍可由现有调度产出研究记录，但在 V1.3 中只作为影子漏选对照，不能提供正式买入资格。

## 共享库

优先使用：

```python
from stock_ai.bootstrap import ensure_repo_root_on_path
from stock_ai.logging import setup_logging
from stock_ai.notify import send_to_lark
from stock_ai.symbols import CODES, code_label
```

根目录的 `logger_config.py`、`feishu_notice.py`、`code_names.py` 为兼容 re-export。
