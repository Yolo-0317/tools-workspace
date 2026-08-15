from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.case_review import CaseCandidate, OpportunityEpisode
from stock_ai.buy_point_selection.models import BuyPointBar, DetectedSetup, SetupType
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.resistance_research import (
    INCOMPLETE,
    LEGACY_ANY_HIGH,
    LEVEL_AT_OR_ABOVE_2R,
    LEVEL_BELOW_2R,
    LOCAL_PIVOT_HIGH,
    NO_LEVEL,
    REPEATED_PIVOT_CLUSTER,
    ResistanceVariantProfile,
    analyze_significant_resistance,
    repeated_pivot_resistance,
    resistance_evidence_basis,
)


SIGNAL = date(2026, 8, 3)


def _episode() -> OpportunityEpisode:
    setup = DetectedSetup(
        "600001",
        SetupType.TREND_PULLBACK,
        SIGNAL,
        SIGNAL - timedelta(days=5),
        Decimal("9.99"),
        Decimal("9.00"),
        Decimal("0.40"),
        (),
        {},
    )
    candidate = CaseCandidate(
        "600001",
        SIGNAL,
        setup,
        PricePlan(
            "structure-1",
            "600001",
            setup.setup_type,
            SIGNAL,
            Decimal("9.80"),
            Decimal("10.00"),
            Decimal("9.00"),
            Decimal("12.00"),
            Decimal("1.00"),
            Decimal("2.00"),
            100,
            SIGNAL + timedelta(days=2),
        ),
        "NEAR_MISS",
        "INSUFFICIENT_TWO_R_SPACE",
        (Decimal("0.20"), Decimal("-0.40"), Decimal("-200000"), "600001"),
    )
    return OpportunityEpisode(
        "episode-1",
        candidate,
        (SIGNAL,),
        ("NEAR_MISS",),
    )


def _bars() -> tuple[BuyPointBar, ...]:
    start = SIGNAL - timedelta(days=59)
    values = tuple(
        BuyPointBar(
            start + timedelta(days=index),
            Decimal("9.80"),
            Decimal("9.90"),
            Decimal("9.70"),
            Decimal("9.80"),
            Decimal("0"),
            Decimal("200000"),
        )
        for index in range(60)
    )
    mutable = list(values)
    mutable[30] = replace(mutable[30], high=Decimal("12.20"))
    mutable[-1] = replace(mutable[-1], high=Decimal("10.20"))
    return tuple(mutable)


def _flat_bars() -> tuple[BuyPointBar, ...]:
    start = SIGNAL - timedelta(days=59)
    return tuple(
        BuyPointBar(
            start + timedelta(days=index),
            Decimal("9.80"),
            Decimal("9.90"),
            Decimal("9.70"),
            Decimal("9.80"),
            Decimal("0"),
            Decimal("200000"),
        )
        for index in range(60)
    )


def test_repeated_pivot_primitive_ignores_future_bars() -> None:
    bars = list(_flat_bars())
    bars[10] = replace(bars[10], high=Decimal("12.10"))
    bars[20] = replace(bars[20], high=Decimal("12.20"))
    future = replace(
        bars[-1],
        trade_date=SIGNAL + timedelta(days=1),
        high=Decimal("10.01"),
    )

    baseline = repeated_pivot_resistance(Decimal("10"), SIGNAL, tuple(bars))
    with_future = repeated_pivot_resistance(
        Decimal("10"), SIGNAL, (*bars, future)
    )

    assert with_future == baseline
    assert baseline.complete
    assert baseline.level == Decimal("12.15")
    assert baseline.touch_count == 2


def test_repeated_pivot_primitive_fails_closed_on_incomplete_history() -> None:
    bars = list(_flat_bars())
    duplicate = tuple(
        replace(value, trade_date=bars[8].trade_date) if index == 9 else value
        for index, value in enumerate(bars)
    )

    too_short = repeated_pivot_resistance(
        Decimal("10"), SIGNAL, tuple(bars[1:])
    )
    duplicated = repeated_pivot_resistance(Decimal("10"), SIGNAL, duplicate)

    assert not too_short.complete
    assert too_short.level is None
    assert too_short.touch_count == 0
    assert not duplicated.complete


