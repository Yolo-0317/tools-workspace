-- 综合选股全量结果（替代 CSV 作为 Top5/SOP 主读源）

CREATE TABLE IF NOT EXISTS selection_daily_results (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    strategy VARCHAR(32) NOT NULL DEFAULT 'combined' COMMENT '选股策略：combined / five_factor 等',
    ts_code VARCHAR(10) NOT NULL,
    rank_no INT NOT NULL DEFAULT 0 COMMENT '当日综合排名',
    close_price DECIMAL(12, 4) DEFAULT NULL,
    change_pct DECIMAL(8, 4) DEFAULT NULL,
    total_score DECIMAL(8, 2) DEFAULT NULL,
    label_count TINYINT UNSIGNED DEFAULT NULL,
    amount_wan DECIMAL(16, 2) DEFAULT NULL COMMENT '成交额(万)',
    strategy_label VARCHAR(128) DEFAULT NULL,
    action_hint VARCHAR(64) DEFAULT NULL,
    raw_json JSON NOT NULL COMMENT '完整选股行（与 CSV 列一致）',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_date_strategy_code (trade_date, strategy, ts_code),
    INDEX idx_trade_date_strategy_rank (trade_date, strategy, rank_no),
    INDEX idx_trade_date_score (trade_date, total_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='综合选股日结果';
