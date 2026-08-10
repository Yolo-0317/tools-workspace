#!/usr/bin/env python3
"""财经快讯与战报快照 MySQL 读写。"""

from __future__ import annotations

import re
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

# 国家队 / 监管稳市（须高于地缘初筛分，见 _attention_score）
MARKET_RESCUE_KEYWORDS = (
    "中国国新",
    "国新投资",
    "中国诚通",
    "诚通资本",
    "中央汇金",
    "汇金",
    "证金",
    "维护市场稳定",
    "维护资本市场",
    "资本市场平稳",
    "稳市机制",
    "稳市",
    "救市",
    "托底",
    "专项再贷款",
    "股票回购增持再贷款",
    "监管座谈",
    "证监会",
    "座谈会",
    "央企密集增持",
    "500亿元",
    "500亿",
    "近百亿元",
)

MARKET_RESCUE_STRONG_KEYWORDS = (
    "维护市场稳定",
    "维护资本市场",
    "资本市场平稳",
    "稳市机制",
    "央企密集增持",
    "中国国新",
    "中国诚通",
    "专项再贷款",
    "股票回购增持再贷款",
    "500亿元",
    "500亿",
    "600亿元",
    "600亿",
    "监管座谈护航",
)

# 当日盘面主线（科创/半导体深 V 等）；大涨日须能压过稳市旧闻
SESSION_THEME_KEYWORDS = (
    "科创50",
    "V型反转",
    "半导体领涨",
    "芯片产业链",
    "科创芯片",
    "跌停潮后半导体",
    "硬科技全线",
)

SESSION_THEME_STRONG_KEYWORDS = (
    "V型反转",
    "跌停潮后半导体",
    "科创50强势反攻",
    "科创50暴涨",
    "科创50涨超",
    "科创50涨幅扩大",
    "半导体领涨",
)

# 周末要闻：优先带 A 股公司/代码/交易信号的快讯（搜一搜友好）
_STOCK_CODE_RE = re.compile(r"(?<!\d)(?:00|30|60|68)\d{4}(?!\d)")
_STOCK_NEWS_KEYWORDS = (
    "涨停",
    "跌停",
    "股份",
    "集团",
    "控股",
    "财报",
    "业绩",
    "净利",
    "回购",
    "增持",
    "减持",
    "立案",
    "中标",
    "收购",
    "并购",
    "停牌",
    "复牌",
    "龙虎榜",
    "研报",
    "评级",
    "上市公司",
    "业绩预告",
    "三季报",
    "年报",
    "中报",
    "定增",
    "配股",
    "ST",
    "*ST",
)

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


def market_rescue_news_blob(item: dict[str, Any] | MacroNewsItem) -> str:
    if isinstance(item, MacroNewsItem):
        return f"{item.title} {item.summary}"
    return f"{item.get('title') or ''} {item.get('summary') or ''}"


def market_rescue_attention_boost(item: dict[str, Any] | MacroNewsItem) -> float:
    """稳市要闻加分：强关键词一次到位，避免被地缘 heat 压过。"""
    blob = market_rescue_news_blob(item)
    if not blob.strip():
        return 0.0
    # 金额词须独立匹配，避免「3500亿元」误中「500亿」
    if any(_standalone_kw(blob, kw) for kw in MARKET_RESCUE_STRONG_KEYWORDS):
        return 120.0
    hits = sum(1 for kw in MARKET_RESCUE_KEYWORDS if _standalone_kw(blob, kw))
    if hits <= 0:
        return 0.0
    return min(40.0 + hits * 12.0, 100.0)


def _standalone_kw(blob: str, kw: str) -> bool:
    """关键词命中；纯数字金额禁止被更长数字吞掉。"""
    if kw not in blob:
        return False
    if kw.endswith("亿") or kw.endswith("亿元"):
        # 禁止 3500亿 命中 500亿
        return re.search(rf"(?<!\d){re.escape(kw)}", blob) is not None
    return True


def is_market_rescue_news(item: dict[str, Any] | MacroNewsItem) -> bool:
    blob = market_rescue_news_blob(item)
    return any(_standalone_kw(blob, kw) for kw in MARKET_RESCUE_KEYWORDS)


def is_session_theme_news(item: dict[str, Any] | MacroNewsItem) -> bool:
    blob = market_rescue_news_blob(item)
    return any(kw in blob for kw in SESSION_THEME_KEYWORDS)


