# 本机命令

先用项目注册表确认路径。本机示例路径如下；从其他目录调用时也使用绝对路径。不要直接 `source .env`，不要显示配置全文。

## 本地选股与诊断

在 `/Users/huan.yu/dev/tools-workspace` 执行：

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/select_short_term_candidates.py --output json

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/diagnose_stock.py --code 300059 --output json
```

`300059` 是示例，替换为已确认的代码。诊断默认 SHADOW；不得添加人工风控放行参数。普通选股不刷新点时参考数据；请求确实包含数据刷新时再按项目 README 的刷新流程执行。选股本身可持久化计划，不要描述为纯只读调用。

板块检测在 `stock-ai` 目录执行：

```bash
.venv/bin/python -m scripts.analysis.detect_sector_rotation --edition auto --top-sectors 6 --stocks-per-sector 10 --no-db
```

`--shadow-only` 会改变选股覆盖范围，不是完整选股结果，不能为了执行方便默默加入。`--at` 仅用于用户明确要求的历史复现。

## 妙想执行方式

本机 Python：`/Users/huan.yu/dev/tools-workspace/stock-ai/.venv/bin/python`。
密钥文件：`/Users/huan.yu/dev/tools-workspace/stock-ai/.env`，使用 `EM_API_KEY`。
技能目录：`/Users/huan.yu/.codex/skills`。

先建立并进入本次输出目录 `stock-ai/output/eastmoney/workbench/<上海日期>/<本次任务唯一目录>`。目录名由本次请求生成，不复用上次结果冒充新结果。下例运行热点查询：

```bash
/Users/huan.yu/dev/tools-workspace/stock-ai/.venv/bin/python -m dotenv -f /Users/huan.yu/dev/tools-workspace/stock-ai/.env run -- /Users/huan.yu/dev/tools-workspace/stock-ai/.venv/bin/python /Users/huan.yu/.codex/skills/stock-market-hotspot-discovery/scripts/get_data.py --query '今日A股市场热点'
```

其他调用复用相同 dotenv 前缀，仅替换脚本路径和参数。先读相应子 Skill：

| Skill | 脚本（相对其目录） | 参数示例 |
|---|---|---|
| mx-finance-data | scripts/get_data.py | `--query '东方财富最新价' --indicators '最新价'` |
| mx-finance-search | scripts/get_data.py | `'东方财富最近七天公告与监管风险'`（位置参数） |
| mx-stocks-screener | scripts/get_data.py | `--query '半导体板块成交额前十' --select-type A股` |
| mx-macro-data | scripts/get_data.py | `--query '中国最新制造业PMI'` |
| stock-market-hotspot-discovery | scripts/get_data.py | `--query '今日A股市场热点'` |
| industry-sector-analysis | scripts/get_data.py | `--query '分析当前半导体板块的景气度和风险'` |
| stock-capital-analysis | scripts/get_data.py | `--query '东方财富的资金面'` |
| stock-news-analysis | scripts/get_data.py | `--query '东方财富公告、新闻及其潜在影响'` |
| stock-institutional-opinion | scripts/get_data.py | `--query '分析东方财富的机构观点'` |

将具体问题作为独立参数传入，使用可靠的 shell 引号或参数数组，不拼接用户文本到可执行 shell 片段。无需 debug 输出；普通结果文件足够。

## 业绩点评的三个步骤

先读 `stock-earnings-review/SKILL.md` 与 `BUSINESS_LOGIC.md`。实际目录为 `~/.codex/skills/stock-earnings-review/scripts/`，上游示例中重复出现的 `stock-earnings-review/` 不再重复拼接。

1. `validate_entity.py --query '东方财富最新一期业绩点评'`：检查识别结果是否为用户指定公司，歧义时不擅自取第一家。
2. `normalize_report_period.py --secu-code 300059 --market-char SZ --class-code 002001`：证券字段使用上一步实际返回值，示例不能当作所有公司的常量。选择用户指定的已发布报告期；未指定则选返回列表最新一期。
3. `call_review_api.py`：传 `--secu-code`、`--market-char`、`--class-code`、`--report-date`、`--secu-name` 的已核验值。报告期缺失或不匹配则停止，不添加 `--non-strict` 暗中回退。

每步都使用 dotenv 前缀。基于接口 `title/content/shareUrl/files` 交付，按上游协议不读取附件反向补写正文。
