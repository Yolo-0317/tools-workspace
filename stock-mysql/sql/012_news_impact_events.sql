-- 个股诊断标准化消息事件缓存；运行时 stt_app 仅做读写，不负责建表。

CREATE TABLE IF NOT EXISTS news_impact_events (
  event_id VARCHAR(64) PRIMARY KEY,
  title VARCHAR(512) NOT NULL,
  summary TEXT NOT NULL,
  published_at DATETIME NOT NULL,
  observed_at DATETIME NOT NULL,
  source_url VARCHAR(1024) NOT NULL,
  source_name VARCHAR(128) NOT NULL,
  source_tier VARCHAR(32) NOT NULL,
  market VARCHAR(32) NOT NULL,
  country VARCHAR(32) NOT NULL,
  subjects_json TEXT NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  direction VARCHAR(16) NOT NULL,
  confirmation_state VARCHAR(32) NOT NULL,
  scope VARCHAR(16) NOT NULL,
  valid_until DATETIME NULL,
  evidence TEXT NOT NULL,
  KEY idx_news_impact_published (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
