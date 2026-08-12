"""标准化消息事件缓存；供聊天核验结果与批量诊断复用。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, delete, select, text
from sqlalchemy.exc import SQLAlchemyError

from stock_ai.news_impact import NewsEvent

metadata = MetaData()
MACRO_PREFIX = "NEWS_IMPACT_JSON:"
events_table = Table(
    "news_impact_events",
    metadata,
    Column("event_id", String(64), primary_key=True),
    Column("title", String(512), nullable=False),
    Column("summary", Text, nullable=False),
    Column("published_at", DateTime, nullable=False, index=True),
    Column("observed_at", DateTime, nullable=False),
    Column("source_url", String(1024), nullable=False),
    Column("source_name", String(128), nullable=False),
    Column("source_tier", String(32), nullable=False),
    Column("market", String(32), nullable=False),
    Column("country", String(32), nullable=False),
    Column("subjects_json", Text, nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("direction", String(16), nullable=False),
    Column("confirmation_state", String(32), nullable=False),
    Column("scope", String(16), nullable=False),
    Column("valid_until", DateTime),
    Column("evidence", Text, nullable=False),
)


def _engine(engine=None):
    if engine is not None:
        return engine
    from scripts.tools.portfolio_db import get_engine
    return get_engine()


def ensure_news_impact_tables(*, engine=None) -> None:
    target = _engine(engine)
    if target is None:
        raise RuntimeError("未配置MYSQL_URL，无法创建消息事件缓存")
    metadata.create_all(target, tables=[events_table])


def encode_macro_cache_summary(event: NewsEvent) -> str:
    payload = {
        **event.__dict__,
        "published_at": event.published_at.isoformat(),
        "observed_at": event.observed_at.isoformat(),
        "valid_until": event.valid_until.isoformat() if event.valid_until else None,
        "subjects": list(event.subjects),
    }
    return MACRO_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_macro_cache_summary(summary: str) -> NewsEvent:
    if not summary.startswith(MACRO_PREFIX):
        raise ValueError("不是标准消息缓存记录")
    values = json.loads(summary[len(MACRO_PREFIX):])
    for key in ("published_at", "observed_at", "valid_until"):
        if values.get(key):
            values[key] = datetime.fromisoformat(values[key])
    values["subjects"] = tuple(values.get("subjects") or ())
    return NewsEvent(**values)


def _upsert_macro_fallback(events: list[NewsEvent], target) -> int:
    now = datetime.now()
    with target.begin() as conn:
        for event in events:
            href = f"{event.source_url}#news-impact-{event.event_id}"[:512]
            conn.execute(text("DELETE FROM macro_news_items WHERE href = :href"), {"href": href})
            conn.execute(text("""
                INSERT INTO macro_news_items
                  (href, title, summary, news_time, published_at, category, sentiment, source, fetched_at, last_seen_at)
                VALUES
                  (:href, :title, :summary, :news_time, :published_at, 'other', 'neutral', 'news-impact-json', :now, :now)
            """), {
                "href": href,
                "title": event.title[:256],
                "summary": encode_macro_cache_summary(event),
                "news_time": event.published_at.strftime("%H:%M"),
                "published_at": event.published_at.replace(tzinfo=None),
                "now": now,
            })
    return len(events)


def upsert_cached_events(events: list[NewsEvent], *, engine=None) -> int:
    target = _engine(engine)
    if target is None:
        raise RuntimeError("未配置MYSQL_URL，无法缓存消息事件")
    try:
        with target.begin() as conn:
            for event in events:
                conn.execute(delete(events_table).where(events_table.c.event_id == event.event_id))
                conn.execute(events_table.insert().values(
                    event_id=event.event_id,
                    title=event.title,
                    summary=event.summary,
                    published_at=event.published_at.replace(tzinfo=None),
                    observed_at=event.observed_at.replace(tzinfo=None),
                    source_url=event.source_url,
                    source_name=event.source_name,
                    source_tier=event.source_tier,
                    market=event.market,
                    country=event.country,
                    subjects_json=json.dumps(event.subjects, ensure_ascii=False),
                    event_type=event.event_type,
                    direction=event.direction,
                    confirmation_state=event.confirmation_state,
                    scope=event.scope,
                    valid_until=event.valid_until.replace(tzinfo=None) if event.valid_until else None,
                    evidence=event.evidence,
                ))
    except SQLAlchemyError:
        return _upsert_macro_fallback(events, target)
    return len(events)


def load_cached_events(*, since: datetime, engine=None) -> list[NewsEvent]:
    target = _engine(engine)
    if target is None:
        return []
    try:
        with target.connect() as conn:
            rows = conn.execute(
                select(events_table).where(events_table.c.published_at >= since.replace(tzinfo=None)).order_by(events_table.c.published_at.desc())
            ).mappings().all()
    except SQLAlchemyError:
        try:
            with target.connect() as conn:
                fallback = conn.execute(text("""
                    SELECT summary FROM macro_news_items
                    WHERE source = 'news-impact-json' AND published_at >= :since
                    ORDER BY published_at DESC
                """), {"since": since.replace(tzinfo=None)}).mappings().all()
            return [decode_macro_cache_summary(str(row["summary"])) for row in fallback]
        except SQLAlchemyError:
            return []
    tz = since.tzinfo
    return [
        NewsEvent(
            event_id=row["event_id"], title=row["title"], summary=row["summary"],
            published_at=row["published_at"].replace(tzinfo=tz), observed_at=row["observed_at"].replace(tzinfo=tz),
            source_url=row["source_url"], source_name=row["source_name"], source_tier=row["source_tier"],
            market=row["market"], country=row["country"], subjects=tuple(json.loads(row["subjects_json"])),
            event_type=row["event_type"], direction=row["direction"], confirmation_state=row["confirmation_state"],
            scope=row["scope"], valid_until=row["valid_until"].replace(tzinfo=tz) if row["valid_until"] else None,
            evidence=row["evidence"],
        )
        for row in rows
    ]
