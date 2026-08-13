from __future__ import annotations

from datetime import datetime, timezone

import pytest

from stock_ai.limit_up_gene_watch import (
    PRECISION_POLICY,
    evaluate_limit_up_gene_candidate,
)
from stock_ai.limit_up_logic import LimitUpPaths, LimitUpResult, LimitUpScoreBreakdown


def limit_result(
    *,
    gene="STRONG",
    continuation=60,
    failure=30,
    risk=False,
    recent_count=1,
    support_broken=False,
    missing=("auction_strength", "seal_quality"),
    distance_to_box_high=None,
    latest_pct_chg=0.2,
    days_since_last_limit_up=17,
    return5=-0.02,
    distance_from_last_limit_close=0.0,
) -> LimitUpResult:
    return LimitUpResult(
        code="600000",
        name="测试股份",
        identity="NORMAL_TREND",
        gene=gene,
        score=LimitUpScoreBreakdown(30, 26, 0, 0),
        paths=LimitUpPaths(10, continuation, failure),
        drivers=("首板后缩量整理，抛压阶段性收敛",),
        prerequisites=("等待次日确认",),
        suppressors=(),
        missing_fields=missing,
        data_cutoff=datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc),
        new_risk_forbidden=risk,
        recent_limit_up_count=recent_count,
        post_limit_support_broken=support_broken,
        post_limit_shrink=True,
        distance_to_consolidation_high=distance_to_box_high,
        latest_pct_chg=latest_pct_chg,
        days_since_last_limit_up=days_since_last_limit_up,
        return5=return5,
        distance_from_last_limit_close=distance_from_last_limit_close,
    )


def test_strong_gene_consolidation_enters_watch_pool() -> None:
    candidate = evaluate_limit_up_gene_candidate(
        limit_result(),
        amount_wan=38_000,
        base_filter_passed=True,
    )

    assert candidate is not None
    assert candidate.action == "蓄势观察，等待次日确认"
    assert candidate.code == "600000"
    assert candidate.score == 56


@pytest.mark.parametrize(
    "changes",
    [
        {"gene": "MEDIUM"},
        {"continuation": 44},
        {"failure": 41},
        {"risk": True},
        {"recent_count": 0},
        {"support_broken": True},
    ],
)
def test_hard_gate_failure_excludes_candidate(changes) -> None:
    assert (
        evaluate_limit_up_gene_candidate(
            limit_result(**changes),
            amount_wan=38_000,
            base_filter_passed=True,
        )
        is None
    )


def test_liquidity_and_base_filter_are_hard_gates() -> None:
    assert evaluate_limit_up_gene_candidate(limit_result(), amount_wan=4_999, base_filter_passed=True) is None
    assert evaluate_limit_up_gene_candidate(limit_result(), amount_wan=38_000, base_filter_passed=False) is None


def test_missing_confirmation_fields_are_disclosed_not_zeroed() -> None:
    candidate = evaluate_limit_up_gene_candidate(
        limit_result(missing=("active_themes", "auction_strength", "seal_quality")),
        amount_wan=38_000,
        base_filter_passed=True,
    )

    assert candidate is not None
    assert candidate.missing_fields == (
        "active_themes",
        "auction_strength",
        "seal_quality",
    )
    assert candidate.metrics["active_themes"] is None


def test_near_box_ceiling_gets_priority_without_becoming_buy_action() -> None:
    candidate = evaluate_limit_up_gene_candidate(
        limit_result(distance_to_box_high=-0.025),
        amount_wan=38_000,
        base_filter_passed=True,
    )

    assert candidate is not None
    assert candidate.score == 66
    assert "箱体上沿临界突破" in candidate.tags
    assert candidate.action == "蓄势观察，等待次日确认"


def test_far_from_box_ceiling_gets_no_priority_bonus() -> None:
    candidate = evaluate_limit_up_gene_candidate(
        limit_result(distance_to_box_high=-0.08),
        amount_wan=38_000,
        base_filter_passed=True,
    )

    assert candidate is not None
    assert candidate.score == 56
    assert "箱体上沿临界突破" not in candidate.tags


def test_precision_policy_requires_near_box_ceiling() -> None:
    assert evaluate_limit_up_gene_candidate(
        limit_result(distance_to_box_high=-0.051),
        amount_wan=38_000,
        base_filter_passed=True,
        policy=PRECISION_POLICY,
    ) is None


def test_precision_policy_rejects_already_accelerated_signal_day() -> None:
    assert evaluate_limit_up_gene_candidate(
        limit_result(distance_to_box_high=-0.02, latest_pct_chg=3.01),
        amount_wan=38_000,
        base_filter_passed=True,
        policy=PRECISION_POLICY,
    ) is None


def test_precision_policy_rewards_executable_liquidity() -> None:
    candidate = evaluate_limit_up_gene_candidate(
        limit_result(distance_to_box_high=-0.02),
        amount_wan=60_000,
        base_filter_passed=True,
        policy=PRECISION_POLICY,
    )

    assert candidate is not None
    assert candidate.score == 71
    assert candidate.metrics["liquidity_bonus"] == 5


def test_precision_policy_requires_mature_second_wave_window() -> None:
    assert evaluate_limit_up_gene_candidate(
        limit_result(distance_to_box_high=-0.02, days_since_last_limit_up=4),
        amount_wan=60_000,
        base_filter_passed=True,
        policy=PRECISION_POLICY,
    ) is None
    assert evaluate_limit_up_gene_candidate(
        limit_result(distance_to_box_high=-0.02, return5=0.04),
        amount_wan=60_000,
        base_filter_passed=True,
        policy=PRECISION_POLICY,
    ) is None