def test_repeated_pivot_primitive_rejects_nearby_touches() -> None:
    bars = list(_flat_bars())
    bars[10] = replace(bars[10], high=Decimal("12.10"))
    bars[12] = replace(bars[12], high=Decimal("12.10"))

    evidence = repeated_pivot_resistance(Decimal("10"), SIGNAL, tuple(bars))

    assert evidence.complete
    assert evidence.level is None
    assert evidence.touch_count == 0


def test_repeated_pivot_primitive_uses_price_tolerance_when_larger() -> None:
    bars = [
        replace(
            value,
            open=Decimal("99.80"),
            high=Decimal("99.90"),
            low=Decimal("99.70"),
            close=Decimal("99.80"),
        )
        for value in _flat_bars()
    ]
    bars[10] = replace(bars[10], high=Decimal("100.10"))
    bars[20] = replace(bars[20], high=Decimal("100.50"))

    evidence = repeated_pivot_resistance(Decimal("100"), SIGNAL, tuple(bars))

    assert evidence.complete
    assert evidence.level == Decimal("100.30")
    assert evidence.touch_count == 2


def test_repeated_pivot_primitive_reports_complete_without_a_cluster() -> None:
    evidence = repeated_pivot_resistance(
        Decimal("10"), SIGNAL, _flat_bars()
    )

    assert evidence.complete
    assert evidence.level is None
    assert evidence.touch_count == 0


def test_profile_separates_any_high_from_a_two_sided_local_pivot() -> None:
    """Catches an ordinary endpoint high being mistaken for a local pivot."""
    profile = analyze_significant_resistance(_episode(), _bars())
    variants = {value.variant: value for value in profile.variants}

    assert profile.complete
    assert variants[LEGACY_ANY_HIGH].level == Decimal("10.20")
    assert variants[LEGACY_ANY_HIGH].effective_resistance_r == Decimal("0.20")
    assert not variants[LEGACY_ANY_HIGH].passes_two_r
    assert variants[LOCAL_PIVOT_HIGH].level == Decimal("12.20")
    assert variants[LOCAL_PIVOT_HIGH].effective_resistance_r == Decimal("2.20")
    assert variants[LOCAL_PIVOT_HIGH].passes_two_r


def test_profile_ignores_bars_after_the_signal_date() -> None:
    future = replace(
        _bars()[-1],
        trade_date=SIGNAL + timedelta(days=1),
        high=Decimal("10.01"),
    )

    baseline = analyze_significant_resistance(_episode(), _bars())
    with_future = analyze_significant_resistance(_episode(), (*_bars(), future))

    assert with_future == baseline


def test_local_pivot_excludes_a_one_sided_endpoint_high() -> None:
    bars = list(_bars())
    bars[30] = replace(bars[30], high=Decimal("9.90"))
    bars[-1] = replace(bars[-1], high=Decimal("12.20"))

    profile = analyze_significant_resistance(_episode(), tuple(bars))
    variants = {value.variant: value for value in profile.variants}

    assert variants[LEGACY_ANY_HIGH].level == Decimal("12.20")
    assert variants[LOCAL_PIVOT_HIGH].level is None


def test_local_pivot_counts_equal_height_double_tops() -> None:
    bars = list(_bars())
    bars[20] = replace(bars[20], high=Decimal("12.20"))
    bars[40] = replace(bars[40], high=Decimal("12.20"))

    profile = analyze_significant_resistance(_episode(), tuple(bars))
    variants = {value.variant: value for value in profile.variants}

    assert variants[LOCAL_PIVOT_HIGH].level == Decimal("12.20")
    assert variants[LOCAL_PIVOT_HIGH].touch_count == 3


def test_repeated_pivot_cluster_uses_the_mean_of_independent_touches() -> None:
    bars = list(_flat_bars())
    bars[10] = replace(bars[10], high=Decimal("12.10"))
    bars[20] = replace(bars[20], high=Decimal("12.20"))

    profile = analyze_significant_resistance(_episode(), tuple(bars))
    variants = {value.variant: value for value in profile.variants}

    assert profile.atr14 == Decimal("0.20")
    assert profile.tolerance == Decimal("0.100")
    assert variants[REPEATED_PIVOT_CLUSTER].level == Decimal("12.15")
    assert variants[REPEATED_PIVOT_CLUSTER].touch_count == 2
    assert variants[REPEATED_PIVOT_CLUSTER].effective_resistance_r == Decimal("2.15")
    assert variants[REPEATED_PIVOT_CLUSTER].passes_two_r


