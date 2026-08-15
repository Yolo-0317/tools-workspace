from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping

import pytest

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
from stock_ai.buy_point_selection.planning import RiskBudget
from stock_ai.buy_point_selection.structure_stop_shadow import (
    build_structure_stop_anchor,
    build_structure_stop_plan,
    build_structure_stop_profiles,
    dynamic_support_anchor,
    recent_setup_low,
    replay_structure_stop_shadows,
    structure_stop_profile_hash,
    validate_structure_stop_profiles,
)


def test_structure_stop_profile_matrix_is_exact() -> None:
    """Catches an added, omitted, reordered, or executable stop profile."""
    profiles = build_structure_stop_profiles()

    assert tuple(value.profile_id for value in profiles) == (
        "STRUCTURE_STOP:RECENT_SETUP_LOW",
        "STRUCTURE_STOP:DYNAMIC_SUPPORT",
        "STRUCTURE_STOP:ATR_1_5",
    )
    assert tuple(value.uses_atr_buffer for value in profiles) == (
        True,
        True,
        False,
    )
    assert len(structure_stop_profile_hash(profiles)) == 64
    with pytest.raises(ValueError, match="profile matrix"):
        validate_structure_stop_profiles(tuple(reversed(profiles)))
    with pytest.raises(ValueError, match="profile matrix"):
        validate_structure_stop_profiles(
            (replace(profiles[0], anchor_kind="FORGED"), *profiles[1:])
        )


def _bars() -> tuple[BuyPointBar, ...]:
    start = date(2026, 6, 12)
    values = []
    for index in range(60):
        close = Decimal("9.80") if index < 50 else Decimal("9.90")
        low = Decimal("9.75")
        if index == 50:
            low = Decimal("9.70")
        if index == 57:
            low = Decimal("9.80")
        if index == 58:
            low = Decimal("9.90")
        if index == 59:
            low = Decimal("9.95")
        values.append(
            BuyPointBar(
                start + timedelta(days=index),
                close,
                Decimal("10.20"),
                low,
                close,
                Decimal("0"),
                Decimal("200000"),
            )
        )
    return tuple(values)


def _setup(setup_type: SetupType, **metrics: Decimal) -> DetectedSetup:
    bars = _bars()
    return DetectedSetup(
        "600001",
        setup_type,
        bars[-1].trade_date,
        bars[-10].trade_date,
        Decimal("10.20"),
        Decimal("9.00"),
        Decimal("0.80"),
        ("FORMAL",),
        metrics,
    )


@pytest.mark.parametrize(
    ("setup", "expected"),
    (
        (_setup(SetupType.PRE_BREAKOUT), Decimal("9.70")),
        (
            _setup(SetupType.TREND_PULLBACK, pullback_sessions=Decimal("3")),
            Decimal("9.80"),
        ),
        (
            _setup(
                SetupType.FIRST_LAUNCH_PULLBACK,
                quiet_sessions=Decimal("2"),
            ),
            Decimal("9.90"),
        ),
    ),
)
def test_recent_setup_low_uses_the_setup_specific_signal_time_window(
    setup: DetectedSetup, expected: Decimal
) -> None:
    """Catches an old low or future low widening a recent stop anchor."""
    bars = _bars()
    future = replace(
        bars[-1],
        trade_date=bars[-1].trade_date + timedelta(days=1),
        low=Decimal("1.00"),
    )

    assert recent_setup_low(setup, bars) == expected
    assert recent_setup_low(setup, (*bars, future)) == expected


def test_dynamic_support_selects_the_highest_valid_support_below_signal_low() -> None:
    """Catches a lower support or already-broken level replacing the nearest support."""
    setup = _setup(SetupType.PRE_BREAKOUT)

    assert dynamic_support_anchor(setup, _bars()) == Decimal("9.90")


def test_invalid_recent_metadata_does_not_remove_valid_moving_average_support() -> None:
    """Catches guessed recent lows while preserving independently valid support."""
    missing = _setup(SetupType.TREND_PULLBACK)
    fractional = _setup(
        SetupType.FIRST_LAUNCH_PULLBACK,
        quiet_sessions=Decimal("1.5"),
    )
    assert recent_setup_low(missing, _bars()) is None
    assert recent_setup_low(fractional, _bars()) is None
    assert dynamic_support_anchor(missing, _bars()) == Decimal("9.90")


def _plan_bars() -> tuple[BuyPointBar, ...]:
    start = date(2026, 6, 12)
    values = []
    for index in range(60):
        values.append(
            BuyPointBar(
                start + timedelta(days=index),
                Decimal("9.88"),
                Decimal("10.00"),
                Decimal("9.80") if index < 59 else Decimal("9.88"),
                Decimal("9.88"),
                Decimal("0"),
                Decimal("200000"),
            )
        )
    return tuple(values)


