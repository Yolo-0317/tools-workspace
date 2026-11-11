from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.public_challenger_execution import (
    ChallengerTrade,
)
from stock_ai.buy_point_selection.public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    ChallengerSignal,
)
from stock_ai.buy_point_selection.public_challenger_validation import (
    ChallengerObservation,
    V3ComparableDay,
    compare_with_v3,
    evaluate_execution_segment,
    evaluate_portfolio_metrics,
    evaluate_reference_track,
    moving_block_bootstrap_interval,
)


def _weekday_dates(count: int) -> tuple[date, ...]:
    values: list[date] = []
    current = date(2025, 1, 2)
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def _signal(
    code: str,
    signal_date: date,
    *,
    sector: str,
    track_id: str = EXECUTION_TRACK,
    bucket: str | None = None,
) -> ChallengerSignal:
    return ChallengerSignal(
        track_id=track_id,
        signal_date=signal_date,
        code=code,
        sector_code=sector,
        matched_index_id="sh.000001",
        signal_close=Decimal("10"),
        formation_return=Decimal("-0.10"),
        residual_5d=(
            Decimal("-0.20") if track_id == EXECUTION_TRACK else None
        ),
        market_percentile=Decimal("0.01"),
        sector_percentile=Decimal("0.01"),
        reference_bucket=bucket,
        in_candidate_pool=bucket != "WINNER",
    )


def _observation(
    *,
    code: str,
    sector: str,
    signal_date: date,
    resolution_date: date,
    net_return: str,
    status: str,
    track_id: str = EXECUTION_TRACK,
    bucket: str | None = None,
) -> ChallengerObservation:
    signal = _signal(
        code,
        signal_date,
        sector=sector,
        track_id=track_id,
        bucket=bucket,
    )
    trade = ChallengerTrade(
        track_id=track_id,
        signal_date=signal_date,
        status=status,
        entry_date=signal_date,
        entry_price=Decimal("10"),
        exit_date=resolution_date,
        exit_price=Decimal("10") * (Decimal("1") + Decimal(net_return)),
        stop_price=Decimal("9.7") if track_id == EXECUTION_TRACK else None,
        net_return=Decimal(net_return),
        mfe=Decimal("0.03"),
        mae=Decimal("0.01"),
        reasons=(),
    )
    return ChallengerObservation(signal, trade, True, resolution_date)


def _qualifying_observations(count: int = 40) -> tuple[ChallengerObservation, ...]:
    dates = _weekday_dates(126)
    rows: list[ChallengerObservation] = []
    for index in range(count):
        winning = index % 4 != 0
        rows.append(
            _observation(
                code=f"60{index:04d}",
                sector=f"S{index % 10}",
                signal_date=dates[index * 3],
                resolution_date=dates[index * 3],
                net_return="0.02" if winning else "-0.01",
                status="TIME_EXIT_GAIN" if winning else "STOPPED",
            )
        )
    return tuple(rows)


def test_execution_segment_requires_every_frozen_threshold() -> None:
    metrics = evaluate_execution_segment(
        _qualifying_observations(),
        trading_dates=_weekday_dates(126),
        segment="VALIDATION",
    )

    assert metrics.triggered_resolved == 40
    assert metrics.qualifies is True
    assert metrics.reasons == ()


