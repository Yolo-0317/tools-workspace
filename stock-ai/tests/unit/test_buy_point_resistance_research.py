from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from stock_ai.buy_point_selection.case_review import CaseCandidate, OpportunityEpisode
from stock_ai.buy_point_selection.models import BuyPointBar, DetectedSetup, SetupType
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.resistance_research import (
    LEGACY_ANY_HIGH,
    LOCAL_PIVOT_HIGH,
    analyze_significant_resistance,
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