def session_theme_attention_boost(item: dict[str, Any] | MacroNewsItem) -> float:
    """当日盘面主线加分：跨日旧稿不加分（防昨日深V粘住）。"""
    blob = market_rescue_news_blob(item)
    if not blob.strip():
        return 0.0
    if isinstance(item, dict):
        day = _item_calendar_date(item)
        if day is not None and day != datetime.now(TZ).date():
            return 0.0
    if any(kw in blob for kw in SESSION_THEME_STRONG_KEYWORDS):
        return 135.0
    hits = sum(1 for kw in SESSION_THEME_KEYWORDS if kw in blob)
    if hits <= 0:
        return 0.0
    return min(50.0 + hits * 15.0, 110.0)


def classify_category(title: str, summary: str) -> NewsCategory:
    blob = f"{title} {summary}"
    if is_market_rescue_news({"title": title, "summary": summary}):
        return "domestic"
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


def _normalize_href(href: str) -> str:
    href = (href or "").strip()
    if href.startswith("//"):
        return f"https:{href}"
    return href


def news_item_has_stock_signal(item: dict[str, Any]) -> bool:
    """标题/摘要是否含 A 股代码或典型个股/公司关键词。"""
    blob = f"{item.get('title') or ''} {item.get('summary') or ''}"
    if _STOCK_CODE_RE.search(blob):
        return True
    return any(kw in blob for kw in _STOCK_NEWS_KEYWORDS)


def _attention_score(
    item: dict[str, Any],
    engagement: dict[str, dict[str, int]] | None,
) -> float:
    href = _normalize_href(str(item.get("href") or ""))
    eng = (engagement or {}).get(href) or {}
    comment = int(eng.get("comment") or item.get("comment") or 0)
    read = int(eng.get("read") or item.get("read") or 0)
    if comment or read:
        return float(comment * 100 + read)

    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")
    blob = f"{title} {summary}"
    theme = {
        "title": title,
        "summary": summary,
    }
    session = session_theme_attention_boost(theme)
    rescue = market_rescue_attention_boost(theme)
    priority = max(session, rescue)
    if priority > 0:
        return priority + min(len(summary), 120) / 40.0
    heat = sum(1 for kw in GEOPOLITICS_KEYWORDS if kw in blob)
    return float(heat * 5 + min(len(summary), 120) / 40.0)


