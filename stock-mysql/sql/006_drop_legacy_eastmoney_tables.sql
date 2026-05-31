-- 移除东财 HTTP 入库遗留表（2026-05-31 起无写入脚本）

DROP TABLE IF EXISTS stock_orderbook_snapshot;
DROP TABLE IF EXISTS stock_intraday_snapshot;
DROP TABLE IF EXISTS capital_flow;
