"""Deterministic attribution of limit-up stocks to persisted selection lanes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any, Callable, Literal, Mapping, Sequence

from .models import SelectionAttribution
from stock_ai.limit_up_gene_watch import PRECISION_POLICY
from stock_ai.limit_up_logic import LimitUpResult


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


def explain_limit_up_gene_result(
    result: LimitUpResult,
    *,
    amount_wan: float,
    base_filter_passed: bool,
) -> ExplainResult | None:
    """Explain the precision-policy rejection in deterministic gate order."""
    policy = PRECISION_POLICY
    reasons: list[str] = []
    if not base_filter_passed or amount_wan < policy.min_amount_wan:
        reasons.append("BASE_FILTER_FAILED")
    if result.gene != policy.required_gene:
        reasons.append("GENE_NOT_STRONG")
    if result.recent_limit_up_count < 1:
        reasons.append("NO_RECENT_LIMIT_UP")
    if result.post_limit_support_broken:
        reasons.append("SUPPORT_BROKEN")
    if result.paths.continuation < policy.min_continuation:
        reasons.append("CONTINUATION_TOO_LOW")
    if result.paths.failure > policy.max_failure:
        reasons.append("FAILURE_TOO_HIGH")
    if result.new_risk_forbidden:
        reasons.append("RISK_VETO")
    required = {
        "distance_to_consolidation_high": result.distance_to_consolidation_high,
        "days_since_last_limit_up": result.days_since_last_limit_up,
        "return5": result.return5,
        "distance_from_last_limit_close": result.distance_from_last_limit_close,
    }
    missing = tuple(key.upper() + "_MISSING" for key, value in required.items() if value is None)
    if missing:
        return ExplainResult(
            attribution="DATA_MISSING",
            reason_codes=missing,
            evidence={"missing_fields": [key for key, value in required.items() if value is None]},
            rule_version=STRATEGY_RULE_VERSIONS["limit_up_gene_watch"],
        )
    if result.latest_pct_chg is not None and result.latest_pct_chg > policy.max_signal_pct:
        reasons.append("SIGNAL_DAY_TOO_HOT")
    near_box = (
        result.post_limit_shrink
        and -policy.max_distance_below_box <= float(result.distance_to_consolidation_high) <= 0.01
    )
    if not near_box:
        reasons.append("NOT_NEAR_BOX_CEILING")
    mature = (
        policy.min_days_since_limit_up <= int(result.days_since_last_limit_up) <= policy.max_days_since_limit_up
        and policy.min_return5 <= float(result.return5) <= policy.max_return5
        and abs(float(result.distance_from_last_limit_close)) <= policy.max_abs_distance_from_limit_close
    )
    if not mature:
        reasons.append("NOT_MATURE_CONSOLIDATION")
    if not reasons:
        return None
    return ExplainResult(
        attribution="HARD_REJECTED",
        reason_codes=tuple(reasons),
        evidence={
            "amount_wan": amount_wan,
            "gene": result.gene,
            "continuation": result.paths.continuation,
            "failure": result.paths.failure,
            "latest_pct_chg": result.latest_pct_chg,
            "distance_to_consolidation_high": result.distance_to_consolidation_high,
            "days_since_last_limit_up": result.days_since_last_limit_up,
            "return5": result.return5,
            "distance_from_last_limit_close": result.distance_from_last_limit_close,
        },
        rule_version=STRATEGY_RULE_VERSIONS["limit_up_gene_watch"],
    )


def _code(row: Mapping[str, Any]) -> str:
    return str(row.get("代码") or row.get("ts_code") or "").split(".")[0].zfill(6)


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    return float(value)


def build_selection_attributions(
    *,
    trade_date: date,
    selection_date: date | None = None,
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
                        selection_date,
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
                        selection_date=selection_date,
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
                        selection_date,
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
                    selection_date=selection_date,
                )
            )
    return tuple(resolved)
