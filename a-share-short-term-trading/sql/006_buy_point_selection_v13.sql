SET @stt_sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'stt_candidates'
          AND column_name = 'candidate_type' AND character_maximum_length < 32
    ),
    'ALTER TABLE stt_candidates MODIFY COLUMN candidate_type VARCHAR(32) NOT NULL',
    'SELECT 1'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'structure_id'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN structure_id CHAR(32) NULL AFTER executable_status'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'selection_tier'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN selection_tier VARCHAR(16) NULL AFTER structure_id'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'pattern_quality'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN pattern_quality DECIMAL(7, 6) NULL AFTER selection_tier'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'missing_fields_json'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN missing_fields_json JSON NULL AFTER pattern_quality'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'sector_metrics_json'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN sector_metrics_json JSON NULL AFTER missing_fields_json'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND index_name = 'uk_buy_point_candidate_structure_rule'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD UNIQUE INDEX uk_buy_point_candidate_structure_rule (structure_id, rule_version)'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'structure_id'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN structure_id CHAR(32) NULL AFTER candidate_id'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'selection_tier'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN selection_tier VARCHAR(16) NULL AFTER structure_id'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'plan_state'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN plan_state VARCHAR(16) NULL AFTER status'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'signal_close'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN signal_close DECIMAL(18, 4) NULL AFTER plan_state'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'target_2r'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN target_2r DECIMAL(18, 4) NULL AFTER first_reduce_price'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'valid_through_trade_date'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN valid_through_trade_date DATE NULL AFTER valid_until'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND index_name = 'uk_buy_point_plan_structure_rule'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD UNIQUE INDEX uk_buy_point_plan_structure_rule (structure_id, rule_version)'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

CREATE TABLE IF NOT EXISTS stt_buy_point_plan_events (
    event_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    plan_id CHAR(36) NOT NULL,
    structure_id CHAR(32) NOT NULL,
    previous_state VARCHAR(16) NULL,
    new_state VARCHAR(16) NOT NULL,
    reason_code VARCHAR(64) NOT NULL,
    evidence_refs_json JSON NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    event_fingerprint CHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (event_id),
    UNIQUE KEY uk_buy_point_event_fingerprint (event_fingerprint),
    INDEX idx_plan_observed_at (plan_id, observed_at),
    INDEX idx_status_observed_at (new_state, observed_at),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='买点计划不可覆盖状态事件';

CREATE TABLE IF NOT EXISTS stt_buy_point_forward_runs (
    run_id CHAR(36) NOT NULL,
    schema_version VARCHAR(8) NOT NULL,
    as_of DATETIME(6) NOT NULL,
    source VARCHAR(64) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    analysis_date DATE NOT NULL,
    rule_version VARCHAR(64) NOT NULL,
    formal_count INT NOT NULL,
    observe_count INT NOT NULL,
    shadow_count INT NOT NULL,
    resolved_count INT NOT NULL,
    duplicate_count INT NOT NULL,
    integrity_violations_json JSON NOT NULL,
    release_mode VARCHAR(16) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (run_id),
    UNIQUE KEY uk_buy_point_forward_date_rule (analysis_date, rule_version),
    INDEX idx_trading_date_rule (analysis_date, rule_version),
    INDEX idx_status_as_of (data_status, as_of),
    INDEX idx_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='买点策略手动前向运行账本';

INSERT INTO stt_schema_versions (version, description)
VALUES ('1.3', 'buy-point selection plans and append-only forward ledger')
ON DUPLICATE KEY UPDATE description = VALUES(description);
