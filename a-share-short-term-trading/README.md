# A 股短线交易辅助系统

第一阶段只实现持仓、用户自选和 P1 观察池的日线同步与交易诊断；不扫描全市场。

## 日线同步

先用本地 MySQL 客户端或既有迁移工具依次执行：

- `sql/001_stt_daily_sync_runs.sql`：日线同步审计表。
- `sql/002_stt_evidence_and_capture.sql`：指标快照与页面采集审计表。

然后从工作区根目录运行关键标的同步：

```bash
MYSQL_URL='mysql+pymysql://…' \
PYTHONPATH=a-share-short-term-trading \
uv run --project stock-ai python a-share-short-term-trading/scripts/daily_bar_sync.py \
  --scope critical \
  --codes 600000,688001 \
  --target-date auto \
  --output json
```

同步仅在 MySQL 日线缺失时调用东财 OpenCLI 日 K 适配器；`PARTIAL` 或 `FAILED` 不能生成新的交易价格计划。

## 收盘个股诊断

完成日线同步及筹码快照采集后，可生成次日的 `WAIT_ENTRY` 计划草案：

```bash
MYSQL_URL='mysql+pymysql://…' \
PYTHONPATH=a-share-short-term-trading \
uv run --project stock-ai python a-share-short-term-trading/scripts/diagnose_eod.py \
  --code 600000
```

该命令只计算支撑、压力、触发、失效、第一减仓参考与最大试错股数；它不会输出 `BUY_ALLOWED`，盘中实时门禁和组合风控尚需另行通过。

## 盘中验证

先采集报价与资金快照，再由盘中验证器读取冻结计划与全部所需快照：

```bash
MYSQL_URL='mysql+pymysql://…' \
PYTHONPATH=a-share-short-term-trading \
uv run --project stock-ai python a-share-short-term-trading/scripts/capture_intraday.py --code 600000
```

`diagnose_intraday.py` 只会在报价、资金、板块、筹码、连续三帧盘口、市场状态和组合风控全部通过时输出 `BUY_ALLOWED`；第一版报价与资金采集已接入，其他快照缺失时安全输出 `NO_TRADE`。
