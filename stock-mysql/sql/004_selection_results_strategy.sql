-- 选股结果按 strategy 分桶：同日同策略覆盖写入，不同策略互不覆盖

DELIMITER //
DROP PROCEDURE IF EXISTS migrate_selection_results_strategy//
CREATE PROCEDURE migrate_selection_results_strategy()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'selection_daily_results'
      AND COLUMN_NAME = 'strategy'
  ) THEN
    ALTER TABLE selection_daily_results
      ADD COLUMN strategy VARCHAR(32) NOT NULL DEFAULT 'combined'
      COMMENT '选股策略：combined / five_factor 等'
      AFTER trade_date;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'selection_daily_results'
      AND INDEX_NAME = 'uk_date_code'
  ) THEN
    ALTER TABLE selection_daily_results DROP INDEX uk_date_code;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'selection_daily_results'
      AND INDEX_NAME = 'uk_date_strategy_code'
  ) THEN
    ALTER TABLE selection_daily_results
      ADD UNIQUE KEY uk_date_strategy_code (trade_date, strategy, ts_code);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'selection_daily_results'
      AND INDEX_NAME = 'idx_trade_date_strategy_rank'
  ) THEN
    ALTER TABLE selection_daily_results
      ADD INDEX idx_trade_date_strategy_rank (trade_date, strategy, rank_no);
  END IF;
END//
DELIMITER ;

CALL migrate_selection_results_strategy();
DROP PROCEDURE IF EXISTS migrate_selection_results_strategy;