def _plan_setup() -> DetectedSetup:
    bars = _plan_bars()
    return DetectedSetup(
        "600001",
        SetupType.PRE_BREAKOUT,
        bars[-1].trade_date,
        bars[-30].trade_date,
        Decimal("10.00"),
        Decimal("9.00"),
        Decimal("0.80"),
        ("FORMAL",),
        {},
    )


def test_atr_profile_uses_exactly_one_point_five_atr_without_extra_buffer() -> None:
    """Catches the production 0.2 ATR support buffer being double-counted."""
    bars = _plan_bars()
    setup = _plan_setup()
    profile = build_structure_stop_profiles()[2]
    anchor = build_structure_stop_anchor(setup, bars, profile)

    assert anchor.reasons == ()
    assert anchor.anchor_price == Decimal("9.71")
    assert anchor.invalidation_price == Decimal("9.71")
    assert anchor.executable_shares == 0


@pytest.mark.parametrize("profile_index", (0, 1, 2))
def test_shadow_plan_preserves_formal_trigger_two_r_expiry_and_zero_share_anchor(
    profile_index: int,
) -> None:
    """Catches an anchor profile changing entry, reward multiple, or validity."""
    bars = _plan_bars()
    setup = _plan_setup()
    expiry = bars[-1].trade_date + timedelta(days=2)

    decision = build_structure_stop_plan(
        setup,
        bars,
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "ALLOW",
        build_structure_stop_profiles()[profile_index],
        valid_through_trade_date=expiry,
    )

    assert decision.reasons == ()
    assert decision.plan is not None
    assert decision.plan.trigger_price == Decimal("10.01")
    assert decision.plan.target_2r == (
        decision.plan.trigger_price
        + Decimal("2") * decision.plan.risk_distance
    )
    assert decision.plan.valid_through_trade_date == expiry


def test_shadow_plan_keeps_formal_resistance_and_limited_budget_checks() -> None:
    """Catches the stop study bypassing resistance or LIMITED position sizing."""
    bars = _plan_bars()
    setup = _plan_setup()
    profile = build_structure_stop_profiles()[0]
    blocked_bars = list(bars)
    blocked_bars[20] = replace(blocked_bars[20], high=Decimal("10.20"))

    blocked = build_structure_stop_plan(
        setup,
        tuple(blocked_bars),
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "ALLOW",
        profile,
    )
    limited = build_structure_stop_plan(
        setup,
        bars,
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "LIMITED",
        profile,
    )

    assert blocked.reasons == ("INSUFFICIENT_TWO_R_SPACE",)
    assert limited.plan is not None
    assert limited.plan.maximum_shares == 100


def _boundary_bars(signal_low: str) -> tuple[BuyPointBar, ...]:
    bars = []
    start = date(2026, 6, 12)
    for index in range(60):
        low = Decimal("9.80") if index < 59 else Decimal(signal_low)
        close = Decimal("9.80") if index < 59 else Decimal("9.90")
        bars.append(
            BuyPointBar(
                start + timedelta(days=index),
                Decimal("9.80"),
                Decimal("10.00"),
                low,
                close,
                Decimal("0"),
                Decimal("200000"),
            )
        )
    return tuple(bars)


@pytest.mark.parametrize(
    ("signal_low", "accepted"),
    (
        ("9.90", False),
        ("9.89", True),
        ("9.56", True),
        ("9.55", False),
    ),
)
def test_shadow_plan_enforces_dynamic_lower_bound_and_five_percent_upper_bound(
    signal_low: str, accepted: bool
) -> None:
    """Catches inclusive risk boundaries drifting from the formal planner."""
    bars = _boundary_bars(signal_low)
    setup = DetectedSetup(
        "600001",
        SetupType.FIRST_LAUNCH_PULLBACK,
        bars[-1].trade_date,
        bars[-2].trade_date,
        Decimal("10.00"),
        Decimal("9.00"),
        Decimal("0.80"),
        ("FORMAL",),
        {"quiet_sessions": Decimal("1")},
    )

    decision = build_structure_stop_plan(
        setup,
        bars,
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "ALLOW",
        build_structure_stop_profiles()[0],
    )

    assert (decision.plan is not None) is accepted
    assert decision.reasons == (() if accepted else ("RISK_DISTANCE_OUT_OF_RANGE",))


REPLAY_SIGNAL_DATE = date(2026, 8, 3)


