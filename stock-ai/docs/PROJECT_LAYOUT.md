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
| 买点优先手动选股 V1.3 / 规则 3.1.0 | `PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/select_short_term_candidates.py --output text` |
| 点时参考数据显式刷新 | 默认巨潮资讯 + BaoStock：`PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python stock-ai/scripts/sync/sync_buy_point_reference_data.py --start 2024-01-02 --end latest`；Tushare 回退追加 `--provider tushare` |
| 买点历史观察集 | `PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python stock-ai/scripts/analysis/generate_buy_point_observations.py --start 2023-12-26 --end 2026-08-04 --out stock-ai/output/buy-point-replay` |
| 2R 冻结回测 | `stock-ai/scripts/analysis/backtest_buy_point_selection.py`，必须依次执行研究、冻结 profile、一次性测试 |
| 五日净收益四画像影子研究 | `PYTHONPATH=. .venv/bin/python scripts/analysis/research_five_day_return_shadow.py <research|freeze|test|forward-screen|forward-settlement>`；仅手动、零股、一次性测试 |
| 定时同步 | `./run_sync_daily.sh` 或 `docker/scheduler`（工作日 17:00，见 [SCHEDULING.md](SCHEDULING.md)） |

旧路径 `scripts/sync_tushare_daily_to_mysql.py` 仍保留兼容包装，会转发到 `scripts/sync/`。

普通选股不刷新参考数据，点时同步命令也不会安装定时任务。买点优先入口没有定时安装项。旧四轨仍可由现有调度产出研究记录，但在 V1.3 中只作为影子漏选对照，不能提供正式买入资格。

规则 3.1.0 以触发后五个交易日内先达到 2R 为主要路径标签，使用同类样本的扣费后净期望和 95% Wilson 概率区间排序。验证只接受 `buy-point-selection-validation-v2`；旧产物或校准缺失时保持失败关闭。

历史观察集生成器从 MySQL 批量读取日线与 PIT 参考事实，并用 BaoStock 三个基准指数重建历史市场状态。`replay-integrity.json` 必须证明至少 630 个信号交易日、行业/ST/公告/市场状态覆盖完整、观察集哈希匹配且没有 `PENDING` 计划，冻结 profile 才会写入训练/验证校准。测试段只使用已冻结校准排序，并且同一 profile 只能写一次测试产物。生成的观察集、profile 和验证产物均为本地忽略文件，不进入 Git。

五日净收益四画像使用独立 `buy-point-five-day-return-shadow-v1` 产物链，按研究、冻结、一次性测试、前向筛选和独立结算五阶段手动执行。它不安装调度、不发送通知、不写持仓、订单或投顾记忆，也不改变旧 `TWO_R` 生产链路。

## 共享库

优先使用：

```python
from stock_ai.bootstrap import ensure_repo_root_on_path
from stock_ai.logging import setup_logging
from stock_ai.notify import send_to_lark
from stock_ai.symbols import CODES, code_label
```

根目录的 `logger_config.py`、`feishu_notice.py`、`code_names.py` 为兼容 re-export。
