from __future__ import annotations

from dataclasses import replace

from .models import StockEventImpact, VetoDecision

SOURCE = {"regulatory": 1.0, "official": 1.0, "authoritative": 0.8, "media": 0.5, "rumor": 0.0}
CONFIRMATION = {"official": 1.0, "closed": 1.0, "premarket": 0.5, "intraday": 0.5, "unverified": 0.0}
RELEVANCE = {"high": 1.0, "medium": 0.6, "low": 0.3, "none": 0.0}
MATERIAL_NEGATIVE = {"investigation", "fraud", "delisting", "contract_termination", "customer_loss", "impairment", "default", "safety_incident", "business_ban"}


def weighted_score(impact: StockEventImpact) -> float:
    event = impact.event
    return impact.base_score * SOURCE[event.source_tier] * CONFIRMATION[event.confirmation_state] * RELEVANCE[impact.relevance]


def score_stock_impacts(impacts: list[StockEventImpact]) -> tuple[float, tuple[StockEventImpact, ...]]:
    ranked = sorted(impacts, key=lambda item: abs(weighted_score(item)), reverse=True)
    total = 0.0
    enriched = []
    same_direction_count = {"positive": 0, "negative": 0}
    for impact in ranked:
        raw = weighted_score(impact)
        direction = "positive" if raw >= 0 else "negative"
        decay = 0.7 ** same_direction_count[direction]
        same_direction_count[direction] += 1
        value = raw * decay
        total += value
        enriched.append(replace(impact, weighted_score=round(value, 3)))
    return round(max(-20.0, min(12.0, total)), 3), tuple(enriched)


def detect_material_negative_veto(impacts: tuple[StockEventImpact, ...]) -> VetoDecision:
    reasons = tuple(
        impact.event.title
        for impact in impacts
        if impact.event.direction == "negative"
        and impact.event.event_type in MATERIAL_NEGATIVE
        and impact.event.source_tier in {"regulatory", "official"}
        and impact.event.confirmation_state == "official"
    )
    return VetoDecision(bool(reasons), True, reasons)