def load_market_rescue_news_items(
    *,
    hours: int = 72,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """近 hours 内稳市/国家队要闻；供 attention 池强制注入（避免被当日快讯量挤出）。"""
    return _load_keyword_news_items(
        hours=hours,
        limit=limit,
        predicate=is_market_rescue_news,
    )


def load_session_theme_news_items(
    *,
    hours: int = 36,
    limit: int = 8,
    same_day_only: bool = True,
) -> list[dict[str, Any]]:
    """盘面主线注入：默认仅**当日**，避免昨日深V/科创稿跨日粘住高分。"""
    items = _load_keyword_news_items(
        hours=hours,
        limit=max(limit * 3, 20),
        predicate=is_session_theme_news,
    )
    if not same_day_only:
        return items[:limit]
    today = datetime.now(TZ).date()
    out: list[dict[str, Any]] = []
    for item in items:
        if _item_calendar_date(item) == today:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def _item_calendar_date(item: dict[str, Any]) -> date | None:
    """快讯所属日历日：优先 published_at，其次 last_seen_at。"""
    for key in ("published_at", "last_seen_at", "fetched_at"):
        raw = str(item.get(key) or "").strip()
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TZ).date()
        except ValueError:
            try:
                return datetime.strptime(raw[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
    return None


def _load_keyword_news_items(
    *,
    hours: int,
    limit: int,
    predicate,
) -> list[dict[str, Any]]:
    engine = get_engine()
    if engine is None or limit <= 0:
        return []

    since = (datetime.now(TZ) - timedelta(hours=hours)).replace(tzinfo=None)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT href, title, summary, news_time, published_at, category, sentiment, source,
                           fetched_at, last_seen_at
                    FROM macro_news_items
                    WHERE last_seen_at >= :since
                    ORDER BY last_seen_at DESC
                    LIMIT 300
                    """
                ),
                {"since": since},
            ).fetchall()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "href": row.href,
            "title": row.title,
            "summary": row.summary or "",
            "news_time": row.news_time or "",
            "published_at": row.published_at.isoformat(sep=" ", timespec="seconds")
            if row.published_at
            else None,
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
        if predicate(item):
            out.append(item)
        if len(out) >= limit:
            break
    return out


def _merge_pool_unique(
    primary: list[dict[str, Any]],
    extra: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen = {_normalize_href(str(x.get("href") or "")) for x in primary}
    merged = list(primary)
    for item in extra:
        href = _normalize_href(str(item.get("href") or ""))
        if not href or href in seen:
            continue
        seen.add(href)
        merged.append(item)
    return merged


def load_news_pool_for_attention(
    *,
    hours: int = 36,
    limit: int = 80,
) -> list[dict[str, Any]]:
    """合并当日库内快讯与近 hours 小时滚动池。"""
    today = datetime.now(TZ).date()
    rows = list_news_items(day=today, limit=limit)
    if len(rows) < limit // 2:
        seen = {_normalize_href(str(r.get("href") or "")) for r in rows}
        for item in load_recent_news(hours=hours, limit=limit):
            href = _normalize_href(item.href)
            if href in seen:
                continue
            rows.append(
                {
                    "href": href,
                    "title": item.title,
                    "summary": item.summary or "",
                    "news_time": item.time or "",
                    "category": classify_category(item.title, item.summary),
                    "sentiment": "neutral",
                }
            )
            seen.add(href)
    rescue = load_market_rescue_news_items(hours=max(hours, 72), limit=5)
    session = load_session_theme_news_items(hours=max(hours, 36), limit=8)
    pinned = _merge_pool_unique(session, rescue)
    rows = _merge_pool_unique(rows, pinned)
    must_hrefs = {_normalize_href(str(x.get("href") or "")) for x in pinned}
    must = [x for x in rows if _normalize_href(str(x.get("href") or "")) in must_hrefs]
    rest = [x for x in rows if _normalize_href(str(x.get("href") or "")) not in must_hrefs]
    cap_rest = max(0, limit - len(must))
    return must + rest[:cap_rest]


def _enrich_news_pick(
    item: dict[str, Any],
    *,
    engagement: dict[str, dict[str, int]] | None,
) -> dict[str, Any]:
    href = _normalize_href(str(item.get("href") or ""))
    eng = (engagement or {}).get(href) or {}
    enriched = dict(item)
    enriched["comment"] = int(eng.get("comment") or item.get("comment") or 0)
    enriched["read"] = int(eng.get("read") or item.get("read") or 0)
    enriched["attention_score"] = _attention_score(item, engagement)
    enriched["has_stock_signal"] = news_item_has_stock_signal(item)
    return enriched


def pick_top_news_by_attention(
    *,
    limit: int = 10,
    pool_limit: int = 80,
    hours: int = 36,
    engagement: dict[str, dict[str, int]] | None = None,
    prefer_stock: bool = False,
) -> list[dict[str, Any]]:
    """按评论/阅读互动排序，取 top N。prefer_stock 时个股相关快讯优先入榜。"""
    pool = load_news_pool_for_attention(hours=hours, limit=pool_limit)
    if not pool:
        return []

    def sort_key(it: dict[str, Any]) -> tuple[float, str]:
        base = _attention_score(it, engagement)
        if prefer_stock and news_item_has_stock_signal(it):
            base += 80.0
        return (base, str(it.get("published_at") or it.get("last_seen_at") or ""))

    ranked = sorted(pool, key=sort_key, reverse=True)

    def append_unique(
        dest: list[dict[str, Any]],
        seen: set[str],
        candidates: list[dict[str, Any]],
        *,
        cap: int,
    ) -> None:
        for item in candidates:
            if len(dest) >= cap:
                return
            href = _normalize_href(str(item.get("href") or ""))
            if not href or href in seen:
                continue
            seen.add(href)
            dest.append(_enrich_news_pick(item, engagement=engagement))

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    if prefer_stock:
        stock_ranked = [it for it in ranked if news_item_has_stock_signal(it)]
        other_ranked = [it for it in ranked if not news_item_has_stock_signal(it)]
        append_unique(out, seen, stock_ranked, cap=limit)
        append_unique(out, seen, other_ranked, cap=limit)
    else:
        append_unique(out, seen, ranked, cap=limit)

    return out
