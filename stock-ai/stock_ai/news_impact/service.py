from __future__ import annotations

from dataclasses import replace

from .events import deduplicate_events, filter_fresh_events
from .mappings import map_event_to_stock
from .models import NewsEvent, NewsImpactResult, ProbabilityPaths, StockContext
from .probability import adjust_probabilities
from .scoring import detect_material_negative_veto, score_stock_impacts


def analyze_stock_news_impact(
    stock: StockContext,
    events: list[NewsEvent],
    base_probabilities: ProbabilityPaths,
    *,
    now,
    existing_holding: bool,
) -> NewsImpactResult:
    fresh = deduplicate_events(filter_fresh_events(events, now=now))
    mapped = [impact for event in fresh if (impact := map_event_to_stock(event, stock)) is not None]
    peer_subjects = {
        subject
        for impact in mapped
        if impact.event.scope == "overseas" and impact.transmission_type == "demand_validation"
        for subject in impact.event.subjects
    }
    if len(peer_subjects) >= 2:
        mapped = [
            replace(impact, transmission_type="peer_validation", base_score=5.0,
                    mapping_evidence=impact.mapping_evidence + "；两家以上海外同业共同验证")
            if impact.event.scope == "overseas" and impact.transmission_type == "demand_validation"
            else impact
            for impact in mapped
        ]
    score, impacts = score_stock_impacts(mapped)
    probability = adjust_probabilities(base_probabilities, score)
    veto = detect_material_negative_veto(impacts)
    missing = () if any(event.scope == "overseas" for event in fresh) else ("overseas_company",)
    direction = "中性" if score == 0 else ("偏利好" if score > 0 else "偏利空")
    return NewsImpactResult(stock, score, direction, impacts, probability, veto, missing, now)


def analyze_portfolio_news_impact(
    stocks: list[StockContext],
    events: list[NewsEvent],
    base_probabilities_by_code: dict[str, ProbabilityPaths],
    *,
    now,
) -> dict[str, NewsImpactResult]:
    return {
        stock.code: analyze_stock_news_impact(
            stock,
            events,
            base_probabilities_by_code[stock.code],
            now=now,
            existing_holding=True,
        )
        for stock in stocks
    }
