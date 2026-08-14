from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from stock_ai.buy_point_selection.historical_replay_runtime import (
    build_historical_market_snapshots,
    discover_historical_plans,
)
from stock_ai.buy_point_selection.models import BuyPointBar, MarketSnapshot, SetupType
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    SectorMembership,
)
from stock_ai.buy_point_selection.reference_sources import IndexBar


def _bar(
    trade_date: date,
    close: Decimal,
    *,
    previous: Decimal | None = None,
    amount: Decimal = Decimal("120000"),
) -> BuyPointBar:
    prior = previous if previous is not None else close
    return BuyPointBar(
        trade_date=trade_date,
        open=close,
        high=close + Decimal("0.08"),
        low=close - Decimal("0.08"),
        close=close,
        pct_chg=(close / prior - Decimal("1")) * Decimal("100"),
        amount_qian=amount,
    )


def test_market_snapshots_use_only_dated_index_and_equity_rows() -> None:
    """Catches future index closes or current market state leaking into a historical day."""
    start = date(2024, 1, 2)
    dates = tuple(start + timedelta(days=index) for index in range(21))
    index_codes = ("sh.000001", "sz.399001", "sh.000688")
    index_bars = {
        code: tuple(
            IndexBar(code, day, Decimal("3000") + index, Decimal("0.1"))
            for index, day in enumerate(dates)
        )
        + (
            IndexBar(
                code,
                dates[-1] + timedelta(days=1),
                Decimal("1"),
                Decimal("-99"),
            ),
        )
        for code in index_codes
    }
    equities = {
        "600001": tuple(
            replace(
                _bar(day, Decimal("10") + Decimal(index) / 100),
                pct_chg=Decimal("0.1"),
            )
            for index, day in enumerate(dates)
        ),
        "600002": tuple(
            replace(
                _bar(day, Decimal("10") - Decimal(index) / 200),
                pct_chg=Decimal("-0.1"),
            )
            for index, day in enumerate(dates)
        ),
    }

    snapshots = build_historical_market_snapshots(dates, equities, index_bars)

    current = snapshots[dates[-1]]
    assert current.complete
    assert current.indexes_above_ma20 == 3
    assert current.breadth_pct == 50.0
    assert current.amount_ratio == 1.0


def test_market_snapshot_fails_closed_when_one_benchmark_is_missing() -> None:
    """Catches a two-index partial regime being labeled complete."""
    start = date(2024, 1, 2)
    dates = tuple(start + timedelta(days=index) for index in range(20))
    index_bars = {
        code: tuple(
            IndexBar(code, day, Decimal("3000") + index, Decimal("0.1"))
            for index, day in enumerate(dates)
        )
        for code in ("sh.000001", "sz.399001")
    }

    current = build_historical_market_snapshots(dates, {}, index_bars)[dates[-1]]

    assert not current.complete


def _first_launch_bars(code_offset: int = 0) -> tuple[BuyPointBar, ...]:
    start = date(2024, 1, 2)
    closes = [Decimal("10.00")] * 57 + [
        Decimal("10.40"),
        Decimal("10.35"),
        Decimal("10.40"),
    ]
    amounts = [Decimal("100000")] * 57 + [
        Decimal("160000"),
        Decimal("110000"),
        Decimal("105000"),
    ]
    bars = [
        _bar(
            start + timedelta(days=index),
            close,
            previous=closes[index - 1] if index else close,
            amount=amounts[index],
        )
        for index, close in enumerate(closes)
    ]
    bars[57] = replace(
        bars[57],
        open=Decimal("10.02"),
        high=Decimal("10.43"),
        low=Decimal("10.00"),
    )
    bars[58] = replace(bars[58], high=Decimal("10.42"))
    bars[59] = replace(bars[59], high=Decimal("10.42"))
    return tuple(bars)


def test_discovery_builds_plan_with_actual_second_future_session() -> None:
    """Catches historical discovery bypassing production gates or using weekday expiry."""
    panels = {
        f"60000{index}": _first_launch_bars(index)
        for index in range(1, 7)
    }
    signal = next(iter(panels.values()))[-1].trade_date
    first = signal + timedelta(days=3)
    second = signal + timedelta(days=10)
    trading_dates = tuple(bar.trade_date for bar in next(iter(panels.values()))) + (
        first,
        second,
    )
    memberships = tuple(
        SectorMembership(
            code,
            "S1",
            "测试行业",
            date(2020, 1, 1),
            None,
            "test",
        )
        for code in panels
    )

    result = discover_historical_plans(
        signal_dates=(signal,),
        trading_dates=trading_dates,
        bars_by_code=panels,
        memberships=memberships,
        risk_flags=(),
        coverage_by_date={signal: ReferenceCoverage(signal, True, True, True)},
        market_snapshots={signal: MarketSnapshot(3, 60.0, 1.0, True)},
    )

    assert result.plans
    assert all(plan.plan.setup_type is SetupType.FIRST_LAUNCH_PULLBACK for plan in result.plans)
    assert all(plan.plan.valid_through_trade_date == second for plan in result.plans)
    assert all(plan.sector_resonating for plan in result.plans)
