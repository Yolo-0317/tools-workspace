from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module

import pytest

from stock_ai.buy_point_selection.five_day_return_profiles import (
    build_five_day_return_profiles,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
)
from stock_ai.buy_point_selection.models import DetectedSetup, SetupType


START = date(2023, 1, 2)


def _plan(
    *,
    market_status: str,
    sector_resonating: bool | None,
    resistance_basis: str,
) -> FiveDaySignalPlan:
    profile = build_five_day_return_profiles()[0]
    setup = DetectedSetup(
        code="600001",
        setup_type=SetupType.PRE_BREAKOUT,
        analysis_date=START,
        structure_start=START - timedelta(days=10),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.50"),
        quality=Decimal("0.80"),
        reasons=("FIXTURE",),
        metrics={},
    )
    candidate = FiveDaySignalCandidate(
        code="600001",
        signal_date=START,
        setup=setup,
        market_status=market_status,
        sector_code="801010",
        sector_resonating=sector_resonating,
        anti_chase_passed=True,
        average_amount5_qian=Decimal("200000"),
        valid_through_trade_date=START + timedelta(days=2),
    )
    return FiveDaySignalPlan(
        candidate=candidate,
        profile=profile,
        structure_id=f"600001-{profile.profile_id}",
        signal_close=Decimal("10.00"),
        breakout_trigger=Decimal("10.01"),
        structure_stop=Decimal("9.50"),
        reference_entry=Decimal("10.01"),
        resistance_basis=resistance_basis,
        resistance_effective_r=None,
    )


def test_v2_registry_contains_exactly_the_preregistered_twelve() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    policies = ranking_v2.build_five_day_v2_policies()

    assert tuple(value.policy_id for value in policies) == (
        "EDGE-K30-BASE",
        "EDGE-K30-STABLE_NEGATIVE",
        "EDGE-K60-BASE",
        "EDGE-K60-STABLE_NEGATIVE",
        "BALANCED-K30-BASE",
        "BALANCED-K30-STABLE_NEGATIVE",
        "BALANCED-K60-BASE",
        "BALANCED-K60-STABLE_NEGATIVE",
        "DOWNSIDE-K30-BASE",
        "DOWNSIDE-K30-STABLE_NEGATIVE",
        "DOWNSIDE-K60-BASE",
        "DOWNSIDE-K60-STABLE_NEGATIVE",
    )
    assert all(sum(value.weights.as_tuple()) == 100 for value in policies)
    hashes = {
        ranking_v2.five_day_v2_policy_hash(value) for value in policies
    }
    assert len(hashes) == 12
    assert all(len(value) == 64 for value in hashes)
    assert len(ranking_v2.five_day_v2_policy_set_hash()) == 64


def test_v2_policy_types_reject_nonpreregistered_parameters() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    weights = ranking_v2.V2Weights(35, 20, 15, 10, 10, 5, 5)

    with pytest.raises(ValueError, match="weights must sum to 100"):
        ranking_v2.V2Weights(34, 20, 15, 10, 10, 5, 5)
    with pytest.raises(ValueError, match="shrinkage_k must be 30 or 60"):
        ranking_v2.FiveDayV2Policy(
            policy_id="EDGE-K10-BASE",
            ranking_version=ranking_v2.V2_RANKING_VERSION,
            shrinkage_k=10,
            gate_mode="BASE",
            weights=weights,
        )
    with pytest.raises(ValueError, match="unsupported gate mode"):
        ranking_v2.FiveDayV2Policy(
            policy_id="EDGE-K30-UNKNOWN",
            ranking_version=ranking_v2.V2_RANKING_VERSION,
            shrinkage_k=30,
            gate_mode="UNKNOWN",
            weights=weights,
        )


def test_shrinkage_has_literal_boundary_and_rejects_invalid_inputs() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    assert ranking_v2.shrink_five_day_edge(
        Decimal("0.02"),
        30,
        30,
    ) == Decimal("0.01")
    with pytest.raises(ValueError, match="invalid shrinkage inputs"):
        ranking_v2.shrink_five_day_edge(Decimal("0.02"), -1, 30)
    with pytest.raises(ValueError, match="invalid shrinkage inputs"):
        ranking_v2.shrink_five_day_edge(Decimal("0.02"), 30, 0)


def test_relative_percentiles_preserve_ties_direction_and_boundaries() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    assert ranking_v2.relative_percentiles(
        (Decimal("1"), Decimal("2"), Decimal("2"), Decimal("4")),
        higher_is_better=True,
    ) == (
        Decimal("0"),
        Decimal("0.5"),
        Decimal("0.5"),
        Decimal("1"),
    )
    assert ranking_v2.relative_percentiles(
        (Decimal("1"), Decimal("2"), Decimal("4")),
        higher_is_better=False,
    ) == (Decimal("1"), Decimal("0.5"), Decimal("0"))
    assert ranking_v2.relative_percentiles(
        (Decimal("7"),),
        higher_is_better=False,
    ) == (Decimal("0.5"),)
    with pytest.raises(ValueError, match="percentile input must not be empty"):
        ranking_v2.relative_percentiles((), higher_is_better=True)


def test_context_score_uses_only_the_three_literal_signal_time_inputs() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    best = _plan(
        market_status="ALLOW",
        sector_resonating=True,
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
    )
    middle = _plan(
        market_status="LIMITED",
        sector_resonating=None,
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
    )
    worst = _plan(
        market_status="LIMITED",
        sector_resonating=False,
        resistance_basis="LEVEL_BELOW_2R",
    )

    assert ranking_v2.five_day_v2_context_score(best) == Decimal("1")
    assert ranking_v2.five_day_v2_context_score(middle) == Decimal("0.5")
    assert ranking_v2.five_day_v2_context_score(worst) == Decimal("0")
