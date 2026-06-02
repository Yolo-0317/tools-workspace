#!/usr/bin/env python3
"""财经快讯与战报快照 MySQL 读写。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import text

from scripts.tools.fetch_eastmoney_macro_news import MacroNewsItem
from scripts.tools.news_sentiment import NewsSentiment, classify_news_sentiment
from scripts.tools.portfolio_db import get_engine

TZ = ZoneInfo("Asia/Shanghai")

GEOPOLITICS_KEYWORDS = ("伊朗", "美伊", "特朗普", "霍尔木兹", "以军", "中东", "制裁", "停火")

NewsCategory = Literal["geo", "domestic", "other"]


@dataclass
class NewsItemRow:
    id: int
    href: str
    title: str
    summary: str
    news_time: str
    published_at: str | None
    category: str
    sentiment: str
    source: str
    fetched_at: str
    last_seen_at: str


@dataclass
class BriefingSnapshotRow:
    briefing_date: str
    slot: str
    title: str
    raw_text: str
    ai_summary: str
    created_at: str


def classify_category(title: str, summary: str) -> NewsCategory:
    blob = f"{title} {summary}"
    if any(kw in blob for kw in GEOPOLITICS_KEYWORDS):
        return "geo"
    return "domestic"


def _parse_published_at(news_time: str, *, ref: datetime | None = None) -> datetime | None:
    ref = ref or datetime.now(TZ)
    raw = (news_time or "").strip()
    if not raw:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.strptime(raw, fmt).time()
            return datetime.combine(ref.date(), t, tzinfo=TZ).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _row_to_macro_item(row: Any) -> MacroNewsItem:
    return MacroNewsItem(
        title=str(row.title or ""),
        summary=str(row.summary or ""),
        time=str(row.news_time or ""),
        href=str(row.href or ""),
        source=str(row.source or "kuaixun"),
    )


def upsert_news_items(items: list[MacroNewsItem], *, now: datetime | None = None) -> tuple[int, int]:
    """写入快讯，返回 (总数, 新增数)。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法落库")

    now = (now or datetime.now(TZ)).replace(tzinfo=None)
    new_count = 0

    with engine.begin() as conn:
        for item in items:
            href = (item.href or "").strip()
            if not href:
                continue
            category = classify_category(item.title, item.summary)
            sentiment = classify_news_sentiment(item.title, item.summary)
            published = _parse_published_at(item.time, ref=now.replace(tzinfo=TZ))
            result = conn.execute(
                text(
                    """
                    INSERT INTO macro_news_items
                      (href, title, summary, news_time, published_at, category, sentiment, source,
                       fetched_at, last_seen_at)
                    VALUES
                      (:href, :title, :summary, :news_time, :published_at, :category, :sentiment, :source,
                       :now, :now)
                    ON DUPLICATE KEY UPDATE
                      title = VALUES(title),
                      summary = VALUES(summary),
                      news_time = VALUES(news_time),
                      published_at = COALESCE(VALUES(published_at), published_at),
                      category = VALUES(category),
                      sentiment = VALUES(sentiment),
                      source = VALUES(source),
                      last_seen_at = VALUES(last_seen_at)
                    """
                ),
                {
                    "href": href[:512],
                    "title": (item.title or "")[:256],
                    "summary": item.summary or "",
                    "news_time": item.time or "",
                    "published_at": published,
                    "category": category,
                    "sentiment": sentiment,
                    "source": item.source or "kuaixun",
                    "now": now,
                },
            )
            if result.rowcount == 1:
                new_count += 1

    return len(items), new_count


