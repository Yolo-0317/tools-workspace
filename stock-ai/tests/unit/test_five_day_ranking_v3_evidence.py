from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3_evidence import (
    build_v3_evidence_windows,
)

from five_day_ranking_v3_fixtures import (
    make_v3_observation,
    make_v3_plan,
    make_v3_research_review,
    weekday_dates,
)


START = date(2023, 1, 2)


def _profile_stats(values):
    return next(value for key, value in values.items() if key.level == "PROFILE")


def test_v3_shared_research_fixture_preserves_split_and_safety_flags() -> None:
    observation = make_v3_observation(make_v3_plan(START))

    review = make_v3_research_review((observation,))

    assert tuple(
        len(segment)
        for segment in (
            review.split.train,
            review.split.validation,
            review.split.test,
        )
    ) == (378, 126, 126)
    assert review.observations == (observation,)
    assert review.point_in_time_complete is True
    assert review.test_outcomes_read is False
    assert observation.plan.trade_permission == "NO-TRADE"


def test_v3_builds_four_profile_isolated_hierarchy_levels() -> None:
    dates = weekday_dates(140)
    first = make_v3_observation(make_v3_plan(dates[5]))
    second = make_v3_observation(
        make_v3_plan(
            dates[6],
            profile_id="PULLBACK_RECLAIM__FIXED_3_PERCENT",
        )
    )

    windows = build_v3_evidence_windows(
        (first, second),
        trading_dates=dates,
    )

    assert {key.level for key in windows.full} == {
        "PROFILE",
        "SETUP",
        "MARKET",
        "SECTOR",
    }
    assert all(
        value.key.profile_id == key.profile_id
        for key, value in windows.full.items()
    )
    assert len({key.profile_id for key in windows.full}) == 2


def test_v3_recent_window_uses_last_126_sessions_only() -> None:
    dates = weekday_dates(252)
    old = make_v3_observation(make_v3_plan(dates[10]))
    recent = make_v3_observation(make_v3_plan(dates[-10]))

    windows = build_v3_evidence_windows(
        (old, recent),
        trading_dates=dates,
    )

    assert windows.full_dates == tuple(dates)
    assert windows.recent_dates == tuple(dates[-126:])
    assert sum(
        value.resolved_samples
        for value in windows.recent.values()
        if value.key.level == "PROFILE"
    ) == 1


def test_v3_summarizes_only_resolved_outcomes_available_by_data_end() -> None:
    dates = weekday_dates(140)
    gain = make_v3_observation(
        make_v3_plan(dates[5]),
        net_return=Decimal("0.03"),
        net_pnl=Decimal("300"),
        mae=Decimal("0.01"),
    )
    loss = make_v3_observation(
        make_v3_plan(dates[6], code="600002"),
        net_return=Decimal("-0.01"),
        net_pnl=Decimal("-100"),
        status="TIME_EXIT_LOSS",
        mae=Decimal("0.02"),
    )
    stopped = make_v3_observation(
        make_v3_plan(dates[7], code="600003"),
        net_return=Decimal("-0.02"),
        net_pnl=Decimal("-100"),
        status="STOPPED",
        mae=Decimal("0.03"),
    )
    future = make_v3_observation(
        make_v3_plan(dates[8], code="600004"),
        net_return=Decimal("0.50"),
        net_pnl=Decimal("5000"),
        resolution_date=dates[-1] + timedelta(days=1),
    )

    windows = build_v3_evidence_windows(
        (gain, loss, stopped, future),
        trading_dates=dates,
    )
    stats = _profile_stats(windows.full)

    assert stats.total_plans == 4
    assert stats.resolved_samples == 3
    assert stats.net_expectancy == Decimal("0")
    assert stats.profit_factor == Decimal("1.5")
    assert stats.stop_rate == Decimal("1") / Decimal("3")
    assert stats.mae_p75 == Decimal("0.03")


@pytest.mark.parametrize(
    "trading_dates",
    ((), (START, START)),
)
def test_v3_rejects_empty_or_duplicate_trading_dates(
    trading_dates: tuple[date, ...],
) -> None:
    with pytest.raises(ValueError, match="trading_dates"):
        build_v3_evidence_windows((), trading_dates=trading_dates)
