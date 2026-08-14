SET @advisor_sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'advisor_decision_cycles'
          AND column_name = 'selection_plan_id'
    ),
    'SELECT 1',
    'ALTER TABLE advisor_decision_cycles ADD COLUMN selection_plan_id CHAR(36) NULL AFTER selection_result_id'
);
PREPARE advisor_stmt FROM @advisor_sql;
EXECUTE advisor_stmt;
DEALLOCATE PREPARE advisor_stmt;

SET @advisor_sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'advisor_decision_cycles'
          AND index_name = 'idx_advisor_selection_plan'
    ),
    'SELECT 1',
    'ALTER TABLE advisor_decision_cycles ADD INDEX idx_advisor_selection_plan (selection_plan_id)'
);
PREPARE advisor_stmt FROM @advisor_sql;
EXECUTE advisor_stmt;
DEALLOCATE PREPARE advisor_stmt;