def refresh_sentiment_for_recent(*, hours: int = 72) -> int:
    """为近期已落库快讯重算 sentiment（补全迁移前或未再抓取条目）。"""
    engine = get_engine()
    if engine is None:
        return 0

    since = (datetime.now(TZ) - timedelta(hours=hours)).replace(tzinfo=None)
    updated = 0
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, title, summary
                    FROM macro_news_items
                    WHERE last_seen_at >= :since
                    """
                ),
                {"since": since},
            ).fetchall()
    except Exception:
        return 0

    if not rows:
        return 0

    with engine.begin() as conn:
        for row in rows:
            sentiment: NewsSentiment = classify_news_sentiment(
                str(row.title or ""),
                str(row.summary or ""),
            )
            conn.execute(
                text(
                    """
                    UPDATE macro_news_items
                    SET sentiment = :sentiment
                    WHERE id = :id
                    """
                ),
                {"id": int(row.id), "sentiment": sentiment},
            )
            updated += 1
    return updated


def record_fetch_run(
    *,
    started_at: datetime,
    finished_at: datetime,
    item_count: int,
    new_count: int,
    ok: bool,
    error_msg: str | None = None,
) -> None:
    engine = get_engine()
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO macro_news_fetch_runs
                  (started_at, finished_at, item_count, new_count, ok, error_msg)
                VALUES (:started, :finished, :items, :new, :ok, :err)
                """
            ),
            {
                "started": started_at.replace(tzinfo=None),
                "finished": finished_at.replace(tzinfo=None),
                "items": item_count,
                "new": new_count,
                "ok": 1 if ok else 0,
                "err": error_msg,
            },
        )


def load_recent_news(
    *,
    hours: int = 24,
    limit: int = 40,
    category: NewsCategory | None = None,
) -> list[MacroNewsItem]:
    engine = get_engine()
    if engine is None:
        return []

    since = (datetime.now(TZ) - timedelta(hours=hours)).replace(tzinfo=None)
    sql = """
        SELECT href, title, summary, news_time, source
        FROM macro_news_items
        WHERE last_seen_at >= :since
    """
    params: dict[str, Any] = {"since": since, "limit": limit}
    if category:
        sql += " AND category = :category"
        params["category"] = category
    sql += " ORDER BY COALESCE(published_at, last_seen_at) DESC LIMIT :limit"

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return []
    return [_row_to_macro_item(r) for r in rows]


def list_news_items(
    *,
    day: date | None = None,
    category: NewsCategory | None = None,
    sentiment: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    engine = get_engine()
    if engine is None:
        return []

    day = day or datetime.now(TZ).date()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)

    sql = """
        SELECT id, href, title, summary, news_time, published_at, category, sentiment, source,
               fetched_at, last_seen_at
        FROM macro_news_items
        WHERE COALESCE(published_at, last_seen_at) >= :start
          AND COALESCE(published_at, last_seen_at) <= :end
    """
    params: dict[str, Any] = {"start": start, "end": end, "limit": limit}
    if category:
        sql += " AND category = :category"
        params["category"] = category
    if sentiment in {"bullish", "bearish", "neutral"}:
        sql += " AND sentiment = :sentiment"
        params["sentiment"] = sentiment
    sql += """
        ORDER BY COALESCE(published_at, last_seen_at) DESC
        LIMIT :limit
    """

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        pub = row.published_at
        out.append(
            {
                "id": int(row.id),
                "href": row.href,
                "title": row.title,
                "summary": row.summary or "",
                "news_time": row.news_time or "",
                "published_at": pub.isoformat(sep=" ", timespec="seconds") if pub else None,
                "category": row.category,
                "sentiment": getattr(row, "sentiment", None) or "neutral",
                "source": row.source,
                "fetched_at": row.fetched_at.isoformat(sep=" ", timespec="seconds")
                if row.fetched_at
                else None,
                "last_seen_at": row.last_seen_at.isoformat(sep=" ", timespec="seconds")
                if row.last_seen_at
                else None,
            }
        )
    return out


