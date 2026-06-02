-- 游资轨：情绪周期日检（盘前 pre_market + 收盘 eod，与 sop_review 同级快照）

CREATE TABLE IF NOT EXISTS emotion_cycle_daily (
    trade_date DATE NOT NULL,
    checklist_slot VARCHAR(16) NOT NULL DEFAULT 'pre_market' COMMENT 'pre_market|eod',
    limit_up_count INT DEFAULT NULL COMMENT '涨停家数',
    limit_down_count INT DEFAULT NULL COMMENT '跌停家数',
    up_down_ratio VARCHAR(32) DEFAULT NULL COMMENT '涨跌家数比，如 2100:900',
    max_board_height INT DEFAULT NULL COMMENT '连板空间龙高度',
    limit_up_premium_pct DECIMAL(8, 4) DEFAULT NULL COMMENT '昨日涨停今日平均溢价%',
    explode_rate_pct DECIMAL(8, 4) DEFAULT NULL COMMENT '炸板率%',
    total_amount_yi DECIMAL(14, 2) DEFAULT NULL COMMENT '全A成交额(亿)',
    theme_count INT DEFAULT NULL COMMENT '同时在炒题材数',
    phase VARCHAR(16) DEFAULT NULL COMMENT '冰点|启动|发酵|高潮|分歧|退潮',
    phase_vs_yesterday VARCHAR(16) DEFAULT NULL COMMENT '升温|持平|降温',
    position_cap_pct DECIMAL(6, 2) DEFAULT NULL COMMENT '游资轨仓位上限%',
    allow_new_open TINYINT(1) DEFAULT NULL COMMENT '是否允许新开',
    main_theme VARCHAR(128) DEFAULT NULL COMMENT '当前最强主线',
    main_theme_is_new TINYINT(1) DEFAULT NULL COMMENT '是否新题材顶替老热点',
    drain_market TINYINT(1) DEFAULT NULL COMMENT '指数涨但个股普跌(抽水)',
    action_summary VARCHAR(64) DEFAULT NULL COMMENT '空仓|观察|试错|持仓',
    tomorrow_phase VARCHAR(16) DEFAULT NULL,
    tomorrow_position_cap_pct DECIMAL(6, 2) DEFAULT NULL,
    tomorrow_plan TEXT,
    exclude_list TEXT COMMENT '明确不做清单',
    review_notes TEXT COMMENT '复盘备注',
    raw_json JSON DEFAULT NULL COMMENT '扩展字段备份',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, checklist_slot),
    INDEX idx_phase (trade_date, phase)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情绪周期日检主表';

CREATE TABLE IF NOT EXISTS emotion_cycle_dragon_watch (
    trade_date DATE NOT NULL,
    checklist_slot VARCHAR(16) NOT NULL DEFAULT 'pre_market',
    rank_no INT NOT NULL DEFAULT 1,
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    board_height INT DEFAULT NULL COMMENT '几板',
    main_theme VARCHAR(128) DEFAULT NULL,
    checklist_pass INT DEFAULT NULL COMMENT '龙头确认项通过数(共7项)',
    notes VARCHAR(255) DEFAULT NULL,
    raw_json JSON DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, checklist_slot, ts_code),
    INDEX idx_trade_rank (trade_date, checklist_slot, rank_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情绪周期龙头观察池';
