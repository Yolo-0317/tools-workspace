from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.case_review import CaseOutcome
from stock_ai.buy_point_selection.models import BuyPointBar, DetectedSetup, SetupType
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ExactRecallComparison,
    ThresholdProfileMetrics,
    ThresholdShadowOutcome,
    aggregate_profile_metrics,
    compare_exact_recall,
    evaluate_threshold_outcomes,
    freeze_threshold_profiles,
    select_frozen_daily_candidates,
)
from stock_ai.buy_point_selection.threshold_shadow_research import (
    ThresholdShadowCandidate,
    ThresholdShadowSetup,
    build_threshold_profiles,
    profile_matrix_hash,
)


SIGNAL = date(2026, 7, 20)


def _candidate(
    *,
    code: str = "600001",
    signal_date: date = SIGNAL,
    profile_index: int = 0,
) -> ThresholdShadowCandidate:
    profile = build_threshold_profiles()[profile_index]
    setup = DetectedSetup(
        code,
        profile.setup_type,
        signal_date,
        signal_date - timedelta(days=20),
        Decimal("9.99"),
        Decimal("9.00"),
        Decimal("0.80"),
        ("SHADOW_FIXTURE",),
        {},
    )
    shadow = ThresholdShadowSetup(
        code,
        signal_date,
        profile,
        setup,
        Decimal("0.05"),
    )
    plan = PricePlan(
        f"structure-{code}-{profile.profile_id}",
        code,
        SetupType.PRE_BREAKOUT,
        signal_date,
        Decimal("10.00"),
        Decimal("10.00"),
        Decimal("9.00"),
        Decimal("20.00"),
        Decimal("1.00"),
        Decimal("10.00"),
        100,
        signal_date + timedelta(days=2),
    )
    return ThresholdShadowCandidate(
        code,
        signal_date,
        profile.profile_id,
        shadow,
        plan,
        Decimal("200000"),
        Decimal("2.00"),
    )


def _time_exit_bars(signal_date: date = SIGNAL) -> tuple[BuyPointBar, ...]:
    return tuple(
        BuyPointBar(
            signal_date + timedelta(days=index),
            Decimal("10.00"),
            Decimal("10.60"),
            Decimal("9.50"),
            Decimal("10.50"),
            Decimal("1"),
            Decimal("200000"),
        )
        for index in range(1, 6)
    )


def test_outcome_wrapper_preserves_profile_and_cost_adjusted_return() -> None:
    """Catches profile identity or transaction costs being lost in evaluation."""
    candidate = _candidate()

    row = evaluate_threshold_outcomes(
        (candidate,),
        {candidate.code: _time_exit_bars()},
        outcome_cutoff=SIGNAL + timedelta(days=5),
    )[0]

    assert row.profile_id == candidate.profile_id
    assert row.code == "600001"
    assert row.outcome.net_return == Decimal(
        "0.03668096421471172962226640159"
    )
    assert row.executable_shares == 0


def _resolved_outcome(
    profile_id: str,
    index: int,
    net_return: str,
    *,
    stop_first: bool = False,
) -> ThresholdShadowOutcome:
    code = f"600{index:03d}"
    return ThresholdShadowOutcome(
        profile_id,
        code,
        SIGNAL,
        CaseOutcome(
            code,
            SIGNAL,
            "THRESHOLD_SHADOW",
            "CLOSED",
            Decimal("0.04"),
            Decimal("0.02"),
            SIGNAL + timedelta(days=1),
            Decimal("10"),
            Decimal(net_return),
            Decimal(net_return),
            stop_first,
            False,
            f"structure-{index}",
        ),
    )


def test_profile_qualifies_at_exact_precision_boundaries() -> None:
    """Catches inclusive win-rate or stop-rate boundaries drifting."""
    profile_id = build_threshold_profiles()[0].profile_id
    outcomes = tuple(
        _resolved_outcome(
            profile_id,
            index,
            "0.02" if index < 5 else "-0.01",
            stop_first=index < 4,
        )
        for index in range(10)
    )

    metrics = aggregate_profile_metrics((profile_id,) * 10, outcomes)[0]

    assert metrics.candidate_count == 10
    assert metrics.triggered == 10
    assert metrics.resolved == 10
    assert metrics.mean_net_return == Decimal("0.005")
    assert metrics.median_net_return == Decimal("0.005")
    assert metrics.positive_net_rate == Decimal("0.5")
    assert metrics.stop_first_rate == Decimal("0.4")
    assert metrics.qualifies
    assert metrics.qualification_reasons == ()


@pytest.mark.parametrize(
    ("outcomes", "reason"),
    (
        (
            tuple(
                _resolved_outcome("PROFILE", index, "0.01")
                for index in range(9)
            ),
            "MINIMUM_RESOLVED_TRIGGERED",
        ),
        (
            tuple(
                _resolved_outcome(
                    "PROFILE", index, "0.01" if index < 5 else "-0.01"
                )
                for index in range(10)
            ),
            "MEAN_NET_RETURN_NOT_POSITIVE",
        ),
        (
            tuple(
                _resolved_outcome(
                    "PROFILE", index, "0.10" if index < 4 else "-0.01"
                )
                for index in range(10)
            ),
            "POSITIVE_NET_RATE_BELOW_HALF",
        ),
        (
            tuple(
                _resolved_outcome(
                    "PROFILE", index, "0.01", stop_first=index < 5
                )
                for index in range(10)
            ),
            "STOP_FIRST_RATE_ABOVE_40_PERCENT",
        ),
    ),
)
def test_profile_qualification_reasons_are_explicit(
    outcomes: tuple[ThresholdShadowOutcome, ...],
    reason: str,
) -> None:
    """Catches a precision failure being silently admitted to freeze."""
    metrics = aggregate_profile_metrics(
        ("PROFILE",) * len(outcomes), outcomes
    )[0]

    assert not metrics.qualifies
    assert reason in metrics.qualification_reasons