def news_meta(*, day: date | None = None) -> dict[str, Any]:
    engine = get_engine()
    if engine is None:
        return {"ok": False, "error": "MySQL 未配置"}

    day = day or datetime.now(TZ).date()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)

    try:
        with engine.connect() as conn:
            last_run = conn.execute(
                text(
                    """
                    SELECT started_at, finished_at, item_count, new_count, ok, error_msg
                    FROM macro_news_fetch_runs
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                )
            ).fetchone()
            counts = conn.execute(
                text(
                    """
                    SELECT category, COUNT(*) AS cnt
                    FROM macro_news_items
                    WHERE COALESCE(published_at, last_seen_at) >= :start
                      AND COALESCE(published_at, last_seen_at) <= :end
                    GROUP BY category
                    """
                ),
                {"start": start, "end": end},
            ).fetchall()
            sentiment_counts = conn.execute(
                text(
                    """
                    SELECT sentiment, COUNT(*) AS cnt
                    FROM macro_news_items
                    WHERE COALESCE(published_at, last_seen_at) >= :start
                      AND COALESCE(published_at, last_seen_at) <= :end
                    GROUP BY sentiment
                    """
                ),
                {"start": start, "end": end},
            ).fetchall()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    by_cat = {str(r.category): int(r.cnt) for r in counts}
    by_sentiment = {str(r.sentiment): int(r.cnt) for r in sentiment_counts}
    meta: dict[str, Any] = {
        "ok": True,
        "date": day.isoformat(),
        "total_today": sum(by_cat.values()),
        "counts": by_cat,
        "sentiment_counts": by_sentiment,
    }
    if last_run:
        meta["last_fetch"] = {
            "started_at": last_run.started_at.isoformat(sep=" ", timespec="seconds")
            if last_run.started_at
            else None,
            "finished_at": last_run.finished_at.isoformat(sep=" ", timespec="seconds")
            if last_run.finished_at
            else None,
            "item_count": int(last_run.item_count or 0),
            "new_count": int(last_run.new_count or 0),
            "ok": bool(last_run.ok),
            "error_msg": last_run.error_msg,
        }
    return meta


def save_briefing_snapshot(
    *,
    slot: str,
    title: str,
    raw_text: str,
    ai_summary: str,
    briefing_date: date | None = None,
    created_at: datetime | None = None,
) -> None:
    engine = get_engine()
    if engine is None:
        return

    briefing_date = briefing_date or datetime.now(TZ).date()
    created_at = (created_at or datetime.now(TZ)).replace(tzinfo=None)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO briefing_snapshots
                  (briefing_date, slot, title, raw_text, ai_summary, created_at)
                VALUES (:d, :slot, :title, :raw, :ai, :created)
                ON DUPLICATE KEY UPDATE
                  title = VALUES(title),
                  raw_text = VALUES(raw_text),
                  ai_summary = VALUES(ai_summary),
                  created_at = VALUES(created_at)
                """
            ),
            {
                "d": briefing_date,
                "slot": slot,
                "title": title[:64],
                "raw": raw_text,
                "ai": ai_summary,
                "created": created_at,
            },
        )


def list_briefing_snapshots(*, day: date | None = None) -> list[dict[str, Any]]:
    engine = get_engine()
    if engine is None:
        return []

    day = day or datetime.now(TZ).date()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT briefing_date, slot, title, raw_text, ai_summary, created_at
                    FROM briefing_snapshots
                    WHERE briefing_date = :d
                    ORDER BY created_at DESC, slot DESC
                    """
                ),
                {"d": day},
            ).fetchall()
    except Exception:
        return []

    return [
        {
            "briefing_date": row.briefing_date.isoformat(),
            "slot": row.slot,
            "title": row.title or "",
            "raw_text": row.raw_text or "",
            "ai_summary": row.ai_summary or "",
            "created_at": row.created_at.isoformat(sep=" ", timespec="seconds")
            if row.created_at
            else None,
        }
        for row in rows
    ]


def latest_briefing_snapshot() -> dict[str, Any] | None:
    engine = get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT briefing_date, slot, title, raw_text, ai_summary, created_at
                    FROM briefing_snapshots
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return {
        "briefing_date": row.briefing_date.isoformat(),
        "slot": row.slot,
        "title": row.title or "",
        "raw_text": row.raw_text or "",
        "ai_summary": row.ai_summary or "",
        "created_at": row.created_at.isoformat(sep=" ", timespec="seconds")
        if row.created_at
        else None,
    }


def macro_items_as_dicts(items: list[MacroNewsItem]) -> list[dict[str, Any]]:
    return [asdict(x) for x in items]