@pytest.mark.parametrize(
    ("mutation", "reason"),
    (
        ("SAMPLES", "SEGMENT_SAMPLES_TOO_LOW"),
        ("EXPECTANCY", "NON_POSITIVE_EXPECTANCY"),
        ("PROFIT_FACTOR", "PROFIT_FACTOR_TOO_LOW"),
        ("WILSON", "WILSON_LOWER_TOO_LOW"),
        ("STOP", "STOP_RATE_TOO_HIGH"),
        ("WINDOW", "POSITIVE_WINDOW_RATIO_TOO_LOW"),
        ("DRAWDOWN", "MAXIMUM_DRAWDOWN_TOO_HIGH"),
    ),
)
def test_execution_segment_fails_each_independent_threshold(
    mutation: str,
    reason: str,
) -> None:
    calendar = _weekday_dates(126)
    rows = list(_qualifying_observations())
    if mutation == "SAMPLES":
        rows = rows[:29]
    elif mutation == "EXPECTANCY":
        rows = [
            replace(
                row,
                trade=replace(
                    row.trade,
                    status="TIME_EXIT_LOSS",
                    net_return=Decimal("-0.01"),
                ),
            )
            for row in rows
        ]
    elif mutation in {"PROFIT_FACTOR", "WILSON"}:
        for index, row in enumerate(rows):
            positive = index < (20 if mutation == "PROFIT_FACTOR" else 18)
            rows[index] = replace(
                row,
                trade=replace(
                    row.trade,
                    status="TIME_EXIT_GAIN" if positive else "TIME_EXIT_LOSS",
                    net_return=Decimal("0.01" if positive else "-0.01"),
                ),
            )
    elif mutation == "STOP":
        for index, row in enumerate(rows):
            if index < 17:
                rows[index] = replace(
                    row,
                    trade=replace(row.trade, status="STOPPED"),
                )
    elif mutation == "WINDOW":
        rows = [
            replace(
                row,
                resolution_date=calendar[0],
                trade=replace(row.trade, exit_date=calendar[0]),
            )
            for row in rows
        ]
    elif mutation == "DRAWDOWN":
        for index, row in enumerate(rows):
            if index < 6:
                rows[index] = replace(
                    row,
                    trade=replace(
                        row.trade,
                        status="TIME_EXIT_LOSS",
                        net_return=Decimal("-0.02"),
                    ),
                )

    metrics = evaluate_execution_segment(
        rows,
        trading_dates=calendar,
        segment="VALIDATION",
    )

    assert reason in metrics.reasons


def test_positive_long_short_spread_cannot_rescue_negative_long_only_return() -> None:
    dates = _weekday_dates(4)
    observations = (
        _observation(
            code="600001",
            sector="S1",
            signal_date=dates[0],
            resolution_date=dates[1],
            net_return="-0.01",
            status="TIME_EXIT_LOSS",
            track_id=CONTRARIAN_TRACK,
            bucket="LOSER",
        ),
        _observation(
            code="600002",
            sector="S2",
            signal_date=dates[0],
            resolution_date=dates[1],
            net_return="-0.03",
            status="TIME_EXIT_LOSS",
            track_id=CONTRARIAN_TRACK,
            bucket="WINNER",
        ),
    )

    metrics = evaluate_reference_track(observations)

    assert metrics.long_short_spread == Decimal("0.02")
    assert metrics.long_only_net_expectancy == Decimal("-0.01")
    assert metrics.long_only_eligible is False


def test_portfolio_concentration_thresholds_are_independent() -> None:
    rows = _qualifying_observations(40)

    diversified = evaluate_portfolio_metrics(rows)
    concentrated = evaluate_portfolio_metrics(
        tuple(
            replace(
                row,
                signal=replace(row.signal, code="600001", sector_code="S1"),
            )
            for row in rows
        )
    )

    assert diversified.qualifies is True
    assert concentrated.qualifies is False
    assert "STOCK_TRADE_CONCENTRATION_TOO_HIGH" in concentrated.reasons
    assert "SECTOR_TRADE_CONCENTRATION_TOO_HIGH" in concentrated.reasons


def test_bootstrap_is_deterministic_for_same_fingerprint() -> None:
    differences = tuple(
        Decimal("0.01") if index % 2 else Decimal("-0.005")
        for index in range(20)
    )

    first = moving_block_bootstrap_interval(
        differences,
        block_size=5,
        samples=10_000,
        seed_material="abc",
    )
    second = moving_block_bootstrap_interval(
        differences,
        block_size=5,
        samples=10_000,
        seed_material="abc",
    )

    assert first == second
    assert first[0] <= first[1]


