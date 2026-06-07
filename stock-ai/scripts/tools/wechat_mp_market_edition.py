#!/usr/bin/env python3
"""A股评论稿分时段（盘前/午间/盘后）：快讯素材注入，不改 market 三节模板。"""

from __future__ import annotations

import os
import re
from datetime import datetime, time, timedelta
from typing import Any, Literal

from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.news_sentiment import sentiment_label

TZ = ZoneInfo("Asia/Shanghai")

MarketEdition = Literal["pre", "midday", "close"]

_EDITION_ALIASES: dict[str, MarketEdition] = {
    "pre": "pre",
    "premarket": "pre",
    "盘前": "pre",
    "before": "pre",
    "midday": "midday",
    "mid": "midday",
    "noon": "midday",
    "午间": "midday",
    "盘中": "midday",
    "close": "close",
    "eod": "close",
    "post": "close",
    "盘后": "close",
    "收盘": "close",
}

_EDITION_META: dict[MarketEdition, dict[str, Any]] = {
    "pre": {
        "label": "盘前",
        "news_hours": 18,
        "news_limit": 8,
        "pool_limit": 60,
        "writing_hint": (
            "当前为盘前稿：A股尚未开盘或刚临近开盘，基于隔夜与清晨财经消息研判"
            "可能的开局结构与风险偏好；勿写「今日收盘」「全天复盘」，可写「若开盘…」"
            "「隔夜…」「盘前…」。"
        ),
    },
    "midday": {
        "label": "午间",
        "news_hours": 10,
        "news_limit": 8,
        "pool_limit": 60,
        "writing_hint": (
            "当前为午间稿：结合上午已披露的消息与半日交易，可写「上午」「半日」"
            "「午前」；结构判断侧重午后是否延续或分化，勿写成全天收盘总结。"
        ),
    },
    "close": {
        "label": "收盘",
        "news_hours": 36,
        "news_limit": 10,
        "pool_limit": 80,
        "writing_hint": (
            "当前为盘后稿：可写「今日收盘」「全天」；结合全日财经消息做复盘式结构判断。"
        ),
    },
}


def normalize_market_edition(raw: str | None = None) -> MarketEdition:
    if raw is None:
        raw = os.getenv("WECHAT_MP_MARKET_EDITION", "close")
    key = (raw or "close").strip().lower()
    if key in _EDITION_ALIASES:
        return _EDITION_ALIASES[key]
    raise ValueError(f"未知 edition={raw!r}，可选: pre, midday, close")


def edition_label(edition: MarketEdition) -> str:
    return str(_EDITION_META[edition]["label"])


def edition_writing_hint(edition: MarketEdition) -> str:
    return str(_EDITION_META[edition]["writing_hint"])


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _item_reference_dt(item: dict[str, Any], *, now: datetime) -> datetime | None:
    pub = item.get("published_at")
    if pub:
        try:
            dt = datetime.fromisoformat(str(pub)[:19])
            if dt.tzinfo is None:
                return dt.replace(tzinfo=TZ)
            return dt.astimezone(TZ)
        except ValueError:
            pass
    raw = str(item.get("news_time") or "").strip()
    if not raw:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(raw, fmt).time()
            return datetime.combine(now.date(), t, tzinfo=TZ)
        except ValueError:
            continue
    return None


def _edition_window(
    edition: MarketEdition,
    *,
    now: datetime,
) -> tuple[datetime | None, datetime | None]:
    """返回 (start, end) 闭区间过滤；None 表示不限制该端。"""
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    else:
        now = now.astimezone(TZ)
    today = now.date()

    if edition == "pre":
        # 昨夜收盘后 ~ 当前：覆盖隔夜宏观
        start = datetime.combine(today, time(0, 0), tzinfo=TZ) - timedelta(hours=6)
        if now.time() >= time(9, 30):
            start = datetime.combine(today, time(0, 0), tzinfo=TZ)
        return start, now

    if edition == "midday":
        start = datetime.combine(today, time(8, 0), tzinfo=TZ)
        return start, now

    # close：当日为主，池子由 hours 控制
    start = datetime.combine(today, time(0, 0), tzinfo=TZ)
    return start, now


def filter_news_for_edition(
    items: list[dict[str, Any]],
    *,
    edition: MarketEdition,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(TZ)
    start, end = _edition_window(edition, now=now)
    out: list[dict[str, Any]] = []
    for item in items:
        ref = _item_reference_dt(item, now=now)
        if ref is None:
            out.append(item)
            continue
        if start and ref < start:
            continue
        if end and ref > end:
            continue
        out.append(item)
    return out


def load_top_news_for_edition(
    edition: MarketEdition,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    from scripts.tools.wechat_mp_news_article import fetch_news_engagement, load_top_news_items

    now = now or datetime.now(TZ)
    meta = _EDITION_META[edition]
    hours = _env_int(f"WECHAT_MP_MARKET_NEWS_HOURS_{edition.upper()}", int(meta["news_hours"]))
    limit = _env_int(f"WECHAT_MP_MARKET_NEWS_LIMIT_{edition.upper()}", int(meta["news_limit"]))
    pool_limit = _env_int(
        f"WECHAT_MP_MARKET_NEWS_POOL_{edition.upper()}",
        int(meta["pool_limit"]),
    )

    engagement = fetch_news_engagement(limit=pool_limit)
    from scripts.tools.news_db import pick_top_news_by_attention

    pool = pick_top_news_by_attention(
        limit=max(limit * 3, 15),
        pool_limit=pool_limit,
        hours=hours,
        engagement=engagement,
    )
    filtered = filter_news_for_edition(pool, edition=edition, now=now)
    if len(filtered) < max(3, limit // 2):
        filtered = pool[: max(limit * 2, 12)]
    return filtered[:limit]


def format_news_context_blob(items: list[dict[str, Any]]) -> str:
    """供 LLM 参考的快讯素材块（不出现在成稿列表中）。"""
    if not items:
        return "（暂无可用快讯素材；请仅依据盘面与外围数据写作。）"

    lines = [
        "【财经快讯素材 · 仅供写作融合，禁止在正文编号列出】",
        "要求：将下列要点自然写入「外围与资金」「结构判断」，写清事件→传导→板块映射。",
        "",
    ]
    for idx, it in enumerate(items, 1):
        title = re.sub(r"\s+", " ", str(it.get("title") or "")).strip()
        summary = re.sub(r"\s+", " ", str(it.get("summary") or "")).strip()
        when = str(it.get("news_time") or it.get("published_at") or "").strip()[:16]
        sent = sentiment_label(str(it.get("sentiment") or "neutral"))
        blob = summary[:220] + ("…" if len(summary) > 220 else "")
        lines.append(f"素材{idx}｜{when}｜{sent}｜{title}")
        if blob:
            lines.append(f"  摘要：{blob}")
    return "\n".join(lines)


def build_market_news_context(
    edition: MarketEdition,
    *,
    now: datetime | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """返回 (context_blob, raw_items)。"""
    items = load_top_news_for_edition(edition, now=now)
    return format_news_context_blob(items), items
