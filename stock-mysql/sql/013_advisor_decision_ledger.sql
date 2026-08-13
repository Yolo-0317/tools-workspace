-- 状态化个人投顾：决策周期投影 + 不可覆盖事件账本

CREATE TABLE IF NOT EXISTS advisor_decision_cycles (
    cycle_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    started_trade_date DATE NOT NULL,
    review_trade_date DATE NOT NULL,
    expiry_trade_date DATE NOT NULL,
    initial_action VARCHAR(64) NOT NULL,
    current_action VARCHAR(64) NOT NULL,
    thesis_json JSON DEFAULT NULL,
    trigger_plan_json JSON DEFAULT NULL,
    selection_source VARCHAR(64) DEFAULT NULL,
    selection_result_id BIGINT UNSIGNED DEFAULT NULL,
    status ENUM('ACTIVE', 'REVIEW_DUE', 'EXTENDED', 'CLOSED', 'INVALIDATED')
        NOT NULL DEFAULT 'ACTIVE',
    source VARCHAR(32) NOT NULL DEFAULT 'advisor',
    opened_by_event_id BIGINT UNSIGNED DEFAULT NULL,
    closed_by_event_id BIGINT UNSIGNED DEFAULT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (cycle_id),
    INDEX idx_cycle_code_status (ts_code, status),
    INDEX idx_cycle_expiry (expiry_trade_date, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='3至5交易日投顾决策周期当前投影';

CREATE TABLE IF NOT EXISTS advisor_decision_events (
    event_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    cycle_id BIGINT UNSIGNED NOT NULL,
    event_type ENUM(
        'CYCLE_OPENED',
        'DAILY_OBSERVATION',
        'HARD_EVENT',
        'ACTION_MAINTAINED',
        'ACTION_UPGRADED',
        'ACTION_DOWNGRADED',
        'CYCLE_EXTENDED',
        'CYCLE_CLOSED',
        'AI_ACTION_REJECTED',
        'CORRECTION'
    ) NOT NULL,
    previous_action VARCHAR(64) DEFAULT NULL,
    new_action VARCHAR(64) DEFAULT NULL,
    reason_json JSON DEFAULT NULL,
    evidence_json JSON DEFAULT NULL,
    source VARCHAR(32) NOT NULL,
    observed_at DATETIME(6) DEFAULT NULL,
    effective_trade_date DATE NOT NULL,
    supersedes_event_id BIGINT UNSIGNED DEFAULT NULL,
    event_fingerprint CHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (event_id),
    UNIQUE KEY uk_decision_event_fingerprint (event_fingerprint),
    INDEX idx_decision_event_cycle_date (cycle_id, effective_trade_date),
    INDEX idx_decision_event_type (event_type, effective_trade_date),
    CONSTRAINT fk_decision_event_cycle
        FOREIGN KEY (cycle_id) REFERENCES advisor_decision_cycles (cycle_id),
    CONSTRAINT fk_decision_event_correction
        FOREIGN KEY (supersedes_event_id) REFERENCES advisor_decision_events (event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='不可覆盖的投顾决策事件账本';

CREATE TABLE IF NOT EXISTS portfolio_position_events (
    position_event_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    cycle_id BIGINT UNSIGNED DEFAULT NULL,
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    event_type ENUM('OPENED', 'ADDED', 'REDUCED', 'CLOSED', 'COST_ADJUSTED', 'CORRECTION')
        NOT NULL,
    shares_before INT NOT NULL,
    shares_after INT NOT NULL,
    shares_delta INT NOT NULL,
    cost_before DECIMAL(18, 6) DEFAULT NULL,
    cost_after DECIMAL(18, 6) DEFAULT NULL,
    execution_price DECIMAL(18, 6) DEFAULT NULL,
    realized_pnl DECIMAL(18, 4) DEFAULT NULL,
    plan_compliance ENUM('MATCHED', 'DEVIATED', 'UNKNOWN')
        NOT NULL DEFAULT 'UNKNOWN',
    evidence_json JSON DEFAULT NULL,
    source VARCHAR(32) NOT NULL,
    broker_captured_at DATETIME(6) NOT NULL,
    event_fingerprint CHAR(64) NOT NULL,
    supersedes_event_id BIGINT UNSIGNED DEFAULT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (position_event_id),
    UNIQUE KEY uk_position_event_fingerprint (event_fingerprint),
    INDEX idx_position_event_code_time (ts_code, broker_captured_at),
    INDEX idx_position_event_cycle (cycle_id, broker_captured_at),
    CONSTRAINT fk_position_event_cycle
        FOREIGN KEY (cycle_id) REFERENCES advisor_decision_cycles (cycle_id),
    CONSTRAINT fk_position_event_correction
        FOREIGN KEY (supersedes_event_id) REFERENCES portfolio_position_events (position_event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='不可覆盖的券商仓位变化事件账本';

DROP TRIGGER IF EXISTS trg_advisor_decision_events_no_update;
DROP TRIGGER IF EXISTS trg_advisor_decision_events_no_delete;
DROP TRIGGER IF EXISTS trg_portfolio_position_events_no_update;
DROP TRIGGER IF EXISTS trg_portfolio_position_events_no_delete;

DELIMITER $$

CREATE TRIGGER trg_advisor_decision_events_no_update
BEFORE UPDATE ON advisor_decision_events
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'advisor_decision_events is append-only';
END$$

CREATE TRIGGER trg_advisor_decision_events_no_delete
BEFORE DELETE ON advisor_decision_events
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'advisor_decision_events is append-only';
END$$

CREATE TRIGGER trg_portfolio_position_events_no_update
BEFORE UPDATE ON portfolio_position_events
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'portfolio_position_events is append-only';
END$$

CREATE TRIGGER trg_portfolio_position_events_no_delete
BEFORE DELETE ON portfolio_position_events
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'portfolio_position_events is append-only';
END$$

DELIMITER ;
