CREATE TABLE IF NOT EXISTS sector_rotation_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    trade_date DATE NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    edition VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL,
    threshold_version VARCHAR(64) NOT NULL,
    warning_json JSON NULL,
    result_json JSON NULL,
    error_code VARCHAR(64) NULL,
    error_message TEXT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY idx_rotation_runs_trade_observed (trade_date, observed_at),
    KEY idx_rotation_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sector_rotation_snapshots (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    chain_code VARCHAR(64) NOT NULL,
    chain_name VARCHAR(128) NOT NULL,
    parent_code VARCHAR(64) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    threshold_version VARCHAR(64) NOT NULL,
    state VARCHAR(16) NULL,
    bucket VARCHAR(16) NULL,
    data_complete TINYINT(1) NOT NULL,
    total_score DECIMAL(8,2) NOT NULL,
    strength_score DECIMAL(8,2) NOT NULL,
    breadth_score DECIMAL(8,2) NOT NULL,
    amount_score DECIMAL(8,2) NOT NULL,
    persistence_score DECIMAL(8,2) NOT NULL,
    structure_score DECIMAL(8,2) NOT NULL,
    overheat_penalty DECIMAL(8,2) NOT NULL,
    reasons_json JSON NOT NULL,
    raw_json JSON NOT NULL,
    UNIQUE KEY uq_rotation_snapshot_run_chain (run_id, chain_code),
    KEY idx_rotation_snapshot_chain_observed (chain_code, observed_at),
    KEY idx_rotation_snapshot_state_observed (state, observed_at),
    CONSTRAINT fk_rotation_snapshot_run FOREIGN KEY (run_id)
        REFERENCES sector_rotation_runs(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sector_rotation_candidates (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    chain_code VARCHAR(64) NOT NULL,
    ts_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(128) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    role VARCHAR(16) NOT NULL,
    pool_rank INT NOT NULL,
    formal_eligible TINYINT(1) NOT NULL,
    held TINYINT(1) NOT NULL,
    watch_price DECIMAL(12,2) NULL,
    trigger_price DECIMAL(12,2) NULL,
    no_chase_price DECIMAL(12,2) NULL,
    invalidation_price DECIMAL(12,2) NULL,
    reasons_json JSON NOT NULL,
    rejection_json JSON NOT NULL,
    raw_json JSON NOT NULL,
    UNIQUE KEY uq_rotation_candidate_run_chain_code (run_id, chain_code, ts_code),
    KEY idx_rotation_candidate_code_observed (ts_code, observed_at),
    KEY idx_rotation_candidate_formal_role_observed (formal_eligible, role, observed_at),
    CONSTRAINT fk_rotation_candidate_run FOREIGN KEY (run_id)
        REFERENCES sector_rotation_runs(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
