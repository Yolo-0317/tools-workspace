CREATE TABLE IF NOT EXISTS stt_daily_sync_runs (
    run_id CHAR(36) NOT NULL,
    scope VARCHAR(16) NOT NULL,
    target_trade_date DATE NOT NULL,
    source_policy VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    requested_codes JSON NOT NULL,
    ready_codes JSON NOT NULL,
    failed_codes JSON NOT NULL,
    coverage_ratio DECIMAL(6, 4) NOT NULL,
    upserted_rows INT NOT NULL DEFAULT 0,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NOT NULL,
    evidence_refs JSON NOT NULL,
    failure_reasons JSON NOT NULL,
    PRIMARY KEY (run_id),
    INDEX idx_target_scope (target_trade_date, scope),
    INDEX idx_status_finished (status, finished_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易日线同步审计';
