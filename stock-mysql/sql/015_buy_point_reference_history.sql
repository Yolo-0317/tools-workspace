-- 买点优先选股：带生效日期的行业、风险与数据覆盖事实。

CREATE TABLE IF NOT EXISTS buy_point_sector_memberships (
  code CHAR(6) NOT NULL,
  sector_code VARCHAR(24) NOT NULL,
  sector_name VARCHAR(128) NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NULL,
  source VARCHAR(64) NOT NULL,
  captured_at DATETIME(6) NOT NULL,
  PRIMARY KEY (code, sector_code, valid_from),
  KEY idx_sector_validity (sector_code, valid_from, valid_to),
  KEY idx_code_validity (code, valid_from, valid_to)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='买点选股点时申万行业成员关系';

CREATE TABLE IF NOT EXISTS buy_point_risk_flags (
  flag_id CHAR(64) NOT NULL,
  code CHAR(6) NOT NULL,
  flag_type VARCHAR(48) NOT NULL,
  severity VARCHAR(16) NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE NULL,
  source VARCHAR(64) NOT NULL,
  evidence_ref VARCHAR(1024) NOT NULL,
  captured_at DATETIME(6) NOT NULL,
  PRIMARY KEY (flag_id),
  KEY idx_risk_code_validity (code, effective_from, effective_to),
  KEY idx_risk_severity_validity (severity, effective_from, effective_to)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='买点选股点时ST与重大公告风险';

CREATE TABLE IF NOT EXISTS buy_point_reference_sync_runs (
  run_id CHAR(36) NOT NULL,
  dataset VARCHAR(32) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  status VARCHAR(16) NOT NULL,
  row_count INT NOT NULL,
  error_code VARCHAR(64) NULL,
  captured_at DATETIME(6) NOT NULL,
  PRIMARY KEY (run_id),
  KEY idx_dataset_bounds (dataset, start_date, end_date, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='买点选股参考数据同步覆盖记录';
