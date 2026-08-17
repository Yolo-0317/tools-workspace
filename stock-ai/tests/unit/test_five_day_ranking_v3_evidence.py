from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3_evidence import (
    V3BucketKey,
    V3BucketStats,
    V3EvidenceRejected,
    V3EvidenceWindows,
    build_v3_evidence_windows,
    resolve_v3_candidate_evidence,
)

from five_day_ranking_v3_fixtures import (
    make_v3_observation,
    make_v3_plan,
    make_v3_research_review,
    weekday_dates,
)


START = date(2023, 1, 2)
PROFILE_ID = "BREAKOUT_TRIGGER__STRUCTURE_ATR"


def _hierarchy_keys() -> tuple[V3BucketKey, ...]:
    setup_type = make_v3_plan(START).candidate.setup.setup_type
    return (
        V3BucketKey(level="PROFILE", profile_id=PROFILE_ID),
        V3BucketKey(
            level="SETUP",
            profile_id=PROFILE_ID,
            setup_type=setup_type,
        ),
        V3BucketKey(
            level="MARKET",
            profile_id=PROFILE_ID,
            setup_type=setup_type,
            market_status="ALLOW",
        ),
        V3BucketKey(
            level="SECTOR",
            profile_id=PROFILE_ID,
            setup_type=setup_type,
            market_status="ALLOW",
            sector_resonating=True,
        ),
    )


def _bucket_stats(
    key: V3BucketKey,
    sample_edge: tuple[int, str],
    *,
    data_end: date,
    profit_factor: str | None = "1.5",
    wilson_upper: str = "0.80",
    stop_rate: str = "0.20",
    mae_p75: str = "0.02",
) -> V3BucketStats:
    samples, edge = sample_edge
    return V3BucketStats(
        key=key,
        data_end=data_end,
        total_plans=samples,
        resolved_samples=samples,
        net_expectancy=Decimal(edge),
        profit_factor=(
            Decimal(profit_factor) if profit_factor is not None else None
        ),
        profitable_interval=(Decimal("0.20"), Decimal(wilson_upper)),
        positive_window_ratio=Decimal("0.50"),
        mae_p75=Decimal(mae_p75),
        stop_rate=Decimal(stop_rate),
    )


def _evidence_windows(
    *,
    profile: tuple[int, str],
    setup: tuple[int, str] = (0, "0"),
    market: tuple[int, str] = (0, "0"),
    sector: tuple[int, str] = (0, "0"),
    data_end: date = START - timedelta(days=1),
) -> V3EvidenceWindows:
    keys = _hierarchy_keys()
    samples = (profile, setup, market, sector)
    values = {
        key: _bucket_stats(key, sample, data_end=data_end)
        for key, sample in zip(keys, samples)
    }
    return V3EvidenceWindows(
        full_dates=(data_end,),
        recent_dates=(data_end,),
        full=values,
        recent=values,
    )


def _negative_windows(
    *,
    profile_samples: int,
    child_samples: int,
) -> V3EvidenceWindows:
    return _evidence_windows(
        profile=(profile_samples, "-0.01"),
        setup=(child_samples, "-0.01"),
        market=(child_samples, "-0.01"),
    )


def _stable_negative_windows(
    *,
    full_samples: int,
    recent_samples: int,
    full_edge: str,
    recent_edge: str,
    profit_factor: str | None,
    wilson_upper: str,
) -> V3EvidenceWindows:
    data_end = START - timedelta(days=1)
    profile, setup, market, sector = _hierarchy_keys()

    def values(samples: int, edge: str) -> dict[V3BucketKey, V3BucketStats]:
        return {
            profile: _bucket_stats(
                profile,
                (100, edge),
                data_end=data_end,
                profit_factor=profit_factor,
                wilson_upper=wilson_upper,
            ),
            setup: _bucket_stats(
                setup,
                (samples, edge),
                data_end=data_end,
                profit_factor=profit_factor,
                wilson_upper=wilson_upper,
            ),
            market: _bucket_stats(
                market,
                (samples, edge),
                data_end=data_end,
                profit_factor=profit_factor,
                wilson_upper=wilson_upper,
            ),
            sector: _bucket_stats(
                sector,
                (0, "0"),
                data_end=data_end,
            ),
        }

    return V3EvidenceWindows(
        full_dates=(data_end,),
        recent_dates=(data_end,),
        full=values(full_samples, full_edge),
        recent=values(recent_samples, recent_edge),
    )


def _risk_windows() -> V3EvidenceWindows:
    windows = _evidence_windows(
        profile=(100, "0"),
        setup=(30, "0"),
    )
    profile, setup, _, _ = _hierarchy_keys()
    values = {
        **windows.full,
        profile: _bucket_stats(
            profile,
            (100, "0"),
            data_end=windows.full_dates[-1],
            stop_rate="0.40",
            mae_p75="0.08",
        ),
        setup: _bucket_stats(
            setup,
            (30, "0"),
            data_end=windows.full_dates[-1],
            stop_rate="0.20",
            mae_p75="0.02",
        ),
    }
    return V3EvidenceWindows(
        full_dates=windows.full_dates,
        recent_dates=windows.recent_dates,
        full=values,
        recent=values,
    )


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


