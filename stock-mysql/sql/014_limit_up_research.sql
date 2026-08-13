-- 东财涨停研究账本：手动采集、确定性归因与 T+1/T+3/T+5 标签

CREATE TABLE IF NOT EXISTS limit_up_research_runs (
    run_id BIGINT NOT NULL AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL,
    source VARCHAR(64) NOT NULL,
    snapshot_hash CHAR(64) DEFAULT NULL,
    limit_up_count INT DEFAULT NULL,
    exploded_count INT DEFAULT NULL,
    limit_down_count INT DEFAULT NULL,
    missing_fields_json JSON NOT NULL,
    error_code VARCHAR(64) DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    raw_meta_json JSON NOT NULL,
    started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) DEFAULT NULL,
    PRIMARY KEY (run_id),
    INDEX idx_limit_up_run_date (trade_date, status),
    INDEX idx_limit_up_snapshot (trade_date, snapshot_hash),
    CHECK (status IN ('STARTED', 'SUCCEEDED', 'FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS limit_up_research_pool (
    id BIGINT NOT NULL AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    pool_kind VARCHAR(16) NOT NULL,
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    pct_chg DECIMAL(10,4) DEFAULT NULL,
    amount_wan DECIMAL(18,2) DEFAULT NULL,
    board_height INT DEFAULT NULL,
    main_theme VARCHAR(128) DEFAULT NULL,
    first_seal_time VARCHAR(16) DEFAULT NULL,
    last_seal_time VARCHAR(16) DEFAULT NULL,
    reopen_count INT DEFAULT NULL,
    seal_amount_wan DECIMAL(18,2) DEFAULT NULL,
    missing_fields_json JSON NOT NULL,
    source_run_id BIGINT NOT NULL,
    raw_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_pool_fact (trade_date, pool_kind, ts_code),
    INDEX idx_pool_ladder (trade_date, pool_kind, board_height),
    CONSTRAINT fk_limit_up_pool_run FOREIGN KEY (source_run_id)
      REFERENCES limit_up_research_runs(run_id),
    CHECK (pool_kind IN ('LIMIT_UP', 'EXPLODED', 'LIMIT_DOWN'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS limit_up_selection_attribution (
    id BIGINT NOT NULL AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    selection_date DATE NOT NULL,
    ts_code VARCHAR(10) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    selected TINYINT(1) NOT NULL DEFAULT 0,
    rank_no INT DEFAULT NULL,
    score DECIMAL(12,4) DEFAULT NULL,
    action VARCHAR(64) DEFAULT NULL,
    attribution VARCHAR(32) NOT NULL,
    first_reason_code VARCHAR(64) DEFAULT NULL,
    reason_codes_json JSON NOT NULL,
    evidence_json JSON NOT NULL,
    rule_version VARCHAR(64) NOT NULL,
    source_run_id BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_attribution (trade_date, ts_code, strategy),
    INDEX idx_attribution_reason (trade_date, strategy, attribution),
    CONSTRAINT fk_limit_up_attribution_run FOREIGN KEY (source_run_id)
      REFERENCES limit_up_research_runs(run_id),
    CHECK (attribution IN (
      'SELECTED', 'RANKED_OUT', 'HARD_REJECTED', 'DATA_MISSING',
      'EXPLAINER_UNAVAILABLE', 'STRATEGY_NOT_RUN'
    ))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS limit_up_forward_labels (
    signal_date DATE NOT NULL,
    ts_code VARCHAR(10) NOT NULL,
    horizon VARCHAR(4) NOT NULL,
    outcome_date DATE DEFAULT NULL,
    signal_close DECIMAL(16,4) DEFAULT NULL,
    outcome_close DECIMAL(16,4) DEFAULT NULL,
    close_return_pct DECIMAL(12,4) DEFAULT NULL,
    max_return_pct DECIMAL(12,4) DEFAULT NULL,
    max_drawdown_pct DECIMAL(12,4) DEFAULT NULL,
    closed_limit_up TINYINT(1) DEFAULT NULL,
    board_height INT DEFAULT NULL,
    data_complete TINYINT(1) NOT NULL DEFAULT 0,
    missing_fields_json JSON NOT NULL,
    label_version VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (signal_date, ts_code, horizon),
    INDEX idx_forward_outcome (outcome_date, horizon),
    CHECK (horizon IN ('T1', 'T3', 'T5'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
