from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.case_review import CaseOutcome
from stock_ai.buy_point_selection.gate_shadow_evaluation import (
    GateProfileMetrics,
    GateShadowOutcome,
    aggregate_gate_profile_metrics,
    evaluate_gate_shadow_outcomes,
    freeze_sector_gate_profiles,
    select_frozen_gate_candidates,
)
from stock_ai.buy_point_selection.gate_shadow_research import (
    GateShadowCandidate,
    GateShadowHit,
    build_gate_shadow_profiles,
    gate_profile_matrix_hash,
)
from stock_ai.buy_point_selection.models import BuyPointBar, DetectedSetup, SetupType
from stock_ai.buy_point_selection.planning import PricePlan


SIGNAL = date(2026, 7, 20)


def _candidate(
    *,
    code: str = "600001",
    profile_index: int = 2,
    quality: str = "0.80",
    buffer: str = "2.00",
) -> GateShadowCandidate:
    profile = build_gate_shadow_profiles()[profile_index]
    setup = DetectedSetup(
        code,
        SetupType.PRE_BREAKOUT,
        SIGNAL,
        SIGNAL - timedelta(days=20),
        Decimal("9.99"),
        Decimal("9.00"),
        Decimal(quality),
        ("FORMAL_FIXTURE",),
        {},
    )
    hit = GateShadowHit(code, SIGNAL, profile, setup, "ALLOW", "S1")
    plan = PricePlan(
        f"structure-{code}-{profile.profile_id}",
        code,
        SetupType.PRE_BREAKOUT,
        SIGNAL,
        Decimal("10.00"),
        Decimal("10.00"),
        Decimal("9.00"),
        Decimal("20.00"),
        Decimal("1.00"),
        Decimal("10.00"),
        100,
        SIGNAL + timedelta(days=2),
    )
    return GateShadowCandidate(
        hit, plan, Decimal("200000"), Decimal(buffer)
    )


def _time_exit_bars() -> tuple[BuyPointBar, ...]:
    return tuple(
        BuyPointBar(
            SIGNAL + timedelta(days=index),
            Decimal("10.00"),
            Decimal("10.60"),
            Decimal("9.50"),
            Decimal("10.50"),
            Decimal("1"),
            Decimal("200000"),
        )
        for index in range(1, 6)
    )


