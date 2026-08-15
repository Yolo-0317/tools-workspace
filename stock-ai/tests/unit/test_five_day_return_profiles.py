from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_return_profiles import (
    build_five_day_return_profiles,
    evaluation_position,
    five_day_profile_hash,
    resolve_profile_stop,
    structure_atr_stop,
    validate_five_day_return_profiles,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    SetupType,
)


def test_profile_matrix_rejects_reordering_and_changed_values() -> None:
    profiles = build_five_day_return_profiles()

    assert tuple(value.profile_id for value in profiles) == (
        "BREAKOUT_TRIGGER__FIXED_3_PERCENT",
        "BREAKOUT_TRIGGER__STRUCTURE_ATR",
        "PULLBACK_RECLAIM__FIXED_3_PERCENT",
        "PULLBACK_RECLAIM__STRUCTURE_ATR",
    )
    assert tuple((value.entry_kind, value.stop_kind) for value in profiles) == (
        ("BREAKOUT_TRIGGER", "FIXED_3_PERCENT"),
        ("BREAKOUT_TRIGGER", "STRUCTURE_ATR"),
        ("PULLBACK_RECLAIM", "FIXED_3_PERCENT"),
        ("PULLBACK_RECLAIM", "STRUCTURE_ATR"),
    )
    assert len(five_day_profile_hash(profiles)) == 64

    with pytest.raises(ValueError, match="profile matrix"):
        validate_five_day_return_profiles(tuple(reversed(profiles)))
    with pytest.raises(ValueError, match="profile matrix"):
        validate_five_day_return_profiles(
            (replace(profiles[0], stop_kind="FORGED"), *profiles[1:])
        )


@pytest.mark.parametrize(
    ("price", "shares", "notional", "exceeds"),
    (
        ("5", 2000, "10000", False),
        ("30", 300, "9000", False),
        ("100", 100, "10000", False),
        ("101", 100, "10100", True),
    ),
)
def test_evaluation_position_targets_ten_thousand_yuan_in_board_lots(
    price: str,
    shares: int,
    notional: str,
    exceeds: bool,
) -> None:
    value = evaluation_position(Decimal(price))

    assert value.evaluation_target_notional == Decimal("10000")
    assert value.evaluation_shares == shares
    assert value.evaluation_notional == Decimal(notional)
    assert value.minimum_lot_exceeds_target is exceeds
    assert value.executable_shares == 0


@pytest.mark.parametrize("price", ("NaN", "Infinity", "0", "-1"))
def test_evaluation_position_rejects_invalid_entry_prices(price: str) -> None:
    with pytest.raises(ValueError, match="entry price"):
        evaluation_position(Decimal(price))


def test_fixed_stop_is_exactly_three_percent_below_the_slipped_entry() -> None:
    profile = build_five_day_return_profiles()[0]

    decision = resolve_profile_stop(
        profile=profile,
        entry_price=Decimal("10.11"),
        structure_stop=None,
    )

    assert decision.stop_price == Decimal("9.80")
    assert decision.risk_fraction == Decimal("0.31") / Decimal("10.11")
    assert decision.reasons == ()


@pytest.mark.parametrize(
    ("entry", "stop", "accepted"),
    (
        ("10", "9.85", True),
        ("10", "9.50", True),
        ("10", "9.86", False),
        ("10", "9.49", False),
    ),
)
def test_structure_stop_accepts_inclusive_one_point_five_to_five_percent(
    entry: str,
    stop: str,
    accepted: bool,
) -> None:
    profile = build_five_day_return_profiles()[1]

    decision = resolve_profile_stop(
        profile=profile,
        entry_price=Decimal(entry),
        structure_stop=Decimal(stop),
    )

    assert (decision.stop_price is not None) is accepted
    assert (decision.reasons == ()) is accepted


def test_structure_stop_rejects_missing_or_nonpositive_risk() -> None:
    profile = build_five_day_return_profiles()[1]

    missing = resolve_profile_stop(profile, Decimal("10"), None)
    above_entry = resolve_profile_stop(profile, Decimal("10"), Decimal("10.01"))

    assert missing.stop_price is None
    assert missing.reasons == ("STRUCTURE_STOP_UNAVAILABLE",)
    assert above_entry.stop_price is None
    assert above_entry.reasons == ("RISK_DISTANCE_OUT_OF_RANGE",)


def _atr_bars() -> tuple[BuyPointBar, ...]:
    start = date(2026, 7, 1)
    return tuple(
        BuyPointBar(
            trade_date=start + timedelta(days=index),
            open=Decimal("9.80"),
            high=Decimal("9.90"),
            low=Decimal("9.70"),
            close=Decimal("9.80"),
            pct_chg=Decimal("0"),
            amount_qian=Decimal("200000"),
        )
        for index in range(20)
    )


def _setup(analysis_date: date) -> DetectedSetup:
    return DetectedSetup(
        code="600001",
        setup_type=SetupType.TREND_PULLBACK,
        analysis_date=analysis_date,
        structure_start=analysis_date - timedelta(days=5),
        structure_high=Decimal("10.20"),
        structure_low=Decimal("9.00"),
        quality=Decimal("0.80"),
        reasons=(),
        metrics={},
    )


def test_structure_atr_stop_ignores_bars_after_the_signal_date() -> None:
    bars = _atr_bars()
    setup = _setup(bars[-1].trade_date)
    future = replace(
        bars[-1],
        trade_date=bars[-1].trade_date + timedelta(days=1),
        high=Decimal("20"),
        low=Decimal("1"),
    )

    assert structure_atr_stop(setup, bars) == Decimal("8.96")
    assert structure_atr_stop(setup, (*bars, future)) == Decimal("8.96")


def test_structure_atr_stop_requires_fourteen_signal_time_bars() -> None:
    bars = _atr_bars()[:13]

    assert structure_atr_stop(_setup(bars[-1].trade_date), bars) is None
