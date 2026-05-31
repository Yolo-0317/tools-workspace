-- 看板：持仓每日快照 + SOP 审查落库（历史可追溯）

CREATE TABLE IF NOT EXISTS portfolio_account_daily (
    snapshot_date DATE NOT NULL,
    snapshot_slot VARCHAR(16) NOT NULL DEFAULT 'eod' COMMENT 'eod|sync|manual',
    total_assets DECIMAL(16, 2) DEFAULT NULL,
    available_cash DECIMAL(16, 2) DEFAULT NULL,
    market_value DECIMAL(16, 2) DEFAULT NULL,
    position_ratio DECIMAL(8, 4) DEFAULT NULL COMMENT '仓位比例 0-1',
    holding_pnl DECIMAL(16, 2) DEFAULT NULL,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_date, snapshot_slot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账户每日快照';

CREATE TABLE IF NOT EXISTS portfolio_positions_daily (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    snapshot_date DATE NOT NULL,
    snapshot_slot VARCHAR(16) NOT NULL DEFAULT 'eod',
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    shares INT NOT NULL DEFAULT 0,
    cost_price DECIMAL(12, 4) NOT NULL DEFAULT 0,
    market_price DECIMAL(12, 4) DEFAULT NULL COMMENT '快照时 OpenCLI 现价',
    market_value DECIMAL(16, 2) DEFAULT NULL,
    pnl_amount DECIMAL(16, 2) DEFAULT NULL,
    pnl_pct DECIMAL(8, 4) DEFAULT NULL,
    status_note VARCHAR(255) DEFAULT NULL,
    action_note VARCHAR(255) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_snap_slot_code (snapshot_date, snapshot_slot, ts_code),
    INDEX idx_snap_date (snapshot_date, snapshot_slot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='持仓每日快照';

CREATE TABLE IF NOT EXISTS sop_review_daily (
    trade_date DATE NOT NULL,
    strategy VARCHAR(32) NOT NULL DEFAULT 'combined',
    selection_source VARCHAR(64) DEFAULT NULL,
    generated_at DATETIME NOT NULL,
    wechat_summary TEXT,
    report_path VARCHAR(512) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, strategy),
    INDEX idx_generated (generated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SOP+DeepSeek 批次摘要';

CREATE TABLE IF NOT EXISTS sop_review_items (
    trade_date DATE NOT NULL,
    strategy VARCHAR(32) NOT NULL DEFAULT 'combined',
    rank_no INT NOT NULL DEFAULT 0,
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    score DECIMAL(8, 2) DEFAULT NULL,
    decision VARCHAR(64) DEFAULT NULL,
    watch_worthy TINYINT(1) NOT NULL DEFAULT 0,
    close_price DECIMAL(12, 4) DEFAULT NULL,
    change_pct DECIMAL(8, 4) DEFAULT NULL,
    strategy_label VARCHAR(128) DEFAULT NULL,
    action_hint VARCHAR(64) DEFAULT NULL,
    support_prices JSON DEFAULT NULL,
    stop_price DECIMAL(12, 4) DEFAULT NULL,
    target_prices JSON DEFAULT NULL,
    in_holdings TINYINT(1) NOT NULL DEFAULT 0,
    review_md MEDIUMTEXT,
    raw_json JSON DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, strategy, ts_code),
    INDEX idx_trade_rank (trade_date, strategy, rank_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SOP 逐股审查';
