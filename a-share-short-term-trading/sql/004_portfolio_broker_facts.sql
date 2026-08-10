SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_positions' AND column_name = 'available_shares'),
    'SELECT 1',
    'ALTER TABLE portfolio_positions ADD COLUMN available_shares INT NULL AFTER shares'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_positions' AND column_name = 'current_price'),
    'SELECT 1',
    'ALTER TABLE portfolio_positions ADD COLUMN current_price DECIMAL(18, 4) NULL AFTER cost_price'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_positions' AND column_name = 'market_value'),
    'SELECT 1',
    'ALTER TABLE portfolio_positions ADD COLUMN market_value DECIMAL(18, 4) NULL AFTER current_price'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_positions' AND column_name = 'position_pnl'),
    'SELECT 1',
    'ALTER TABLE portfolio_positions ADD COLUMN position_pnl DECIMAL(18, 4) NULL AFTER market_value'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_positions' AND column_name = 'position_pnl_pct'),
    'SELECT 1',
    'ALTER TABLE portfolio_positions ADD COLUMN position_pnl_pct DECIMAL(12, 6) NULL AFTER position_pnl'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_positions' AND column_name = 'daily_pnl'),
    'SELECT 1',
    'ALTER TABLE portfolio_positions ADD COLUMN daily_pnl DECIMAL(18, 4) NULL AFTER position_pnl_pct'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_positions' AND column_name = 'daily_pnl_pct'),
    'SELECT 1',
    'ALTER TABLE portfolio_positions ADD COLUMN daily_pnl_pct DECIMAL(12, 6) NULL AFTER daily_pnl'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_positions' AND column_name = 'broker_captured_at'),
    'SELECT 1',
    'ALTER TABLE portfolio_positions ADD COLUMN broker_captured_at DATETIME(6) NULL AFTER daily_pnl_pct'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_account' AND column_name = 'cash_balance'),
    'SELECT 1',
    'ALTER TABLE portfolio_account ADD COLUMN cash_balance DECIMAL(18, 4) NULL AFTER available_cash'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_account' AND column_name = 'withdrawable_cash'),
    'SELECT 1',
    'ALTER TABLE portfolio_account ADD COLUMN withdrawable_cash DECIMAL(18, 4) NULL AFTER cash_balance'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_account' AND column_name = 'frozen_cash'),
    'SELECT 1',
    'ALTER TABLE portfolio_account ADD COLUMN frozen_cash DECIMAL(18, 4) NULL AFTER withdrawable_cash'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_account' AND column_name = 'daily_pnl'),
    'SELECT 1',
    'ALTER TABLE portfolio_account ADD COLUMN daily_pnl DECIMAL(18, 4) NULL AFTER holding_pnl'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;

SET @stt_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'portfolio_account' AND column_name = 'broker_captured_at'),
    'SELECT 1',
    'ALTER TABLE portfolio_account ADD COLUMN broker_captured_at DATETIME(6) NULL AFTER daily_pnl'
);
PREPARE stt_stmt FROM @stt_sql;
EXECUTE stt_stmt;
DEALLOCATE PREPARE stt_stmt;
