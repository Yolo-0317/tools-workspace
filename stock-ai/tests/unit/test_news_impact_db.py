from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools.news_impact_db import (
    decode_macro_cache_summary,
    encode_macro_cache_summary,
    ensure_news_impact_tables,
    load_cached_events,
    upsert_cached_events,
)
from stock_ai.news_impact import NewsEvent
from stock_ai.news_impact.providers import load_news_coverage


TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 12, 9, 0, tzinfo=TZ)


def test_cached_event_round_trip_and_idempotent_update():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    ensure_news_impact_tables(engine=engine)
    original = NewsEvent(
        "evt", "标题", "摘要", NOW, NOW, "https://example.com", "公司官网", "official",
        "US", "US", ("CoreWeave",), "earnings", "positive", "official", "overseas", evidence="证据",
    )
    revised = NewsEvent(**{**original.__dict__, "summary": "更新摘要"})
    upsert_cached_events([original, revised], engine=engine)
    loaded = load_cached_events(since=NOW - timedelta(days=1), engine=engine)
    assert len(loaded) == 1
    assert loaded[0].summary == "更新摘要"
    assert loaded[0].subjects == ("CoreWeave",)


def test_news_coverage_merges_verified_cache_with_macro_pool():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    ensure_news_impact_tables(engine=engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE macro_news_items (href TEXT, title TEXT, summary TEXT, published_at DATETIME, source TEXT)"))
    cached = NewsEvent(
        "verified", "Nebius财报", "AI云收入增长", NOW, NOW, "https://example.com/nebius", "公司官网", "official",
        "US", "US", ("Nebius",), "earnings", "positive", "official", "overseas", evidence="官方财报",
    )
    upsert_cached_events([cached], engine=engine)
    coverage = load_news_coverage(engine=engine, now=NOW)
    assert [event.event_id for event in coverage.events] == ["verified"]
    assert "overseas_company" not in coverage.missing_scopes


def test_runtime_upsert_does_not_attempt_schema_creation():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    cached = NewsEvent(
        "no-table", "标题", "摘要", NOW, NOW, "https://example.com", "公司官网", "official",
        "US", "US", ("CoreWeave",), "earnings", "positive", "official", "overseas", evidence="证据",
    )
    try:
        upsert_cached_events([cached], engine=engine)
    except OperationalError:
        pass
    else:
        raise AssertionError("运行时写入不应自动创建事件表")


def test_macro_news_fallback_preserves_standard_event_fields():
    original = NewsEvent(
        "fallback", "CoreWeave财报", "资本开支上调", NOW, NOW,
        "https://example.com/coreweave", "公司官网", "official", "US", "US",
        ("CoreWeave",), "earnings", "positive", "premarket", "overseas", evidence="官方材料",
    )
    restored = decode_macro_cache_summary(encode_macro_cache_summary(original))
    assert restored == original
