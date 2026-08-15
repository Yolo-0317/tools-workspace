from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.gate_shadow_research import (
    build_gate_shadow_profiles,
    gate_profile_matrix_hash,
    matching_gate_profile,
    replay_gate_shadows,
    validate_gate_shadow_profiles,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    MarketSnapshot,
    SectorSnapshot,
    SetupType,
)
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    SectorMembership,
)


SIGNAL_DATE = date(2026, 8, 3)


def _bars() -> tuple[BuyPointBar, ...]:
    return tuple(
        BuyPointBar(
            SIGNAL_DATE - timedelta(days=59 - index),
            Decimal("10"),
            Decimal("10.10"),
            Decimal("9.90"),
            Decimal("10"),
            Decimal("0"),
            Decimal("200000"),
        )
        for index in range(60)
    )


def _setup() -> DetectedSetup:
    return DetectedSetup(
        "600001",
        SetupType.PRE_BREAKOUT,
        SIGNAL_DATE,
        SIGNAL_DATE - timedelta(days=20),
        Decimal("10.10"),
        Decimal("9.80"),
        Decimal("0.80"),
        ("FORMAL",),
        {},
    )


def _replay(
    market: MarketSnapshot,
    sector: SectorSnapshot,
    *,
    bars: tuple[BuyPointBar, ...] | None = None,
    holding_codes: frozenset[str] = frozenset(),
    setup_detector=None,
):
    return replay_gate_shadows(
        signal_dates=(SIGNAL_DATE,),
        trading_dates=(
            SIGNAL_DATE,
            SIGNAL_DATE + timedelta(days=1),
            SIGNAL_DATE + timedelta(days=2),
        ),
        bars_by_code={"600001": bars or _bars()},
        memberships=(
            SectorMembership(
                "600001",
                "S1",
                "测试行业",
                SIGNAL_DATE - timedelta(days=100),
                None,
                "fixture",
            ),
        ),
        risk_flags=(),
        coverage_by_date={
            SIGNAL_DATE: ReferenceCoverage(SIGNAL_DATE, True, True, True)
        },
        market_snapshots={SIGNAL_DATE: market},
        holding_codes_by_date={SIGNAL_DATE: holding_codes},
        profiles=build_gate_shadow_profiles(),
        setup_detector=setup_detector or (lambda code, bars, policy: (_setup(),)),
        sector_snapshot_builder=lambda panel, memberships, policy: {"S1": sector},
    )


def test_gate_profile_matrix_is_exact_and_market_is_diagnostic_only() -> None:
    """Catches an unsafe gate reason becoming freeze-eligible or disappearing."""
    profiles = build_gate_shadow_profiles()

    assert [value.profile_id for value in profiles] == [
        "MARKET:AMOUNT_AND_BREADTH_WEAK:DIAGNOSTIC",
        "MARKET:INDEX_AND_BREADTH_WEAK:DIAGNOSTIC",
        "SECTOR:SECTOR_AMOUNT_WEAK:BYPASS",
        "SECTOR:SECTOR_BREADTH_WEAK:BYPASS",
        "SECTOR:SECTOR_NOT_RESONATING:BYPASS",
        "SECTOR:SECTOR_RELATIVE_STRENGTH_WEAK:BYPASS",
    ]
    assert all(not value.freeze_eligible for value in profiles[:2])
    assert all(value.freeze_eligible for value in profiles[2:])
    assert len(gate_profile_matrix_hash(profiles)) == 64


def test_only_one_supported_reason_matches_a_gate_profile() -> None:
    """Catches multi-failure or hard-boundary rows entering the shadow cohort."""
    profiles = build_gate_shadow_profiles()

    assert matching_gate_profile(
        "SECTOR", ("SECTOR_BREADTH_WEAK",), profiles
    ).profile_id == "SECTOR:SECTOR_BREADTH_WEAK:BYPASS"
    assert matching_gate_profile(
        "SECTOR",
        ("SECTOR_BREADTH_WEAK", "SECTOR_AMOUNT_WEAK"),
        profiles,
    ) is None
    assert matching_gate_profile(
        "SECTOR", ("SECTOR_SAMPLE_TOO_SMALL",), profiles
    ) is None
    assert matching_gate_profile(
        "MARKET", ("MARKET_DATA_INCOMPLETE",), profiles
    ) is None


