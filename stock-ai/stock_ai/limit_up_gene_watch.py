"""Pure eligibility policy for the full-market limit-up-gene shadow lane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from stock_ai.limit_up_logic import LimitUpResult


WATCH_ACTION = "蓄势观察，等待次日确认"


@dataclass(frozen=True)
class LimitUpGeneWatchPolicy:
    min_amount_wan: float = 5000.0
    min_continuation: int = 45
    max_failure: int = 40
    required_gene: str = "STRONG"
    require_near_box_ceiling: bool = False
    max_distance_below_box: float = 0.05
    max_signal_pct: float = 3.0
    reward_liquidity: bool = False
    require_mature_consolidation: bool = False
    min_days_since_limit_up: int = 8
    max_days_since_limit_up: int = 19
    min_return5: float = -0.08
    max_return5: float = 0.03
    max_abs_distance_from_limit_close: float = 0.08


DEFAULT_POLICY = LimitUpGeneWatchPolicy()
PRECISION_POLICY = LimitUpGeneWatchPolicy(
    require_near_box_ceiling=True,
    reward_liquidity=True,
    require_mature_consolidation=True,
)


@dataclass(frozen=True)
class LimitUpGeneCandidate:
    code: str
    name: str
    score: int
    action: str
    tags: tuple[str, ...]
    missing_fields: tuple[str, ...]
    metrics: Mapping[str, Any]


def evaluate_limit_up_gene_candidate(
    result: LimitUpResult,
    *,
    amount_wan: float,
    base_filter_passed: bool,
    policy: LimitUpGeneWatchPolicy = DEFAULT_POLICY,
) -> LimitUpGeneCandidate | None:
    """Return an observation-only candidate when every hard gate passes."""
    if not base_filter_passed or float(amount_wan) < policy.min_amount_wan:
        return None
    if result.gene != policy.required_gene:
        return None
    if result.recent_limit_up_count < 1:
        return None
    if result.post_limit_support_broken:
        return None
    if result.paths.continuation < policy.min_continuation:
        return None
    if result.paths.failure > policy.max_failure:
        return None
    if result.new_risk_forbidden:
        return None

    near_box_ceiling = (
        result.post_limit_shrink
        and result.distance_to_consolidation_high is not None
        and -policy.max_distance_below_box
        <= result.distance_to_consolidation_high
        <= 0.01
        and (result.latest_pct_chg is None or result.latest_pct_chg <= policy.max_signal_pct)
    )
    if policy.require_near_box_ceiling and not near_box_ceiling:
        return None
    mature_consolidation = (
        result.days_since_last_limit_up is not None
        and policy.min_days_since_limit_up
        <= result.days_since_last_limit_up
        <= policy.max_days_since_limit_up
        and result.return5 is not None
        and policy.min_return5 <= result.return5 <= policy.max_return5
        and result.distance_from_last_limit_close is not None
        and abs(result.distance_from_last_limit_close)
        <= policy.max_abs_distance_from_limit_close
    )
    if policy.require_mature_consolidation and not mature_consolidation:
        return None

    liquidity_bonus = 0
    if policy.reward_liquidity:
        if amount_wan >= 50_000:
            liquidity_bonus = 5
        elif amount_wan >= 20_000:
            liquidity_bonus = 3
        elif amount_wan >= 10_000:
            liquidity_bonus = 1
    score = min(
        100,
        max(
            0,
            int(result.score.total)
            + (10 if near_box_ceiling else 0)
            + liquidity_bonus,
        ),
    )
    tags = ["强涨停基因", "关键支撑未破"]
    if result.post_limit_shrink:
        tags.append("首板后缩量承接")
    if near_box_ceiling:
        tags.append("箱体上沿临界突破")
    metrics: dict[str, Any] = {
        "recent_limit_up_count": result.recent_limit_up_count,
        "continuation": result.paths.continuation,
        "failure": result.paths.failure,
        "amount_wan": float(amount_wan),
        "consolidation_high": result.consolidation_high,
        "distance_to_consolidation_high": result.distance_to_consolidation_high,
        "last_limit_up_low": result.last_limit_up_low,
        "latest_pct_chg": result.latest_pct_chg,
        "box_ceiling_bonus": 10 if near_box_ceiling else 0,
        "liquidity_bonus": liquidity_bonus,
        "days_since_last_limit_up": result.days_since_last_limit_up,
        "return5": result.return5,
        "distance_from_last_limit_close": result.distance_from_last_limit_close,
        "mature_consolidation": mature_consolidation,
    }
    for field in result.missing_fields:
        metrics[field] = None
    return LimitUpGeneCandidate(
        code=result.code,
        name=result.name,
        score=score,
        action=WATCH_ACTION,
        tags=tuple(tags),
        missing_fields=tuple(result.missing_fields),
        metrics=metrics,
    )