def _replay_bars() -> tuple[BuyPointBar, ...]:
    return tuple(
        BuyPointBar(
            REPLAY_SIGNAL_DATE - timedelta(days=59 - index),
            Decimal("10.00"),
            Decimal("10.00"),
            Decimal("9.80"),
            Decimal("10.00"),
            Decimal("0"),
            Decimal("200000"),
        )
        for index in range(60)
    )


def _risk_only_setup() -> DetectedSetup:
    return DetectedSetup(
        "600001",
        SetupType.PRE_BREAKOUT,
        REPLAY_SIGNAL_DATE,
        REPLAY_SIGNAL_DATE - timedelta(days=20),
        Decimal("10.00"),
        Decimal("9.93"),
        Decimal("0.80"),
        ("FORMAL",),
        {},
    )


def _passing_sector() -> SectorSnapshot:
    return SectorSnapshot(
        "S1", "测试行业", 0.8, 6, 2, 0.60, 0.90, True
    )


def _structure_replay(
    *,
    bars: tuple[BuyPointBar, ...] | None = None,
    bars_by_code: Mapping[str, tuple[BuyPointBar, ...]] | None = None,
    memberships: tuple[SectorMembership, ...] | None = None,
    coverage: ReferenceCoverage | None = None,
    market: MarketSnapshot | None = None,
    holding_codes: frozenset[str] = frozenset(),
    holdings_present: bool = True,
    setup_detector=None,
    sector: SectorSnapshot | None = None,
):
    resolved_memberships = (
        (
            SectorMembership(
                "600001",
                "S1",
                "测试行业",
                REPLAY_SIGNAL_DATE - timedelta(days=100),
                None,
                "fixture",
            ),
        )
        if memberships is None
        else memberships
    )
    return replay_structure_stop_shadows(
        signal_dates=(REPLAY_SIGNAL_DATE,),
        trading_dates=(
            REPLAY_SIGNAL_DATE,
            REPLAY_SIGNAL_DATE + timedelta(days=1),
            REPLAY_SIGNAL_DATE + timedelta(days=2),
        ),
        bars_by_code=(
            bars_by_code
            if bars_by_code is not None
            else {"600001": bars or _replay_bars()}
        ),
        memberships=resolved_memberships,
        risk_flags=(),
        coverage_by_date={
            REPLAY_SIGNAL_DATE: coverage
            or ReferenceCoverage(REPLAY_SIGNAL_DATE, True, True, True)
        },
        market_snapshots={
            REPLAY_SIGNAL_DATE: market or MarketSnapshot(3, 60.0, 1.1, True)
        },
        holding_codes_by_date=(
            {REPLAY_SIGNAL_DATE: holding_codes} if holdings_present else {}
        ),
        profiles=build_structure_stop_profiles(),
        setup_detector=setup_detector
        or (
            lambda code, bars, policy: (
                replace(_risk_only_setup(), code=code),
            )
        ),
        sector_snapshot_builder=lambda panel, memberships, policy: {
            "S1": sector or _passing_sector()
        },
    )


def test_replay_admits_only_risk_only_formal_gate_passes_to_primary() -> None:
    """Catches a non-risk or gate failure entering the primary cohort."""
    replay = _structure_replay()

    assert replay.incomplete_dates == ()
    assert len(replay.baseline_hits) == 1
    assert replay.baseline_hits[0].baseline_reasons == (
        "RISK_DISTANCE_OUT_OF_RANGE",
    )
    assert replay.baseline_hits[0].executable_shares == 0
    assert tuple(value.profile.profile_id for value in replay.candidates) == (
        "STRUCTURE_STOP:RECENT_SETUP_LOW",
        "STRUCTURE_STOP:DYNAMIC_SUPPORT",
        "STRUCTURE_STOP:ATR_1_5",
    )
    assert all(value.anchor.executable_shares == 0 for value in replay.candidates)
    assert all(value.executable_shares == 0 for value in replay.candidates)
    assert all(value.status == "CASE_ANALYSIS_ONLY" for value in replay.candidates)
    assert all(value.trade_permission == "NO-TRADE" for value in replay.candidates)


def test_replay_uses_the_highest_quality_production_setup() -> None:
    """Catches replay order selecting a lower-quality detected setup."""
    low = replace(_risk_only_setup(), quality=Decimal("0.70"))
    high = replace(_risk_only_setup(), quality=Decimal("0.90"))

    replay = _structure_replay(
        setup_detector=lambda code, bars, policy: (low, high)
    )

    assert replay.baseline_hits[0].setup.quality == Decimal("0.90")