def test_v3_child_edge_recursively_shrinks_to_parent() -> None:
    windows = _evidence_windows(
        profile=(100, "0.01"),
        setup=(30, "-0.01"),
    )

    result = resolve_v3_candidate_evidence(
        make_v3_plan(START),
        windows,
        shrinkage_k=30,
    )

    root_edge = Decimal("100") / Decimal("130") * Decimal("0.01")
    expected = (
        Decimal("30") / Decimal("60") * Decimal("-0.01")
        + Decimal("30") / Decimal("60") * root_edge
    )
    assert result.full_edge == expected
    assert result.edge == expected
    assert result.deepest_full_key.level == "SETUP"
    assert result.deepest_recent_key.level == "SETUP"


@pytest.mark.parametrize("shrinkage_k", (30, 60))
def test_v3_missing_child_inherits_profile_root(shrinkage_k: int) -> None:
    windows = _evidence_windows(profile=(100, "0.01"))

    result = resolve_v3_candidate_evidence(
        make_v3_plan(START),
        windows,
        shrinkage_k=shrinkage_k,
    )

    expected = (
        Decimal("100")
        / Decimal(100 + shrinkage_k)
        * Decimal("0.01")
    )
    assert result.full_edge == expected
    assert result.deepest_full_key.level == "PROFILE"


def test_v3_risk_metrics_shrink_children_to_raw_root_values() -> None:
    result = resolve_v3_candidate_evidence(
        make_v3_plan(START),
        _risk_windows(),
        shrinkage_k=30,
    )

    assert result.stop_rate == Decimal("0.30")
    assert result.mae_p75 == Decimal("0.05")


def test_v3_rejects_calibration_ending_on_signal_date() -> None:
    windows = _evidence_windows(
        profile=(100, "0.01"),
        data_end=START,
    )

    with pytest.raises(
        V3EvidenceRejected,
        match="CALIBRATION_NOT_POINT_IN_TIME",
    ):
        resolve_v3_candidate_evidence(
            make_v3_plan(START),
            windows,
            shrinkage_k=30,
        )


def test_v3_rejects_profile_history_below_sixty_samples() -> None:
    with pytest.raises(V3EvidenceRejected, match="PROFILE_HISTORY_TOO_LOW"):
        resolve_v3_candidate_evidence(
            make_v3_plan(START),
            _evidence_windows(profile=(59, "0.01")),
            shrinkage_k=30,
        )


@pytest.mark.parametrize("shrinkage_k", (0, 31))
def test_v3_rejects_unregistered_shrinkage(shrinkage_k: int) -> None:
    with pytest.raises(ValueError, match="shrinkage_k"):
        resolve_v3_candidate_evidence(
            make_v3_plan(START),
            _evidence_windows(profile=(100, "0.01")),
            shrinkage_k=shrinkage_k,
        )


def test_v3_profile_root_alone_cannot_trigger_stable_negative() -> None:
    result = resolve_v3_candidate_evidence(
        make_v3_plan(START),
        _negative_windows(profile_samples=100, child_samples=0),
        shrinkage_k=30,
    )

    assert result.stable_negative is False


def test_v3_stable_negative_requires_parent_child_and_all_boundaries() -> None:
    windows = _stable_negative_windows(
        full_samples=60,
        recent_samples=30,
        full_edge="0",
        recent_edge="0",
        profit_factor="1",
        wilson_upper="0.4999",
    )

    result = resolve_v3_candidate_evidence(
        make_v3_plan(START),
        windows,
        shrinkage_k=60,
    )

    assert result.stable_negative is True


@pytest.mark.parametrize(
    ("override", "value"),
    (
        ("full_samples", 59),
        ("recent_samples", 29),
        ("full_edge", "0.0001"),
        ("recent_edge", "0.0001"),
        ("profit_factor", "1.0001"),
        ("profit_factor", None),
        ("wilson_upper", "0.50"),
    ),
)
def test_v3_stable_negative_boundaries_fail_open(
    override: str,
    value: object,
) -> None:
    inputs: dict[str, object] = {
        "full_samples": 60,
        "recent_samples": 30,
        "full_edge": "0",
        "recent_edge": "0",
        "profit_factor": "1",
        "wilson_upper": "0.4999",
    }
    inputs[override] = value
    windows = _stable_negative_windows(**inputs)

    result = resolve_v3_candidate_evidence(
        make_v3_plan(START),
        windows,
        shrinkage_k=60,
    )

    assert result.stable_negative is False