def test_profile_validation_rejects_forged_or_reordered_matrices() -> None:
    """Catches callers silently changing the approved six-profile experiment."""
    profiles = build_gate_shadow_profiles()

    with pytest.raises(ValueError, match="unsupported gate profile matrix"):
        validate_gate_shadow_profiles(tuple(reversed(profiles)))
    with pytest.raises(ValueError, match="unsupported gate profile matrix"):
        validate_gate_shadow_profiles(
            (replace(profiles[0], freeze_eligible=True), *profiles[1:])
        )


def test_sector_single_reason_reaches_unchanged_price_plan() -> None:
    """Catches a supported sector reason being discarded before plan validation."""
    replay = _replay(
        MarketSnapshot(3, 60.0, 1.1, True),
        SectorSnapshot("S1", "测试行业", 0.8, 6, 2, 0.40, 0.9, True),
    )

    assert len(replay.raw_hits) == 1
    assert len(replay.candidates) == 1
    candidate = replay.candidates[0]
    assert candidate.hit.profile.profile_id == "SECTOR:SECTOR_BREADTH_WEAK:BYPASS"
    assert candidate.plan.risk_reward_ratio == Decimal("2")
    assert candidate.executable_shares == 0


def test_market_failure_uses_limited_plan_but_remains_diagnostic() -> None:
    """Catches a weak market being treated as ALLOW or becoming freeze-eligible."""
    replay = _replay(
        MarketSnapshot(1, 39.0, 0.9, True),
        SectorSnapshot("S1", "测试行业", 0.8, 6, 2, 0.60, 0.9, True),
    )

    assert len(replay.candidates) == 1
    candidate = replay.candidates[0]
    assert candidate.hit.profile.mode == "DIAGNOSTIC"
    assert candidate.hit.market_status == "FREEZE"
    assert candidate.plan.maximum_shares == 100
    assert candidate.executable_shares == 0


def test_market_diagnostic_still_requires_sector_gate_to_pass() -> None:
    """Catches a market counterfactual also bypassing a second sector failure."""
    replay = _replay(
        MarketSnapshot(1, 39.0, 0.9, True),
        SectorSnapshot("S1", "测试行业", 0.8, 6, 2, 0.40, 0.9, True),
    )

    assert replay.raw_hits == ()
    assert replay.candidates == ()
    assert any(value.stage == "SECTOR" for value in replay.rejections)


def test_formal_setup_and_hard_base_boundaries_cannot_be_bypassed() -> None:
    """Catches gate research admitting a no-setup row or an existing holding."""
    market = MarketSnapshot(3, 60.0, 1.1, True)
    sector = SectorSnapshot("S1", "测试行业", 0.8, 6, 2, 0.40, 0.9, True)

    no_setup = _replay(
        market,
        sector,
        setup_detector=lambda code, bars, policy: (),
    )
    holding = _replay(
        market,
        sector,
        holding_codes=frozenset({"600001"}),
    )

    assert no_setup.raw_hits == no_setup.candidates == ()
    assert any(value.reasons == ("NO_BUY_POINT_SETUP",) for value in no_setup.rejections)
    assert holding.raw_hits == holding.candidates == ()
    assert any("EXISTING_HOLDING" in value.reasons for value in holding.rejections)


def test_multiple_sector_failures_are_not_counterfactually_admitted() -> None:
    """Catches one profile masking a second simultaneous sector weakness."""
    replay = _replay(
        MarketSnapshot(3, 60.0, 1.1, True),
        SectorSnapshot("S1", "测试行业", 0.8, 6, 2, 0.40, 0.70, True),
    )

    assert replay.raw_hits == replay.candidates == ()
    assert any(
        value.reasons == ("SECTOR_BREADTH_WEAK", "SECTOR_AMOUNT_WEAK")
        for value in replay.rejections
    )


def test_future_price_bar_cannot_change_signal_time_replay() -> None:
    """Catches outcome data leaking into setup, gate, or plan construction."""
    market = MarketSnapshot(3, 60.0, 1.1, True)
    sector = SectorSnapshot("S1", "测试行业", 0.8, 6, 2, 0.40, 0.9, True)
    future = BuyPointBar(
        SIGNAL_DATE + timedelta(days=1),
        Decimal("50"),
        Decimal("55"),
        Decimal("45"),
        Decimal("52"),
        Decimal("420"),
        Decimal("900000"),
    )

    bounded = _replay(market, sector)
    with_future = _replay(market, sector, bars=(*_bars(), future))

    assert with_future.raw_hits == bounded.raw_hits
    assert with_future.candidates == bounded.candidates