def _resolved_outcome(
    profile_id: str,
    index: int,
    net_return: str,
    *,
    stop_first: bool = False,
) -> GateShadowOutcome:
    code = f"600{index:03d}"
    return GateShadowOutcome(
        profile_id,
        code,
        SIGNAL,
        CaseOutcome(
            code,
            SIGNAL,
            "GATE_SHADOW",
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


def _qualifying_metrics(profile_id: str, mean: str) -> GateProfileMetrics:
    return GateProfileMetrics(
        profile_id,
        12,
        10,
        10,
        6,
        3,
        Decimal(mean),
        Decimal("0.01"),
        Decimal("0.60"),
        Decimal("0.30"),
        Decimal("0.06"),
        Decimal("0.02"),
        True,
        (),
    )


def test_outcome_wrapper_preserves_profile_and_cost_adjusted_return() -> None:
    """Catches profile identity or execution costs being lost in evaluation."""
    candidate = _candidate()

    row = evaluate_gate_shadow_outcomes(
        (candidate,),
        {candidate.hit.code: _time_exit_bars()},
        outcome_cutoff=SIGNAL + timedelta(days=5),
    )[0]

    assert row.profile_id == candidate.hit.profile.profile_id
    assert row.code == "600001"
    assert row.outcome.net_return == Decimal("0.03668096421471172962226640159")
    assert row.executable_shares == 0


def test_sector_profile_qualifies_at_literal_boundaries_but_market_never_does() -> None:
    """Catches inclusive precision edges drifting or market entering freeze."""
    sector_id = build_gate_shadow_profiles()[2].profile_id
    sector_outcomes = tuple(
        _resolved_outcome(
            sector_id,
            index,
            "0.02" if index < 5 else "-0.01",
            stop_first=index < 4,
        )
        for index in range(10)
    )
    sector = aggregate_gate_profile_metrics((sector_id,) * 10, sector_outcomes)[0]
    market_id = build_gate_shadow_profiles()[0].profile_id
    market_outcomes = tuple(
        _resolved_outcome(market_id, index, "0.02") for index in range(10)
    )
    market = aggregate_gate_profile_metrics((market_id,) * 10, market_outcomes)[0]

    assert sector.mean_net_return == Decimal("0.005")
    assert sector.positive_net_rate == Decimal("0.5")
    assert sector.stop_first_rate == Decimal("0.4")
    assert sector.qualifies
    assert not market.qualifies
    assert "DIAGNOSTIC_ONLY_MARKET_PROFILE" in market.qualification_reasons


@pytest.mark.parametrize(
    ("outcomes", "reason"),
    (
        (
            tuple(_resolved_outcome("PROFILE", index, "0.01") for index in range(9)),
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
                _resolved_outcome("PROFILE", index, "0.01", stop_first=index < 5)
                for index in range(10)
            ),
            "STOP_FIRST_RATE_ABOVE_40_PERCENT",
        ),
    ),
)
def test_sector_qualification_failures_are_explicit(
    outcomes: tuple[GateShadowOutcome, ...], reason: str
) -> None:
    """Catches a failed precision threshold being silently ignored."""
    metrics = aggregate_gate_profile_metrics(("PROFILE",) * len(outcomes), outcomes)[0]

    assert not metrics.qualifies
    assert reason in metrics.qualification_reasons


def test_freeze_requires_three_identities_and_excludes_market_profiles() -> None:
    """Catches observed evidence or diagnostic market profiles entering screen."""
    profiles = build_gate_shadow_profiles()
    market = _qualifying_metrics(profiles[0].profile_id, "0.20")
    weaker = _qualifying_metrics(profiles[2].profile_id, "0.01")
    better = _qualifying_metrics(profiles[3].profile_id, "0.02")

    freeze = freeze_sector_gate_profiles(
        profiles=profiles,
        training_identities=("research-c", "research-a", "research-b"),
        metrics=(market, weaker, better),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=gate_profile_matrix_hash(profiles),
        risk_coverage_complete=False,
    )

    assert freeze.training_identities == (
        "research-a",
        "research-b",
        "research-c",
    )
    assert [(value.profile_id, value.rank) for value in freeze.profiles] == [
        (better.profile_id, 1),
        (weaker.profile_id, 2),
    ]
    assert all(not value.profile_id.startswith("MARKET:") for value in freeze.profiles)
    assert freeze.retrospective
    assert not freeze.promotion_eligible

    with pytest.raises(ValueError, match="three distinct research identities"):
        freeze_sector_gate_profiles(
            profiles=profiles,
            training_identities=("same", "same", "third"),
            metrics=(weaker,),
            formal_rule_version="buy-point-selection-3.1.0",
            formal_policy_hash="policy-hash",
            profile_matrix_hash=gate_profile_matrix_hash(profiles),
            risk_coverage_complete=True,
        )


def test_freeze_ranks_literal_zero_stop_rate_ahead_of_nonzero_rate() -> None:
    """Catches Decimal zero being treated as missing during profile ranking."""
    profiles = build_gate_shadow_profiles()
    zero_stop = replace(
        _qualifying_metrics(profiles[2].profile_id, "0.02"),
        stop_first=0,
        stop_first_rate=Decimal("0"),
    )
    nonzero_stop = replace(
        _qualifying_metrics(profiles[3].profile_id, "0.02"),
        stop_first=3,
        stop_first_rate=Decimal("0.30"),
    )

    freeze = freeze_sector_gate_profiles(
        profiles=profiles,
        training_identities=("first", "second", "third"),
        metrics=(nonzero_stop, zero_stop),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=gate_profile_matrix_hash(profiles),
        risk_coverage_complete=True,
    )

    assert freeze.profiles[0].profile_id == zero_stop.profile_id


def test_frozen_selection_deduplicates_filters_and_caps_daily_candidates() -> None:
    """Catches market backfill, duplicate stocks, or baskets above five."""
    profiles = build_gate_shadow_profiles()
    freeze = freeze_sector_gate_profiles(
        profiles=profiles,
        training_identities=("first", "second", "third"),
        metrics=(
            _qualifying_metrics(profiles[2].profile_id, "0.01"),
            _qualifying_metrics(profiles[3].profile_id, "0.02"),
        ),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=gate_profile_matrix_hash(profiles),
        risk_coverage_complete=True,
    )
    candidates = (
        _candidate(code="600001", profile_index=2),
        _candidate(code="600001", profile_index=3),
        _candidate(code="600002", profile_index=3),
        _candidate(code="600003", profile_index=3),
        _candidate(code="600004", profile_index=2),
        _candidate(code="600005", profile_index=2),
        _candidate(code="600006", profile_index=2),
        _candidate(code="600007", profile_index=2),
        _candidate(code="600008", profile_index=0),
    )

    selected = select_frozen_gate_candidates(candidates, freeze)

    assert [value.hit.code for value in selected] == [
        "600001",
        "600002",
        "600003",
        "600004",
        "600005",
    ]
    assert len({(value.hit.signal_date, value.hit.code) for value in selected}) == 5
    assert all(value.executable_shares == 0 for value in selected)


def test_empty_freeze_never_backfills_candidates() -> None:
    """Catches a failed research result being hidden by fallback selection."""
    profiles = build_gate_shadow_profiles()
    failed = replace(
        _qualifying_metrics(profiles[2].profile_id, "0.01"),
        qualifies=False,
        qualification_reasons=("MINIMUM_RESOLVED_TRIGGERED",),
    )
    freeze = freeze_sector_gate_profiles(
        profiles=profiles,
        training_identities=("first", "second", "third"),
        metrics=(failed,),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=gate_profile_matrix_hash(profiles),
        risk_coverage_complete=True,
    )

    assert freeze.empty
    assert select_frozen_gate_candidates((_candidate(),), freeze) == ()
