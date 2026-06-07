-- 投顾周五周复盘（看板只读）

CREATE TABLE IF NOT EXISTS advisor_weekly_reviews (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  week_end_date   DATE NOT NULL COMMENT '复盘基准日（通常周五）',
  phase           TINYINT NOT NULL DEFAULT 0,
  title           VARCHAR(128) DEFAULT NULL,
  health_score    INT DEFAULT NULL,
  report_md       MEDIUMTEXT,
  report_json     JSON DEFAULT NULL COMMENT '结构化摘要',
  created_at      DATETIME NOT NULL,
  UNIQUE KEY uk_week_end (week_end_date),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
