-- 盘中监控现价缓存：由 monitor_holdings_alerts（每 5 分钟 cron）经 OpenCLI 写入，看板只读

CREATE TABLE IF NOT EXISTS monitor_live_quotes (
    ts_code VARCHAR(10) NOT NULL COMMENT '6位代码',
    name VARCHAR(64) NOT NULL DEFAULT '',
    price DECIMAL(12, 4) NOT NULL,
    change_amt DECIMAL(12, 4) DEFAULT NULL,
    change_pct DECIMAL(8, 4) DEFAULT NULL COMMENT '涨跌幅 %',
    source VARCHAR(32) NOT NULL DEFAULT 'opencli' COMMENT '采集来源',
    quoted_at DATETIME NOT NULL COMMENT '采集时间（Asia/Shanghai）',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code),
    INDEX idx_quoted_at (quoted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='盘中监控现价缓存';
