from __future__ import annotations

from datetime import timedelta

from .models import NewsEvent

FRESHNESS = {
    "overseas": timedelta(hours=24),
    "policy": timedelta(days=3),
    "a_share": timedelta(days=7),
}
SOURCE_RANK = {"rumor": 0, "media": 1, "authoritative": 2, "official": 3, "regulatory": 4}


def filter_fresh_events(events: list[NewsEvent], *, now) -> list[NewsEvent]:
    return [
        event
        for event in events
        if now <= (event.valid_until or event.published_at + FRESHNESS[event.scope])
    ]


def deduplicate_events(events: list[NewsEvent]) -> list[NewsEvent]:
    chosen: dict[str, NewsEvent] = {}
    order: list[str] = []
    for event in events:
        key = event.event_id
        if key not in chosen:
            chosen[key] = event
            order.append(key)
        elif SOURCE_RANK[event.source_tier] > SOURCE_RANK[chosen[key].source_tier]:
            chosen[key] = event
    return [chosen[key] for key in order]
