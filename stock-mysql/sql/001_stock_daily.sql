-- 行情日线（与 stock-ai/sql/create_stock_daily_table.sql 保持一致）
CREATE TABLE IF NOT EXISTS stock_daily (
    ts_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    exch_code VARCHAR(10) COMMENT '交易所代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    open DECIMAL(10, 4) COMMENT '开盘价',
    high DECIMAL(10, 4) COMMENT '最高价',
    low DECIMAL(10, 4) COMMENT '最低价',
    close DECIMAL(10, 4) COMMENT '收盘价',
    pre_close DECIMAL(10, 4) COMMENT '昨收价',
    change_amount DECIMAL(10, 4) COMMENT '涨跌额',
    pct_chg DECIMAL(8, 4) COMMENT '涨跌幅（%）',
    vol BIGINT COMMENT '成交量（手）',
    amount DECIMAL(20, 4) COMMENT '成交额（千元）',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date),
    INDEX idx_trade_date (trade_date),
    INDEX idx_ts_code (ts_code),
    INDEX idx_exch_date (exch_code, trade_date),
    INDEX idx_date_code (trade_date, ts_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票日线行情表';
