from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

SourceTier = Literal["regulatory", "official", "authoritative", "media", "rumor"]
Direction = Literal["positive", "negative", "neutral"]
ConfirmationState = Literal["official", "closed", "premarket", "intraday", "unverified"]
EventScope = Literal["overseas", "policy", "a_share"]


@dataclass(frozen=True)
class NewsEvent:
    event_id: str
    title: str
    summary: str
    published_at: datetime
    observed_at: datetime
    source_url: str
    source_name: str
    source_tier: SourceTier
    market: str
    country: str
    subjects: tuple[str, ...]
    event_type: str
    direction: Direction
    confirmation_state: ConfirmationState
    scope: EventScope
    valid_until: datetime | None = None
    evidence: str = ""


@dataclass(frozen=True)
class StockContext:
    code: str
    name: str
    industry: str = ""
    concepts: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProbabilityPaths:
    strong: int
    neutral: int
    weak: int

    def as_tuple(self) -> tuple[int, int, int]:
        return self.strong, self.neutral, self.weak


@dataclass(frozen=True)
class StockEventImpact:
    event: NewsEvent
    transmission_type: str
    mapped_sectors: tuple[str, ...]
    relevance: str
    confidence: str
    base_score: float
    weighted_score: float
    mapping_evidence: str
    mapping_source: str = "fixed"


@dataclass(frozen=True)
class ProbabilityAdjustment:
    base: ProbabilityPaths
    delta: ProbabilityPaths
    final: ProbabilityPaths


@dataclass(frozen=True)
class VetoDecision:
    new_risk_forbidden: bool = False
    protective_exit_allowed: bool = True
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewsImpactResult:
    stock: StockContext
    score: float
    direction: str
    impacts: tuple[StockEventImpact, ...]
    probability: ProbabilityAdjustment
    veto: VetoDecision
    missing_scopes: tuple[str, ...] = ()
    data_cutoff: datetime | None = None
