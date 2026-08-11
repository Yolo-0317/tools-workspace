SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'analysis_date'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN analysis_date DATE NULL AFTER trading_date'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'setup_score'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN setup_score DECIMAL(7, 3) NULL AFTER candidate_type'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'rule_version'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN rule_version VARCHAR(64) NULL AFTER sector'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'source_strategies_json'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN source_strategies_json JSON NULL AFTER rule_version'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND column_name = 'executable_status'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD COLUMN executable_status VARCHAR(16) NULL AFTER source_strategies_json'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

UPDATE stt_candidates
SET analysis_date = COALESCE(analysis_date, trading_date),
    setup_score = COALESCE(setup_score, ROUND((liquidity_score + trend_score + catalyst_score) * 100 / 3, 3)),
    rule_version = COALESCE(rule_version, 'legacy-1.1'),
    source_strategies_json = COALESCE(source_strategies_json, JSON_ARRAY(source)),
    executable_status = COALESCE(executable_status, 'OBSERVE')
WHERE analysis_date IS NULL
   OR setup_score IS NULL
   OR rule_version IS NULL
   OR source_strategies_json IS NULL
   OR executable_status IS NULL;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND index_name = 'uk_candidate_code_date_type'),
    'ALTER TABLE stt_candidates DROP INDEX uk_candidate_code_date_type',
    'SELECT 1'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'stt_candidates' AND index_name = 'uk_candidate_analysis_code_type_rule'),
    'SELECT 1',
    'ALTER TABLE stt_candidates ADD UNIQUE INDEX uk_candidate_analysis_code_type_rule (analysis_date, code, candidate_type, rule_version)'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'analysis_date'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN analysis_date DATE NULL AFTER candidate_id'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'risk_reward_ratio'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN risk_reward_ratio DECIMAL(12, 6) NULL AFTER risk_distance'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'atr'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN atr DECIMAL(18, 4) NULL AFTER risk_reward_ratio'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'chip_trade_date'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN chip_trade_date DATE NULL AFTER atr'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'maximum_shares'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN maximum_shares INT NULL AFTER chip_trade_date'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'market_status'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN market_status VARCHAR(16) NULL AFTER maximum_shares'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stt_trade_plans' AND column_name = 'portfolio_status'),
    'SELECT 1',
    'ALTER TABLE stt_trade_plans ADD COLUMN portfolio_status VARCHAR(16) NULL AFTER market_status'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

UPDATE stt_trade_plans
SET analysis_date = COALESCE(analysis_date, trading_date),
    risk_reward_ratio = COALESCE(risk_reward_ratio, (first_reduce_price - trigger_price) / risk_distance),
    atr = COALESCE(atr, risk_distance),
    chip_trade_date = COALESCE(chip_trade_date, trading_date),
    market_status = COALESCE(market_status, 'FREEZE'),
    portfolio_status = COALESCE(portfolio_status, 'NOT_APPROVED')
WHERE analysis_date IS NULL
   OR risk_reward_ratio IS NULL
   OR atr IS NULL
   OR chip_trade_date IS NULL
   OR market_status IS NULL
   OR portfolio_status IS NULL;

INSERT INTO stt_schema_versions (version, description)
VALUES ('1.2', 'automatic dual-shape short-term selection')
ON DUPLICATE KEY UPDATE description = VALUES(description);
