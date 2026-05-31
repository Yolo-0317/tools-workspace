# 已归档 DDL（勿再 init-db 自动执行）

以下表已于 2026-05-31 通过 `006_drop_legacy_eastmoney_tables.sql` 删除：

| 表 | 原用途 | 替代 |
|----|--------|------|
| `capital_flow` | 东财 push2 资金流 | OpenCLI SOP / 已移除「主力异动」选股 |
| `stock_intraday_snapshot` | 东财盘中分钟快照 | OpenCLI 现价 + `stock_daily` |
| `stock_orderbook_snapshot` | 东财盘口快照 | 未使用 |

保留本目录文件仅供历史参考。
