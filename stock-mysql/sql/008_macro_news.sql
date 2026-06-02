-- 东财 7×24 财经快讯 + 战报快照（看板财经页）

CREATE TABLE IF NOT EXISTS macro_news_items (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  href          VARCHAR(512) NOT NULL,
  title         VARCHAR(256) NOT NULL,
  summary       TEXT,
  news_time     VARCHAR(16) DEFAULT NULL COMMENT '页面 HH:MM',
  published_at  DATETIME DEFAULT NULL,
  category      ENUM('geo', 'domestic', 'other') NOT NULL DEFAULT 'other',
  source        VARCHAR(32) NOT NULL DEFAULT 'kuaixun',
  fetched_at    DATETIME NOT NULL,
  last_seen_at  DATETIME NOT NULL,
  UNIQUE KEY uk_href (href(191)),
  KEY idx_published (published_at),
  KEY idx_category_seen (category, last_seen_at),
  KEY idx_last_seen (last_seen_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS macro_news_fetch_runs (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  started_at   DATETIME NOT NULL,
  finished_at  DATETIME DEFAULT NULL,
  item_count   INT NOT NULL DEFAULT 0,
  new_count    INT NOT NULL DEFAULT 0,
  ok           TINYINT(1) NOT NULL DEFAULT 0,
  error_msg    TEXT,
  KEY idx_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS briefing_snapshots (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  briefing_date DATE NOT NULL,
  slot          VARCHAR(8) NOT NULL,
  title         VARCHAR(64) DEFAULT NULL,
  raw_text      MEDIUMTEXT,
  ai_summary    TEXT,
  created_at    DATETIME NOT NULL,
  UNIQUE KEY uk_date_slot (briefing_date, slot),
  KEY idx_briefing_date (briefing_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
