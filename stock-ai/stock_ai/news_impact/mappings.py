from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .models import NewsEvent, StockContext, StockEventImpact

CONFIG_PATH = Path(__file__).with_name("industry_mappings.json")
NEGATIVE_TYPES = {"investigation", "fraud", "delisting", "contract_termination", "customer_loss", "impairment", "default", "safety_incident", "business_ban"}


@dataclass(frozen=True)
class MappedStock:
    code: str
    name: str
    theme: str
    sectors: tuple[str, ...]


def load_fixed_mappings() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def infer_event_themes(event: NewsEvent) -> list[tuple[str, dict]]:
    blob = " ".join((event.title, event.summary, *event.subjects)).lower()
    matches = []
    for theme, rule in load_fixed_mappings().items():
        tokens = [*rule.get("subjects", []), *rule.get("keywords", [])]
        if any(token.lower() in blob for token in tokens):
            matches.append((theme, rule))
    return matches


def iter_event_mapped_stocks(event: NewsEvent) -> tuple[MappedStock, ...]:
    """Return only explicitly reviewed code/name pairs from matching rules."""
    by_code: dict[str, MappedStock] = {}
    for theme, rule in infer_event_themes(event):
        values = tuple(str(value).strip() for value in rule.get("stocks", ()))
        for index in range(0, len(values) - 1, 2):
            code, name = values[index], values[index + 1]
            if not re.fullmatch(r"\d{6}", code) or re.fullmatch(r"\d{6}", name):
                continue
            by_code.setdefault(
                code,
                MappedStock(
                    code=code,
                    name=name,
                    theme=theme,
                    sectors=tuple(rule.get("sectors", ())),
                ),
            )
    return tuple(by_code.values())


def map_event_to_stock(event: NewsEvent, stock: StockContext) -> StockEventImpact | None:
    if stock.name in event.subjects or stock.code in event.subjects:
        relevance = "high"
        transmission = "direct"
        sectors = (stock.industry,) if stock.industry else ()
        evidence = "事件主体与目标公司一致"
        base = 8.0
    else:
        themes = infer_event_themes(event)
        stock_blob = " ".join((stock.industry, *stock.concepts)).lower()
        matched = [
            (name, rule)
            for name, rule in themes
            if any(sector.lower() in stock_blob for sector in rule.get("sectors", []))
            or stock.code in rule.get("stocks", [])
            or stock.name in rule.get("stocks", [])
        ]
        if not matched:
            return None
        sectors = tuple(dict.fromkeys(sector for _, rule in matched for sector in rule.get("sectors", [])))
        relevance = "medium"
        transmission = "macro_policy" if event.scope == "policy" else "demand_validation"
        evidence = f"事件验证{','.join(sectors)}需求；无目标公司供货关系证据"
        base = 2.0 if event.scope == "policy" else 4.0
    if event.direction == "negative":
        base = -abs(base)
    elif event.direction == "neutral":
        base = 0.0
    return StockEventImpact(event, transmission, sectors, relevance, "high", base, 0.0, evidence)
