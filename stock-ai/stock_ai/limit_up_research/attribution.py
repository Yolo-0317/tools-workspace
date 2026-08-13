"""Deterministic attribution of limit-up stocks to persisted selection lanes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any, Callable, Literal, Mapping, Sequence

from .models import SelectionAttribution


AttributionCode = Literal[
    "SELECTED",
    "RANKED_OUT",
    "HARD_REJECTED",
    "DATA_MISSING",
    "EXPLAINER_UNAVAILABLE",
    "STRATEGY_NOT_RUN",
]

STRATEGY_RULE_VERSIONS: dict[str, str] = {
    "short_term_trade": "short-term-selection-2.1.0",
    "combined": "combined-current",
    "five_factor": "five-factor-current",
    "ma5": "ma5-current",
    "watch": "watch-current",
    "bottom_breakout": "bottom-breakout-current",
    "limit_up_gene_watch": "limit-up-gene-watch-1.0.0",
}


@dataclass(frozen=True)
class StrategySnapshot:
    ran: bool
    rows: tuple[Mapping[str, Any], ...]
    retained_limit: int | None = None


@dataclass(frozen=True)
class ExplainResult:
    attribution: Literal["HARD_REJECTED", "DATA_MISSING"]
    reason_codes: tuple[str, ...]
    evidence: Mapping[str, Any]
    rule_version: str

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError("explain result requires at least one reason code")
        if any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", code) for code in self.reason_codes):
            raise ValueError("reason codes must be stable uppercase identifiers")


Explainer = Callable[[str], ExplainResult]


def _code(row: Mapping[str, Any]) -> str:
    return str(row.get("代码") or row.get("ts_code") or "").split(".")[0].zfill(6)


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    return float(value)


def build_selection_attributions(
    *,
    trade_date: date,
    limit_up_codes: Sequence[str],
    snapshots: Mapping[str, StrategySnapshot],
    explainers: Mapping[str, Explainer],
) -> tuple[SelectionAttribution, ...]:
    resolved: list[SelectionAttribution] = []
    for strategy, snapshot in snapshots.items():
        version = STRATEGY_RULE_VERSIONS.get(strategy, f"{strategy}-unknown")
        indexed = {_code(row): (rank, row) for rank, row in enumerate(snapshot.rows, 1)}
        for raw_code in limit_up_codes:
            code = str(raw_code).split(".")[0].zfill(6)
            if not snapshot.ran:
                resolved.append(
                    SelectionAttribution(
                        trade_date, code, strategy, False, None, None, None,
                        "STRATEGY_NOT_RUN", "STRATEGY_NOT_RUN", ("STRATEGY_NOT_RUN",), {}, version,
                    )
                )
                continue
            persisted = indexed.get(code)
            if persisted is not None:
                rank, row = persisted
                ranked_out = snapshot.retained_limit is not None and rank > snapshot.retained_limit
                reason_codes = ("BELOW_RETAINED_LIMIT",) if ranked_out else ()
                resolved.append(
                    SelectionAttribution(
                        trade_date=trade_date,
                        code=code,
                        strategy=strategy,
                        selected=not ranked_out,
                        rank_no=rank,
                        score=_optional_float(row.get("总分") or row.get("total_score")),
                        action=str(row.get("建议动作") or row.get("action_hint") or "") or None,
                        attribution="RANKED_OUT" if ranked_out else "SELECTED",
                        first_reason_code=reason_codes[0] if reason_codes else None,
                        reason_codes=reason_codes,
                        evidence={"retained_limit": snapshot.retained_limit} if ranked_out else {},
                        rule_version=version,
                    )
                )
                continue
            explainer = explainers.get(strategy)
            if explainer is None:
                resolved.append(
                    SelectionAttribution(
                        trade_date, code, strategy, False, None, None, None,
                        "EXPLAINER_UNAVAILABLE", "EXPLAINER_UNAVAILABLE",
                        ("EXPLAINER_UNAVAILABLE",), {}, version,
                    )
                )
                continue
            explanation = explainer(code)
            resolved.append(
                SelectionAttribution(
                    trade_date=trade_date,
                    code=code,
                    strategy=strategy,
                    selected=False,
                    rank_no=None,
                    score=None,
                    action=None,
                    attribution=explanation.attribution,
                    first_reason_code=explanation.reason_codes[0],
                    reason_codes=explanation.reason_codes,
                    evidence=dict(explanation.evidence),
                    rule_version=explanation.rule_version,
                )
            )
    return tuple(resolved)
