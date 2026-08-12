from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import text

from .models import NewsEvent

OVERSEAS_SUBJECTS = (
    "CoreWeave", "Nebius", "Supermicro", "超微电脑", "英伟达", "NVIDIA",
    "三星电子", "SK海力士", "Samsung", "SK Hynix", "东京电子", "爱德万测试",
    "迪斯科", "发那科", "安川电机",
)
NEGATIVE_WORDS = ("立案", "造假", "退市", "终止", "流失", "减值", "违约", "事故", "禁止", "下调")
POSITIVE_WORDS = ("增长", "上调", "中标", "订单", "回购", "增持", "突破", "涨超", "扩产", "资本开支")


@dataclass(frozen=True)
class NewsCoverage:
    events: tuple[NewsEvent, ...]
    providers_ok: tuple[str, ...]
    missing_scopes: tuple[str, ...]
    fetched_at: datetime


def _value(record: Any, key: str, default=None):
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _event_type(blob: str) -> str:
    checks = (
        ("立案", "investigation"), ("造假", "fraud"), ("退市", "delisting"),
        ("合同终止", "contract_termination"), ("核心客户流失", "customer_loss"),
        ("减值", "impairment"), ("违约", "default"), ("事故", "safety_incident"),
        ("资本开支", "capex"), ("财报", "earnings"), ("订单", "order"), ("政策", "policy"),
    )
    return next((kind for keyword, kind in checks if keyword in blob), "market_news")


def normalize_news_record(record: Any, *, observed_at: datetime) -> NewsEvent | None:
    if str(_value(record, "source", "") or "") == "news-impact-json":
        return None
    title = str(_value(record, "title", "") or "").strip()
    summary = str(_value(record, "summary", "") or "").strip()
    href = str(_value(record, "href", _value(record, "source_url", "")) or "").strip()
    published = _value(record, "published_at")
    if not title or not href or not isinstance(published, datetime):
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=observed_at.tzinfo)
    blob = f"{title} {summary}"
    subjects = tuple(subject for subject in OVERSEAS_SUBJECTS if subject.lower() in blob.lower())
    overseas = bool(subjects) or any(word in blob for word in ("美股", "韩国", "日本股市", "日股"))
    scope = "overseas" if overseas else ("policy" if "政策" in blob else "a_share")
    confirmation = "premarket" if "盘前" in blob else ("intraday" if "盘中" in blob else "official")
    direction = "negative" if any(word in blob for word in NEGATIVE_WORDS) else ("positive" if any(word in blob for word in POSITIVE_WORDS) else "neutral")
    source_name = str(_value(record, "source", _value(record, "source_name", "")) or "未知来源")
    tier = "official" if any(word in source_name for word in ("公司", "交易所", "监管", "官网")) else "media"
    digest = hashlib.sha256(f"{title}|{published.isoformat()}".encode()).hexdigest()[:20]
    return NewsEvent(
        event_id=str(_value(record, "event_id", "") or digest),
        title=title,
        summary=summary,
        published_at=published,
        observed_at=observed_at,
        source_url=href,
        source_name=source_name,
        source_tier=tier,
        market="US" if overseas else "CN",
        country="overseas" if overseas else "CN",
        subjects=subjects,
        event_type=_event_type(blob),
        direction=direction,
        confirmation_state=confirmation,
        scope=scope,
        evidence=summary or title,
    )


def load_news_coverage(*, engine=None, now: datetime, hours: int = 168) -> NewsCoverage:
    if engine is None:
        from scripts.tools.portfolio_db import get_engine
        engine = get_engine()
    if engine is None:
        return NewsCoverage((), (), ("macro_news", "overseas_company"), now)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT href, title, summary, published_at, source
                FROM macro_news_items
                WHERE published_at >= :since
                ORDER BY published_at DESC
            """), {"since": now.replace(tzinfo=None) - timedelta(hours=hours)}).mappings().all()
    except Exception:
        rows = []
    events = [event for row in rows if (event := normalize_news_record(row, observed_at=now)) is not None]
    try:
        from scripts.tools.news_impact_db import load_cached_events
        events.extend(load_cached_events(since=now - timedelta(hours=hours), engine=engine))
    except Exception:
        pass
    by_id = {event.event_id: event for event in events}
    events_tuple = tuple(sorted(by_id.values(), key=lambda item: item.published_at, reverse=True))
    missing = () if any(event.scope == "overseas" for event in events_tuple) else ("overseas_company",)
    providers = ("macro_news", "verified_cache") if events_tuple else ()
    return NewsCoverage(events_tuple, providers, missing, now)
