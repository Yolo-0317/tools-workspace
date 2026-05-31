-- 见 archived/README.md；本文件仅作历史参考

CREATE TABLE IF NOT EXISTS stock_intraday_snapshot (
    ts_code VARCHAR(10) NOT NULL COMMENT '证券代码（6 位）',
    bar_time DATETIME NOT NULL COMMENT '快照时间（北京时间，分钟级）',
    trade_date DATE NOT NULL COMMENT '交易日期（来自东财）',
    open DECIMAL(10, 4) COMMENT '今开',
    high DECIMAL(10, 4) COMMENT '当日最高（盘中动态）',
    low DECIMAL(10, 4) COMMENT '当日最低（盘中动态）',
    close DECIMAL(10, 4) COMMENT '盘中最新价（东财 close/当前）',
    vol BIGINT COMMENT '成交量（手，盘中累计）',
    amount DECIMAL(20, 4) COMMENT '成交额（千元，盘中累计）',
    pct_chg DECIMAL(8, 4) COMMENT '涨跌幅（%）',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (ts_code, bar_time),
    INDEX idx_trade_date (trade_date),
    INDEX idx_bar_time (bar_time),
    INDEX idx_code_date (ts_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='已废弃';
