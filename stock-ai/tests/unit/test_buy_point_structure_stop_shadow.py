from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    SetupType,
)
from stock_ai.buy_point_selection.planning import RiskBudget
from stock_ai.buy_point_selection.structure_stop_shadow import (
    build_structure_stop_anchor,
    build_structure_stop_plan,
    build_structure_stop_profiles,
    dynamic_support_anchor,
    recent_setup_low,
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
