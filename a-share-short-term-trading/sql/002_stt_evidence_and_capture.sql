CREATE TABLE IF NOT EXISTS stt_evidence_snapshots (
    snapshot_id CHAR(36) NOT NULL,
    code VARCHAR(10) NULL,
    kind VARCHAR(32) NOT NULL,
    as_of DATETIME NOT NULL,
    source VARCHAR(64) NOT NULL,
    parser_version VARCHAR(64) NOT NULL,
    data_json JSON NOT NULL,
    raw_evidence_ref VARCHAR(512) NOT NULL,
    data_status VARCHAR(16) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_id),
    INDEX idx_code_kind_time (code, kind, as_of),
    INDEX idx_kind_time (kind, as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易原始证据快照';

CREATE TABLE IF NOT EXISTS stt_capture_attempts (
    attempt_id CHAR(36) NOT NULL,
    code VARCHAR(10) NULL,
    kind VARCHAR(32) NOT NULL,
    source VARCHAR(64) NOT NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NOT NULL,
    status VARCHAR(16) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    field_completeness DECIMAL(5, 4) NOT NULL,
    parser_version VARCHAR(64) NOT NULL,
    raw_evidence_ref VARCHAR(512) NULL,
    error_class VARCHAR(128) NULL,
    error_message TEXT NULL,
    PRIMARY KEY (attempt_id),
    INDEX idx_kind_started (kind, started_at),
    INDEX idx_code_started (code, started_at),
    INDEX idx_status_started (status, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短线交易采集尝试审计';
