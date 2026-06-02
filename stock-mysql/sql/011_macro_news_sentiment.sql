-- 财经快讯利好/利空标记（sync_macro_news 每 15 分钟写入）

DELIMITER //
DROP PROCEDURE IF EXISTS migrate_macro_news_sentiment//
CREATE PROCEDURE migrate_macro_news_sentiment()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'macro_news_items'
      AND COLUMN_NAME = 'sentiment'
  ) THEN
    ALTER TABLE macro_news_items
      ADD COLUMN sentiment ENUM('bullish', 'bearish', 'neutral') NOT NULL DEFAULT 'neutral'
      COMMENT '利好/利空/中性（关键词分类）'
      AFTER category;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'macro_news_items'
      AND INDEX_NAME = 'idx_sentiment_seen'
  ) THEN
    ALTER TABLE macro_news_items
      ADD INDEX idx_sentiment_seen (sentiment, last_seen_at);
  END IF;
END//
DELIMITER ;

CALL migrate_macro_news_sentiment();
DROP PROCEDURE IF EXISTS migrate_macro_news_sentiment;
