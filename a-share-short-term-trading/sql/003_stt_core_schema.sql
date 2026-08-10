CREATE TABLE IF NOT EXISTS stt_schema_versions (
    version VARCHAR(16) NOT NULL,
    description VARCHAR(255) NOT NULL,
    applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易数据库版本';

INSERT INTO stt_schema_versions (version, description)
VALUES ('1.1', 'short-term trading v1.1 foundation')
ON DUPLICATE KEY UPDATE description = VALUES(description);

CREATE TABLE IF NOT EXISTS stt_watchlist (
    watch_id CHAR(36) NOT NULL,
    code CHAR(6) NOT NULL,
    trading_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL,
    source VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (watch_id),
    UNIQUE KEY uk_watchlist_code_date (code, trading_date),
    INDEX idx_code_trading_date (code, trading_date),
    INDEX idx_trading_date_status (trading_date, status),
    INDEX idx_status_updated_at (status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易关注列表';

CREATE TABLE IF NOT EXISTS stt_market_states (
    state_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    trading_date DATE NOT NULL,
    index_change_pct DECIMAL(12, 6) NOT NULL,
    breadth_ratio DECIMAL(7, 6) NOT NULL,
    turnover_ratio DECIMAL(12, 6) NOT NULL,
    strong_sector_count INT NOT NULL,
    status VARCHAR(16) NOT NULL,
    reasons_json JSON NOT NULL,
    evidence_refs_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (state_id),
    INDEX idx_trading_date_as_of (trading_date, as_of),
    INDEX idx_status_as_of (status, as_of),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易市场状态快照';

CREATE TABLE IF NOT EXISTS stt_candidates (
    candidate_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    trading_date DATE NOT NULL,
    code CHAR(6) NOT NULL,
    name VARCHAR(64) NOT NULL,
    candidate_type VARCHAR(16) NOT NULL,
    liquidity_score DECIMAL(7, 6) NOT NULL,
    trend_score DECIMAL(7, 6) NOT NULL,
    catalyst_score DECIMAL(7, 6) NOT NULL,
    sector VARCHAR(128) NOT NULL,
    rejected_reasons_json JSON NOT NULL,
    evidence_refs_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (candidate_id),
    UNIQUE KEY uk_candidate_code_date_type (code, trading_date, candidate_type),
    INDEX idx_code_trading_date (code, trading_date),
    INDEX idx_trading_date_status (trading_date, data_status),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易突破候选';

CREATE TABLE IF NOT EXISTS stt_trade_plans (
    plan_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    candidate_id CHAR(36) NOT NULL,
    trading_date DATE NOT NULL,
    code CHAR(6) NOT NULL,
    status VARCHAR(16) NOT NULL,
    trigger_price DECIMAL(18, 4) NOT NULL,
    entry_ceiling DECIMAL(18, 4) NOT NULL,
    pullback_low DECIMAL(18, 4) NOT NULL,
    pullback_high DECIMAL(18, 4) NOT NULL,
    invalidation_price DECIMAL(18, 4) NOT NULL,
    first_reduce_price DECIMAL(18, 4) NOT NULL,
    risk_distance DECIMAL(18, 4) NOT NULL,
    valid_until DATETIME(6) NOT NULL,
    rule_version VARCHAR(32) NOT NULL,
    evidence_refs_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (plan_id),
    UNIQUE KEY uk_plan_candidate_rule (candidate_id, rule_version),
    INDEX idx_code_trading_date (code, trading_date),
    INDEX idx_status_valid_until (status, valid_until),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易收盘计划';

CREATE TABLE IF NOT EXISTS stt_risk_decisions (
    risk_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    plan_id CHAR(36) NOT NULL,
    code CHAR(6) NOT NULL,
    market_status VARCHAR(16) NOT NULL,
    account_exposure DECIMAL(18, 4) NOT NULL,
    theme_exposure DECIMAL(18, 4) NOT NULL,
    open_trade_slots INT NOT NULL,
    max_shares INT NOT NULL,
    allowed BOOLEAN NOT NULL,
    rejection_reasons_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (risk_id),
    UNIQUE KEY uk_risk_plan_as_of (plan_id, as_of),
    INDEX idx_code_as_of (code, as_of),
    INDEX idx_status_as_of (market_status, as_of),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易组合风控决定';

CREATE TABLE IF NOT EXISTS stt_decision_snapshots (
    decision_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    trading_date DATE NOT NULL,
    code CHAR(6) NOT NULL,
    candidate_id CHAR(36) NOT NULL,
    plan_id CHAR(36) NOT NULL,
    risk_id CHAR(36) NOT NULL,
    evidence_refs_json JSON NOT NULL,
    frozen_payload_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (decision_id),
    UNIQUE KEY uk_decision_plan_risk (plan_id, risk_id),
    INDEX idx_code_trading_date (code, trading_date),
    INDEX idx_status_as_of (data_status, as_of),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易不可变决策快照';

CREATE TABLE IF NOT EXISTS stt_intraday_decisions (
    intraday_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    decision_id CHAR(36) NOT NULL,
    code CHAR(6) NOT NULL,
    status VARCHAR(16) NOT NULL,
    release_mode VARCHAR(16) NOT NULL,
    actionable BOOLEAN NOT NULL,
    passed_gates_json JSON NOT NULL,
    failed_gates_json JSON NOT NULL,
    evidence_refs_json JSON NOT NULL,
    max_shares INT NOT NULL,
    valid_until DATETIME(6) NOT NULL,
    reduce_shares INT NULL,
    reduce_ratio DECIMAL(7, 6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (intraday_id),
    UNIQUE KEY uk_intraday_decision_as_of (decision_id, as_of),
    INDEX idx_code_as_of (code, as_of),
    INDEX idx_status_valid_until (status, valid_until),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易盘中决定';

CREATE TABLE IF NOT EXISTS stt_outcome_observations (
    observation_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    decision_id CHAR(36) NOT NULL,
    code CHAR(6) NOT NULL,
    horizon VARCHAR(4) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    close_price DECIMAL(18, 4) NOT NULL,
    triggered BOOLEAN NOT NULL,
    max_favorable_excursion_pct DECIMAL(12, 6) NOT NULL,
    max_adverse_excursion_pct DECIMAL(12, 6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (observation_id),
    UNIQUE KEY uk_outcome_decision_horizon (decision_id, horizon),
    INDEX idx_code_observed_at (code, observed_at),
    INDEX idx_status_as_of (data_status, as_of),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易后续结果观测';

CREATE TABLE IF NOT EXISTS stt_trade_journal (
    journal_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    decision_id CHAR(36) NOT NULL,
    code CHAR(6) NOT NULL,
    action VARCHAR(16) NOT NULL,
    user_confirmed BOOLEAN NOT NULL,
    quantity INT NOT NULL,
    execution_price DECIMAL(18, 4) NOT NULL,
    fees DECIMAL(18, 4) NOT NULL,
    reason VARCHAR(512) NOT NULL,
    broker_evidence_ref VARCHAR(512) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (journal_id),
    UNIQUE KEY uk_journal_decision_action_as_of (decision_id, action, as_of),
    INDEX idx_code_as_of (code, as_of),
    INDEX idx_status_as_of (data_status, as_of),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易用户确认成交记录';

CREATE TABLE IF NOT EXISTS stt_plan_evaluations (
    evaluation_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    rule_version VARCHAR(32) NOT NULL,
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    horizon VARCHAR(4) NOT NULL,
    sample_size INT NOT NULL,
    total_return_pct DECIMAL(12, 6) NOT NULL,
    max_drawdown_pct DECIMAL(12, 6) NOT NULL,
    execution_deviation_pct DECIMAL(12, 6) NOT NULL,
    decision_refs_json JSON NOT NULL,
    review_tags_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (evaluation_id),
    UNIQUE KEY uk_evaluation_rule_window (rule_version, window_start, window_end, horizon),
    INDEX idx_trading_date_window (window_start, window_end),
    INDEX idx_status_as_of (data_status, as_of),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易计划效果评估';
