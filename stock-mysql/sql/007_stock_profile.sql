-- 入选股档案（OpenCLI 东财 enrich，按 ts_code 累积）

CREATE TABLE IF NOT EXISTS stock_profile (
    ts_code VARCHAR(10) NOT NULL COMMENT '6 位代码',
    name VARCHAR(64) DEFAULT NULL,
    industry VARCHAR(128) DEFAULT NULL COMMENT '所属行业',
    concepts JSON DEFAULT NULL COMMENT '概念/题材列表',
    profile_text TEXT DEFAULT NULL COMMENT '公司简介摘要',
    info_text TEXT DEFAULT NULL COMMENT '行情页 brief_info 原文',
    sectors_text TEXT DEFAULT NULL COMMENT 'F10 所属板块原文',
    source VARCHAR(32) NOT NULL DEFAULT 'eastmoney-opencli',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code),
    INDEX idx_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='入选股东财档案';
