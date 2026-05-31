-- 持仓与监控规则（逐步替代 CSV / JSON / 执行卡表格）

CREATE TABLE IF NOT EXISTS portfolio_positions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ts_code VARCHAR(10) NOT NULL COMMENT '6位代码',
    name VARCHAR(64) NOT NULL DEFAULT '',
    asset_type ENUM('stock', 'fund', 'etf') NOT NULL DEFAULT 'stock',
    shares INT NOT NULL DEFAULT 0 COMMENT '股数/份数',
    cost_price DECIMAL(12, 4) NOT NULL DEFAULT 0 COMMENT '成本价',
    status_note VARCHAR(255) DEFAULT NULL COMMENT '状态简述',
    action_note VARCHAR(255) DEFAULT NULL COMMENT '操作建议',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    source VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT 'csv|card|manual',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_code (ts_code),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='当前持仓';

CREATE TABLE IF NOT EXISTS portfolio_account (
    id TINYINT UNSIGNED NOT NULL DEFAULT 1,
    total_assets DECIMAL(16, 2) DEFAULT NULL,
    available_cash DECIMAL(16, 2) DEFAULT NULL,
    market_value DECIMAL(16, 2) DEFAULT NULL,
    position_ratio DECIMAL(8, 4) DEFAULT NULL COMMENT '仓位比例 0-1',
    holding_pnl DECIMAL(16, 2) DEFAULT NULL,
    snapshot_date DATE DEFAULT NULL,
    notes TEXT,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账户快照';

CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id VARCHAR(64) NOT NULL,
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    rule_type VARCHAR(32) NOT NULL COMMENT 'price_below|price_above|price_in_range|daily_pct_above',
    price DECIMAL(12, 4) DEFAULT NULL,
    low_price DECIMAL(12, 4) DEFAULT NULL,
    high_price DECIMAL(12, 4) DEFAULT NULL,
    pct_threshold DECIMAL(8, 4) DEFAULT NULL,
    message_template TEXT NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'holdings' COMMENT 'holdings|selection',
    is_enabled TINYINT(1) NOT NULL DEFAULT 1,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_id),
    INDEX idx_code_enabled (ts_code, is_enabled),
    INDEX idx_source (source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='盘中监控规则';

CREATE TABLE IF NOT EXISTS selection_watch_picks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    selection_trade_date DATE NOT NULL,
    watch_date DATE NOT NULL,
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    close_price DECIMAL(12, 4) DEFAULT NULL,
    change_pct DECIMAL(8, 4) DEFAULT NULL,
    score DECIMAL(8, 2) DEFAULT NULL,
    label VARCHAR(32) DEFAULT NULL,
    action_hint VARCHAR(64) DEFAULT NULL,
    in_holdings TINYINT(1) NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    raw_json JSON DEFAULT NULL COMMENT '原始 pick 条目备份',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_watch_date (watch_date, is_active),
    INDEX idx_code (ts_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='选股池次日监控标的';
