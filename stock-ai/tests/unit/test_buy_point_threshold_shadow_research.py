from __future__ import annotations

from dataclasses import fields, replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.models import BuyPointBar, SelectionPolicy, SetupType
from stock_ai.buy_point_selection.threshold_shadow_research import (
    ThresholdProfile,
    build_threshold_profiles,
    generate_threshold_shadow_setups,
    profile_matrix_hash,
)


SIGNAL_DATE = date(2026, 8, 3)


def _single_width_failure_platform() -> tuple[BuyPointBar, ...]:
    bars = []
    for index in range(60):
        close = Decimal("10.40") + Decimal(index) * Decimal("0.01")
        high = close + Decimal("0.04")
        low = close - Decimal("0.04")
        amount = Decimal("200000")
        if index == 30:
            low = Decimal("10.00")
        if index == 45:
            high = Decimal("11.30")
        if index >= 50:
            high = close + Decimal("0.02")
            low = close - Decimal("0.02")
        if index >= 55:
            amount = Decimal("120000")
        bars.append(
            BuyPointBar(
                SIGNAL_DATE - timedelta(days=59 - index),
                close,
                high,
                low,
                close,
                Decimal("0.10"),
                amount,
            )
        )
    return tuple(bars)


def test_profile_matrix_has_48_unique_single_field_relaxations() -> None:
    """Catches a missing ladder rung or a profile mutating multiple gates."""
    profiles = build_threshold_profiles()

    assert len(profiles) == 48
    assert len({value.profile_id for value in profiles}) == 48
    profile = next(
        value
        for value in profiles
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    assert profile == ThresholdProfile(
        profile_id="PRE_BREAKOUT:platform_width_max:UPPER:0.10",
        setup_type=SetupType.PRE_BREAKOUT,
        policy_field="platform_width_max",
        direction="UPPER",
        relaxation_rate=Decimal("0.10"),
        formal_value=Decimal("0.12"),
        shadow_value=Decimal("0.1320"),
        failure_reason="PLATFORM_WIDTH_WIDE",
        metric_name="platform_width",
    )

    formal = SelectionPolicy()
    shadow = replace(formal, **{profile.policy_field: profile.shadow_value})
    changed = {
        field.name
        for field in fields(SelectionPolicy)
        if getattr(formal, field.name) != getattr(shadow, field.name)
    }
    assert changed == {"platform_width_max"}


def test_lower_bound_profile_relaxes_only_downward() -> None:
    """Catches a lower-bound profile being widened in the wrong direction."""
    profile = next(
        value
        for value in build_threshold_profiles()
        if value.policy_field == "trend_return10_min"
        and value.relaxation_rate == Decimal("0.25")
    )

    assert profile.direction == "LOWER"
    assert profile.formal_value == Decimal("0.05")
    assert profile.shadow_value == Decimal("0.0375")


def test_profile_matrix_hash_is_order_independent_and_content_sensitive() -> None:
    """Catches artifact identity ignoring a changed shadow threshold."""
    profiles = build_threshold_profiles()
    changed = replace(profiles[0], shadow_value=Decimal("0.999"))

    assert profile_matrix_hash(tuple(reversed(profiles))) == profile_matrix_hash(
        profiles
    )
    assert profile_matrix_hash((changed, *profiles[1:])) != profile_matrix_hash(
        profiles
    )


def test_single_width_failure_is_admitted_only_by_width_profile() -> None:
    """Catches an unrelated gate being relaxed or a small width miss being lost."""
    profiles = build_threshold_profiles()
    width = next(
        value
        for value in profiles
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    amount = next(
        value
        for value in profiles
        if value.policy_field == "platform_amount_ratio_max"
        and value.relaxation_rate == Decimal("0.10")
    )

    rows = generate_threshold_shadow_setups(
        "600001",
        SIGNAL_DATE,
        _single_width_failure_platform(),
        (width, amount),
    )

    assert [value.profile.profile_id for value in rows] == [width.profile_id]
    assert rows[0].actual_deviation == Decimal("0.01") / Decimal("0.12")
    assert rows[0].executable_shares == 0


def test_forged_or_structural_profile_is_rejected() -> None:
    """Catches callers bypassing the frozen numeric profile allowlist."""
    forged = replace(
        build_threshold_profiles()[0],
        policy_field="max_signal_gain_pct",
        shadow_value=Decimal("9"),
    )

    with pytest.raises(ValueError, match="unsupported threshold profile"):
        generate_threshold_shadow_setups(
            "600001",
            SIGNAL_DATE,
            _single_width_failure_platform(),
            (forged,),
        )


def test_formal_positive_and_multi_failure_shapes_are_not_incremental() -> None:
    """Catches a formal setup or a two-gate miss entering one-gate shadows."""
    width = next(
        value
        for value in build_threshold_profiles()
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    bars = list(_single_width_failure_platform())
    formal = list(bars)
    formal[45] = replace(formal[45], high=Decimal("11.19"))
    multiple = [
        replace(value, amount_qian=Decimal("200000"))
        if index >= 55
        else value
        for index, value in enumerate(bars)
    ]

    assert generate_threshold_shadow_setups(
        "600001", SIGNAL_DATE, formal, (width,)
    ) == ()
    assert generate_threshold_shadow_setups(
        "600001", SIGNAL_DATE, multiple, (width,)
    ) == ()


def test_future_bar_cannot_change_shadow_setup_generation() -> None:
    """Catches outcome prices leaking into profile admission."""
    profile = next(
        value
        for value in build_threshold_profiles()
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    bars = _single_width_failure_platform()
    future = replace(
        bars[-1],
        trade_date=SIGNAL_DATE + timedelta(days=1),
        high=Decimal("99"),
        close=Decimal("90"),
    )

    assert generate_threshold_shadow_setups(
        "600001", SIGNAL_DATE, (*bars, future), (profile,)
    ) == generate_threshold_shadow_setups(
        "600001", SIGNAL_DATE, bars, (profile,)
    )