def _v3_calendar(
    challenger: tuple[ChallengerObservation, ...],
    *,
    return_builder,
    shared_count: int = 0,
) -> tuple[V3ComparableDay, ...]:
    observations_by_date = {row.signal.signal_date: row for row in challenger}
    rows: list[V3ComparableDay] = []
    shared_dates = set(sorted(observations_by_date)[:shared_count])
    for index, trade_date in enumerate(_weekday_dates(126)):
        observation = observations_by_date.get(trade_date)
        if observation is None:
            rows.append(V3ComparableDay(trade_date, frozenset(), Decimal("0")))
            continue
        key = (
            observation.signal.code
            if trade_date in shared_dates
            else f"V3-{index:03d}"
        )
        rows.append(
            V3ComparableDay(
                trade_date,
                frozenset({key}),
                return_builder(observation, index),
            )
        )
    return tuple(rows)


def test_compare_without_v3_uses_explicit_validation_calendar() -> None:
    calendar = _weekday_dates(126)

    assessment = compare_with_v3(
        challenger=_qualifying_observations(),
        v3_days=None,
        trading_dates=calendar,
        segment="VALIDATION",
        input_fingerprint="fingerprint-validation-calendar",
    )

    assert assessment.execution_metrics.segment == "VALIDATION"
    assert assessment.execution_metrics.positive_window_ratio == Decimal("1")
    assert assessment.verdict == "INCONCLUSIVE"
    assert assessment.reasons == ("V3_COMPARABLE_MISSING",)


def test_compare_rejects_v3_calendar_mismatch() -> None:
    calendar = _weekday_dates(126)
    v3_days = _v3_calendar(
        _qualifying_observations(),
        return_builder=lambda _row, _index: Decimal("0"),
    )

    with pytest.raises(ValueError, match="V3_CALENDAR_MISMATCH"):
        compare_with_v3(
            challenger=_qualifying_observations(),
            v3_days=v3_days[:-1],
            trading_dates=calendar,
            segment="TEST",
            input_fingerprint="fingerprint-calendar-mismatch",
        )


def _negative_challenger() -> tuple[ChallengerObservation, ...]:
    return tuple(
        replace(
            row,
            trade=replace(
                row.trade,
                status="TIME_EXIT_LOSS",
                net_return=Decimal("-0.01"),
            ),
        )
        for row in _qualifying_observations()
    )


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        ("WINS", "CHALLENGER_WINS"),
        ("COMPLEMENTARY", "COMPLEMENTARY"),
        ("V3", "V3_RETAINS"),
        ("MISSING", "INCONCLUSIVE"),
    ),
)
def test_frozen_verdicts(case: str, expected: str) -> None:
    challenger = (
        _negative_challenger()
        if case == "V3"
        else _qualifying_observations()
    )
    if case == "MISSING":
        v3_days = None
    elif case == "WINS":
        v3_days = _v3_calendar(
            challenger,
            return_builder=lambda row, _: (
                row.trade.net_return - Decimal("0.005")
            ),
        )
    elif case == "COMPLEMENTARY":
        paired_index = {row.signal.signal_date: index for index, row in enumerate(challenger)}
        v3_days = _v3_calendar(
            challenger,
            shared_count=10,
            return_builder=lambda row, _: (
                row.trade.net_return
                + (
                    Decimal("0.01")
                    if paired_index[row.signal.signal_date] % 2
                    else Decimal("-0.01")
                )
            ),
        )
    else:
        v3_days = _v3_calendar(
            challenger,
            return_builder=lambda _row, index: (
                Decimal("0.02") if index % 4 != 0 else Decimal("-0.01")
            ),
        )

    assessment = compare_with_v3(
        challenger=challenger,
        v3_days=v3_days,
        trading_dates=(
            tuple(row.signal_date for row in v3_days)
            if v3_days is not None
            else _weekday_dates(126)
        ),
        segment="TEST",
        input_fingerprint=f"fingerprint-{case}",
    )

    assert assessment.verdict == expected
    if case == "COMPLEMENTARY":
        assert assessment.paired is not None
        assert assessment.paired.jaccard is not None
        assert assessment.paired.jaccard <= Decimal("0.50")
        assert assessment.paired.incremental_resolved == 30