def test_incomplete_history_fails_closed_for_every_variant() -> None:
    profile = analyze_significant_resistance(_episode(), _flat_bars()[1:])

    assert not profile.complete
    assert all(not value.passes_two_r for value in profile.variants)
    assert all(value.level is None for value in profile.variants)


def test_repeated_cluster_rejects_touches_less_than_three_bars_apart() -> None:
    bars = list(_flat_bars())
    bars[10] = replace(bars[10], high=Decimal("12.10"))
    bars[12] = replace(bars[12], high=Decimal("12.10"))

    profile = analyze_significant_resistance(_episode(), tuple(bars))
    variants = {value.variant: value for value in profile.variants}

    assert variants[REPEATED_PIVOT_CLUSTER].level is None
    assert variants[REPEATED_PIVOT_CLUSTER].touch_count == 0


def test_repeated_cluster_rejects_prices_outside_tolerance() -> None:
    bars = list(_flat_bars())
    bars[10] = replace(bars[10], high=Decimal("12.10"))
    bars[20] = replace(bars[20], high=Decimal("12.21"))

    profile = analyze_significant_resistance(_episode(), tuple(bars))
    variants = {value.variant: value for value in profile.variants}

    assert profile.tolerance == Decimal("0.100")
    assert variants[REPEATED_PIVOT_CLUSTER].level is None


def test_repeated_cluster_selects_the_lower_valid_resistance_zone() -> None:
    bars = list(_flat_bars())
    for index, high in (
        (8, "12.10"),
        (18, "12.20"),
        (32, "13.00"),
        (42, "13.05"),
    ):
        bars[index] = replace(bars[index], high=Decimal(high))

    profile = analyze_significant_resistance(_episode(), tuple(bars))
    variants = {value.variant: value for value in profile.variants}

    assert variants[REPEATED_PIVOT_CLUSTER].level == Decimal("12.15")
    assert variants[REPEATED_PIVOT_CLUSTER].touch_count == 2


@pytest.mark.parametrize(
    ("level", "passes"),
    (("11.99", False), ("12.00", True), ("12.01", True)),
)
def test_local_pivot_two_r_boundary_is_inclusive(level: str, passes: bool) -> None:
    bars = list(_flat_bars())
    bars[30] = replace(bars[30], high=Decimal(level))

    profile = analyze_significant_resistance(_episode(), tuple(bars))
    variants = {value.variant: value for value in profile.variants}

    assert variants[LOCAL_PIVOT_HIGH].passes_two_r is passes


def test_no_resistance_is_complete_and_passes_by_absence() -> None:
    profile = analyze_significant_resistance(_episode(), _flat_bars())

    assert profile.complete
    assert all(value.level is None for value in profile.variants)
    assert all(value.passes_two_r for value in profile.variants)


def test_duplicate_trade_dates_fail_closed() -> None:
    bars = list(_flat_bars())
    bars[10] = replace(bars[10], trade_date=bars[9].trade_date)

    profile = analyze_significant_resistance(_episode(), tuple(bars))

    assert not profile.complete
    assert all(not value.passes_two_r for value in profile.variants)


def test_resistance_evidence_basis_keeps_pass_reasons_separate() -> None:
    """Catches no-level passes being pooled with observed levels above 2R."""
    level_pass = ResistanceVariantProfile(
        LOCAL_PIVOT_HIGH,
        Decimal("12.20"),
        Decimal("2.20"),
        True,
        1,
    )
    no_level = ResistanceVariantProfile(
        REPEATED_PIVOT_CLUSTER,
        None,
        None,
        True,
        0,
    )
    below_level = ResistanceVariantProfile(
        LEGACY_ANY_HIGH,
        Decimal("10.20"),
        Decimal("0.20"),
        False,
        1,
    )

    assert resistance_evidence_basis(True, level_pass) == LEVEL_AT_OR_ABOVE_2R
    assert resistance_evidence_basis(True, no_level) == NO_LEVEL
    assert resistance_evidence_basis(True, below_level) == LEVEL_BELOW_2R
    assert resistance_evidence_basis(False, no_level) == INCOMPLETE
    assert level_pass.passes_two_r
    assert no_level.passes_two_r
    assert not below_level.passes_two_r