@pytest.mark.parametrize(
    ("market", "sector", "expected_gate", "expected_reason"),
    (
        (
            MarketSnapshot(1, 39.0, 0.9, True),
            _passing_sector(),
            "MARKET",
            "INDEX_AND_BREADTH_WEAK",
        ),
        (
            MarketSnapshot(3, 60.0, 1.1, True),
            SectorSnapshot(
                "S1", "测试行业", 0.8, 6, 2, 0.40, 0.90, True
            ),
            "SECTOR",
            "SECTOR_BREADTH_WEAK",
        ),
    ),
)
def test_single_supported_gate_plus_risk_failure_is_diagnostic_only(
    market: MarketSnapshot,
    sector: SectorSnapshot,
    expected_gate: str,
    expected_reason: str,
) -> None:
    """Catches a combined gate failure entering primary or being discarded."""
    replay = _structure_replay(market=market, sector=sector)

    assert replay.baseline_hits == ()
    assert replay.candidates == ()
    assert len(replay.diagnostics) == 1
    diagnostic = replay.diagnostics[0]
    assert diagnostic.gate == expected_gate
    assert diagnostic.gate_reason == expected_reason
    assert diagnostic.baseline_reason == "RISK_DISTANCE_OUT_OF_RANGE"
    assert diagnostic.label == "DIAGNOSTIC_ONLY_COMBINED_FAILURE"
    assert diagnostic.executable_shares == 0


@pytest.mark.parametrize(
    ("bars", "setup", "expected_reasons"),
    (
        (
            (
                replace(_replay_bars()[0], high=Decimal("10.10")),
                *_replay_bars()[1:],
            ),
            _risk_only_setup(),
            (
                "RISK_DISTANCE_OUT_OF_RANGE",
                "INSUFFICIENT_TWO_R_SPACE",
            ),
        ),
        (
            tuple(
                replace(
                    value,
                    open=Decimal("100"),
                    high=Decimal("100"),
                    low=Decimal("98"),
                    close=Decimal("100"),
                )
                for value in _replay_bars()
            ),
            replace(
                _risk_only_setup(),
                structure_high=Decimal("100"),
                structure_low=Decimal("99.93"),
            ),
            (
                "RISK_DISTANCE_OUT_OF_RANGE",
                "POSITION_BELOW_BOARD_LOT",
            ),
        ),
    ),
)
def test_extra_price_failure_cannot_enter_primary_cohort(
    bars: tuple[BuyPointBar, ...],
    setup: DetectedSetup,
    expected_reasons: tuple[str, ...],
) -> None:
    """Catches a second price-plan failure being attributed to stop geometry."""
    replay = _structure_replay(
        bars=bars,
        setup_detector=lambda code, values, policy: (setup,),
    )

    assert replay.baseline_hits == replay.candidates == replay.diagnostics == ()
    assert any(
        value.stage == "PRICE_PLAN" and value.reasons == expected_reasons
        for value in replay.rejections
    )


@pytest.mark.parametrize(
    "kwargs",
    (
        {
            "coverage": ReferenceCoverage(
                REPLAY_SIGNAL_DATE, False, True, True
            )
        },
        {"holdings_present": False},
    ),
)
def test_incomplete_reference_or_historical_holdings_fail_closed(kwargs) -> None:
    """Catches missing point-in-time facts being replaced with current defaults."""
    replay = _structure_replay(**kwargs)

    assert replay.incomplete_dates == (REPLAY_SIGNAL_DATE,)
    assert replay.baseline_hits == replay.candidates == replay.diagnostics == ()


def test_hard_gate_failures_never_reach_stop_attribution() -> None:
    """Catches holdings, anti-chase, or missing setup being bypassed."""
    heated_bars = (
        *_replay_bars()[:-1],
        replace(_replay_bars()[-1], pct_chg=Decimal("6")),
    )
    holding = _structure_replay(holding_codes=frozenset({"600001"}))
    heated = _structure_replay(bars=heated_bars)
    no_setup = _structure_replay(
        setup_detector=lambda code, bars, policy: ()
    )
    no_membership = _structure_replay(memberships=())

    assert any("EXISTING_HOLDING" in value.reasons for value in holding.rejections)
    assert any(value.stage == "ANTI_CHASE" for value in heated.rejections)
    assert any(value.stage == "SETUP" for value in no_setup.rejections)
    assert any(
        value.reasons == ("SECTOR_MISSING",)
        for value in no_membership.rejections
    )
    for replay in (holding, heated, no_setup, no_membership):
        assert replay.baseline_hits == replay.candidates == replay.diagnostics == ()


