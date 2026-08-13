"""Deterministic Eastmoney limit-up research ledger."""

from .models import (
    ForwardLabel,
    NormalizedSnapshot,
    PoolFact,
    SelectionAttribution,
    normalize_topic_pools,
)
from .attribution import (
    ExplainResult,
    StrategySnapshot,
    build_selection_attributions,
)
from .labels import compute_forward_labels
from .report import build_research_report

__all__ = [
    "ForwardLabel",
    "NormalizedSnapshot",
    "PoolFact",
    "SelectionAttribution",
    "normalize_topic_pools",
    "ExplainResult",
    "StrategySnapshot",
    "build_selection_attributions",
    "compute_forward_labels",
    "build_research_report",
]
