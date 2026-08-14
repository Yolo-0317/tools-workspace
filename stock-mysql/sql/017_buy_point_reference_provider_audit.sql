-- 买点优先选股：替代参考数据源审计与可恢复检查点。

SET @bp_sql = IF(
  EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'buy_point_reference_sync_runs'
      AND column_name = 'provider'
  ),
  'SELECT 1',
  'ALTER TABLE buy_point_reference_sync_runs ADD COLUMN provider VARCHAR(32) NULL AFTER dataset'
);
PREPARE bp_stmt FROM @bp_sql;
EXECUTE bp_stmt;
DEALLOCATE PREPARE bp_stmt;

SET @bp_sql = IF(
  EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'buy_point_reference_sync_runs'
      AND column_name = 'expected_count'
  ),
  'SELECT 1',
  'ALTER TABLE buy_point_reference_sync_runs ADD COLUMN expected_count INT NULL AFTER row_count'
);
PREPARE bp_stmt FROM @bp_sql;
EXECUTE bp_stmt;
DEALLOCATE PREPARE bp_stmt;

SET @bp_sql = IF(
  EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'buy_point_reference_sync_runs'
      AND column_name = 'coverage_ratio'
  ),
  'SELECT 1',
  'ALTER TABLE buy_point_reference_sync_runs ADD COLUMN coverage_ratio DECIMAL(7,6) NULL AFTER expected_count'
);
PREPARE bp_stmt FROM @bp_sql;
EXECUTE bp_stmt;
DEALLOCATE PREPARE bp_stmt;

SET @bp_sql = IF(
  EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'buy_point_reference_sync_runs'
      AND column_name = 'details_json'
  ),
  'SELECT 1',
  'ALTER TABLE buy_point_reference_sync_runs ADD COLUMN details_json JSON NULL AFTER error_code'
);
PREPARE bp_stmt FROM @bp_sql;
EXECUTE bp_stmt;
DEALLOCATE PREPARE bp_stmt;

CREATE TABLE IF NOT EXISTS buy_point_reference_checkpoints (
  provider VARCHAR(32) NOT NULL,
  dataset VARCHAR(32) NOT NULL,
  partition_key VARCHAR(64) NOT NULL,
  cursor_value VARCHAR(64) NULL,
  status VARCHAR(16) NOT NULL,
  error_code VARCHAR(64) NULL,
  details_json JSON NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (provider, dataset, partition_key),
  KEY idx_reference_checkpoint_status (dataset, status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='买点参考数据提供方断点与恢复状态';