def _qualifying_metrics(
    profile_id: str,
    *,
    mean_net_return: str,
) -> ThresholdProfileMetrics:
    return ThresholdProfileMetrics(
        profile_id,
        12,
        10,
        10,
        6,
        3,
        Decimal(mean_net_return),
        Decimal("0.01"),
        Decimal("0.60"),
        Decimal("0.30"),
        Decimal("0.06"),
        Decimal("0.02"),
        True,
        (),
    )


def test_freeze_ranks_only_qualified_profiles_and_blocks_promotion() -> None:
    """Catches weak profiles entering the immutable holdout configuration."""
    profiles = build_threshold_profiles()
    slower = _qualifying_metrics(
        profiles[0].profile_id, mean_net_return="0.01"
    )
    better = _qualifying_metrics(
        profiles[1].profile_id, mean_net_return="0.02"
    )
    failed = replace(
        _qualifying_metrics(profiles[2].profile_id, mean_net_return="0.03"),
        qualifies=False,
        qualification_reasons=("STOP_FIRST_RATE_ABOVE_40_PERCENT",),
    )

    freeze = freeze_threshold_profiles(
        profiles=profiles,
        training_identities=("research-b", "research-a"),
        metrics=(slower, better, failed),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=profile_matrix_hash(profiles),
        risk_coverage_complete=False,
    )

    assert freeze.training_identities == ("research-a", "research-b")
    assert [(value.profile_id, value.rank) for value in freeze.profiles] == [
        (better.profile_id, 1),
        (slower.profile_id, 2),
    ]
    assert not freeze.empty
    assert not freeze.promotion_eligible
    assert len(freeze.freeze_hash) == 64


def test_freeze_rejects_bad_lineage_and_can_be_explicitly_empty() -> None:
    """Catches duplicate training evidence or threshold lowering to avoid emptiness."""
    profiles = build_threshold_profiles()
    failed = replace(
        _qualifying_metrics(profiles[0].profile_id, mean_net_return="0.01"),
        qualifies=False,
        qualification_reasons=("MINIMUM_RESOLVED_TRIGGERED",),
    )
    kwargs = {
        "profiles": profiles,
        "metrics": (failed,),
        "formal_rule_version": "buy-point-selection-3.1.0",
        "formal_policy_hash": "policy-hash",
        "profile_matrix_hash": profile_matrix_hash(profiles),
        "risk_coverage_complete": True,
    }

    with pytest.raises(ValueError, match="two distinct research identities"):
        freeze_threshold_profiles(
            training_identities=("same", "same"),
            **kwargs,
        )

    freeze = freeze_threshold_profiles(
        training_identities=("first", "second"),
        **kwargs,
    )

    assert freeze.profiles == ()
    assert freeze.empty
    assert not freeze.promotion_eligible


def test_frozen_selection_deduplicates_filters_and_caps_daily_candidates() -> None:
    """Catches profile rank overriding dedupe or a daily basket exceeding five."""
    profiles = build_threshold_profiles()
    freeze = freeze_threshold_profiles(
        profiles=profiles,
        training_identities=("first", "second"),
        metrics=(
            _qualifying_metrics(profiles[0].profile_id, mean_net_return="0.01"),
            _qualifying_metrics(profiles[1].profile_id, mean_net_return="0.02"),
        ),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=profile_matrix_hash(profiles),
        risk_coverage_complete=True,
    )
    candidates = (
        _candidate(code="600001", profile_index=0),
        _candidate(code="600001", profile_index=1),
        _candidate(code="600002", profile_index=1),
        _candidate(code="600003", profile_index=1),
        _candidate(code="600004", profile_index=0),
        _candidate(code="600005", profile_index=0),
        _candidate(code="600006", profile_index=0),
        _candidate(code="600007", profile_index=0),
        _candidate(code="600008", profile_index=2),
    )

    selected = select_frozen_daily_candidates(candidates, freeze)

    assert [value.code for value in selected] == [
        "600002",
        "600003",
        "600001",
        "600004",
        "600005",
    ]
    assert selected[2].profile_id == profiles[0].profile_id
    assert len({(value.signal_date, value.code) for value in selected}) == 5
    assert all(value.executable_shares == 0 for value in selected)


def test_empty_freeze_selects_nothing_and_exact_recall_uses_date_code_keys() -> None:
    """Catches backfilling or cross-date recall attribution."""
    profiles = build_threshold_profiles()
    failed = replace(
        _qualifying_metrics(profiles[0].profile_id, mean_net_return="0.01"),
        qualifies=False,
        qualification_reasons=("MINIMUM_RESOLVED_TRIGGERED",),
    )
    freeze = freeze_threshold_profiles(
        profiles=profiles,
        training_identities=("first", "second"),
        metrics=(failed,),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=profile_matrix_hash(profiles),
        risk_coverage_complete=True,
    )
    candidate = _candidate()

    assert select_frozen_daily_candidates((candidate,), freeze) == ()
    comparison = compare_exact_recall(
        (candidate,),
        {
            (SIGNAL, "600001"),
            (SIGNAL, "600002"),
            (SIGNAL + timedelta(days=1), "600001"),
        },
        {(SIGNAL, "600002")},
    )
    assert comparison == ExactRecallComparison(3, 1, 1, 1, 0)