def test_multiple_gate_failures_or_non_risk_price_failure_are_not_diagnostics() -> None:
    """Catches a diagnostic label masking a second gate or another price cause."""
    weak_market = MarketSnapshot(1, 39.0, 0.9, True)
    weak_sector = SectorSnapshot(
        "S1", "测试行业", 0.8, 6, 2, 0.40, 0.90, True
    )
    two_gates = _structure_replay(market=weak_market, sector=weak_sector)

    price_bars = (
        replace(_replay_bars()[0], high=Decimal("10.20")),
        *_replay_bars()[1:],
    )
    valid_risk_setup = replace(
        _risk_only_setup(), structure_low=Decimal("9.70")
    )
    wrong_price_reason = _structure_replay(
        bars=price_bars,
        market=weak_market,
        setup_detector=lambda code, bars, policy: (valid_risk_setup,),
    )

    assert two_gates.diagnostics == ()
    assert any(value.stage == "SECTOR" for value in two_gates.rejections)
    assert wrong_price_reason.diagnostics == ()
    assert any(
        value.reasons == ("INSUFFICIENT_TWO_R_SPACE",)
        for value in wrong_price_reason.rejections
    )


def test_profile_rejections_remain_independent() -> None:
    """Catches one profile failure suppressing valid alternate stop profiles."""
    bars = tuple(
        replace(
            value,
            open=Decimal("9.80"),
            high=Decimal("10.00"),
            low=(Decimal("9.90") if index == 59 else Decimal("9.70")),
            close=Decimal("9.80"),
        )
        for index, value in enumerate(_replay_bars())
    )
    setup = replace(
        _risk_only_setup(),
        setup_type=SetupType.TREND_PULLBACK,
        metrics={},
    )

    replay = _structure_replay(
        bars=bars,
        setup_detector=lambda code, values, policy: (setup,),
    )

    assert tuple(value.profile.profile_id for value in replay.candidates) == (
        "STRUCTURE_STOP:DYNAMIC_SUPPORT",
        "STRUCTURE_STOP:ATR_1_5",
    )
    assert any(
        value.profile_id == "STRUCTURE_STOP:RECENT_SETUP_LOW"
        and value.reasons == ("RECENT_SETUP_LOW_UNAVAILABLE",)
        for value in replay.rejections
    )


def test_future_prices_and_memberships_cannot_change_replay_or_zero_shares() -> None:
    """Catches outcome or future-reference leakage into cohort construction."""
    future_bar = BuyPointBar(
        REPLAY_SIGNAL_DATE + timedelta(days=1),
        Decimal("50"),
        Decimal("55"),
        Decimal("45"),
        Decimal("52"),
        Decimal("420"),
        Decimal("900000"),
    )
    current_membership = SectorMembership(
        "600001",
        "S1",
        "测试行业",
        REPLAY_SIGNAL_DATE - timedelta(days=100),
        None,
        "fixture",
    )
    future_membership = SectorMembership(
        "600001",
        "S2",
        "未来行业",
        REPLAY_SIGNAL_DATE + timedelta(days=1),
        None,
        "future-fixture",
    )

    bounded = _structure_replay(memberships=(current_membership,))
    with_future = _structure_replay(
        bars=(*_replay_bars(), future_bar),
        memberships=(current_membership, future_membership),
    )

    assert with_future == bounded
    assert all(value.executable_shares == 0 for value in bounded.baseline_hits)
    assert all(value.executable_shares == 0 for value in bounded.candidates)
    assert all(
        value.anchor.executable_shares == 0 for value in bounded.candidates
    )

    diagnostic_bounded = _structure_replay(
        memberships=(current_membership,),
        market=MarketSnapshot(1, 39.0, 0.9, True),
    )
    diagnostic_with_future = _structure_replay(
        bars=(*_replay_bars(), future_bar),
        memberships=(current_membership, future_membership),
        market=MarketSnapshot(1, 39.0, 0.9, True),
    )
    assert diagnostic_with_future == diagnostic_bounded
    assert all(
        value.executable_shares == 0
        for value in diagnostic_bounded.diagnostics
    )


def test_diagnostics_are_sorted_by_date_code_gate_and_reason() -> None:
    """Catches input mapping order leaking into immutable diagnostic rows."""
    memberships = tuple(
        SectorMembership(
            code,
            "S1",
            "测试行业",
            REPLAY_SIGNAL_DATE - timedelta(days=100),
            None,
            "fixture",
        )
        for code in ("600002", "600001")
    )

    replay = _structure_replay(
        bars_by_code={"600002": _replay_bars(), "600001": _replay_bars()},
        memberships=memberships,
        market=MarketSnapshot(1, 39.0, 0.9, True),
    )

    assert tuple(value.code for value in replay.diagnostics) == (
        "600001",
        "600002",
    )
