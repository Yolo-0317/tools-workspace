from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, localcontext

import pytest

from stock_ai.buy_point_selection.models import BuyPointBar
from stock_ai.buy_point_selection.public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    RESIDUAL_TRACK,
    build_contrarian_signals,
    build_execution_signals,
    build_residual_signals,
    build_sector_return_series,
    estimate_residual_signal,
)
from stock_ai.buy_point_selection.reference_data import SectorMembership


def _dates(count: int, start: date = date(2025, 1, 2)) -> tuple[date, ...]:
    values: list[date] = []
    current = start
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def _bars(code: str, closes: list[Decimal], dates: tuple[date, ...]) -> tuple[BuyPointBar, ...]:
    assert len(closes) == len(dates), code
    rows: list[BuyPointBar] = []
    previous = closes[0]
    for trade_date, close in zip(dates, closes):
        pct_chg = (
            Decimal("0")
            if not rows
            else (close / previous - Decimal("1")) * Decimal("100")
        )
        rows.append(
            BuyPointBar(
                trade_date=trade_date,
                open=close,
                high=close,
                low=close,
                close=close,
                pct_chg=pct_chg,
                amount_qian=Decimal("100000"),
            )
        )
        previous = close
    return tuple(rows)


def _prices_from_returns(
    returns: list[Decimal],
    *,
    initial: Decimal = Decimal("100"),
) -> list[Decimal]:
    values = [initial]
    with localcontext() as context:
        context.prec = 50
        for value in returns:
            values.append(values[-1] * (Decimal("1") + value))
    return values


def _membership(code: str, sector: str, dates: tuple[date, ...]) -> SectorMembership:
    return SectorMembership(
        code=code,
        sector_code=sector,
        sector_name=sector,
        valid_from=dates[0],
        valid_to=None,
        source="TEST",
    )


def test_contrarian_uses_t_minus_5_close_and_stable_code_tie_break() -> None:
    dates = _dates(6)
    closes = {
        "600002": ["10", "9", "9", "9", "9", "9"],
        "600001": ["10", "9", "9", "9", "9", "9"],
        "600003": ["10", "10", "10", "10", "10", "10"],
        "600004": ["10", "11", "11", "11", "11", "11"],
        "600005": ["10", "12", "12", "12", "12", "12"],
    }
    signals = build_contrarian_signals(
        signal_date=dates[-1],
        bars_by_code={
            code: _bars(code, [Decimal(value) for value in values], dates)
            for code, values in closes.items()
        },
        sector_by_code={code: "S1" for code in closes},
    )

    assert [row.code for row in signals if row.in_candidate_pool] == ["600001"]
    assert signals[0].track_id == CONTRARIAN_TRACK
    assert signals[0].formation_return == Decimal("-0.1")
    assert [row.code for row in signals if row.reference_bucket == "WINNER"] == [
        "600005"
    ]


def test_contrarian_does_not_form_quantiles_with_fewer_than_five_stocks() -> None:
    dates = _dates(6)
    bars = {
        f"60000{index}": _bars(
            f"60000{index}",
            [Decimal("10")] * 6,
            dates,
        )
        for index in range(1, 5)
    }

    signals = build_contrarian_signals(
        signal_date=dates[-1],
        bars_by_code=bars,
        sector_by_code={code: "S1" for code in bars},
    )

    assert signals == ()


def test_residual_estimation_excludes_last_five_sessions() -> None:
    dates = _dates(65)
    market: dict[date, Decimal] = {}
    sector: dict[date, Decimal] = {}
    stock: dict[date, Decimal] = {}
    for index, trade_date in enumerate(dates):
        market_value = Decimal(index % 5 - 2) / Decimal("1000")
        sector_excess = Decimal((index * 2) % 7 - 3) / Decimal("1000")
        sector_value = market_value + sector_excess
        predicted = Decimal("0.001") + Decimal("2") * market_value + Decimal(
            "3"
        ) * sector_excess
        market[trade_date] = market_value
        sector[trade_date] = sector_value
        stock[trade_date] = (
            predicted if index < 60 else predicted - Decimal("0.05")
        )

    estimate = estimate_residual_signal(
        stock_returns=stock,
        market_returns=market,
        sector_returns=sector,
        estimation_dates=dates[:60],
        signal_dates=dates[60:],
    )

    assert estimate.estimation_dates == dates[:60]
    assert estimate.signal_dates == dates[60:]
    assert estimate.alpha == Decimal("0.001")
    assert estimate.beta_market == Decimal("2")
    assert estimate.beta_sector == Decimal("3")
    assert estimate.residual_5d == Decimal("-0.250")


def test_residual_estimation_rejects_overlap_and_short_history() -> None:
    dates = _dates(45)
    values = {trade_date: Decimal("0.01") for trade_date in dates}

    with pytest.raises(ValueError, match="ESTIMATION_SIGNAL_OVERLAP"):
        estimate_residual_signal(
            stock_returns=values,
            market_returns=values,
            sector_returns=values,
            estimation_dates=dates[:40],
            signal_dates=dates[39:44],
        )

    with pytest.raises(ValueError, match="RESIDUAL_WINDOW_INCOMPLETE"):
        estimate_residual_signal(
            stock_returns=values,
            market_returns=values,
            sector_returns=values,
            estimation_dates=dates[:39],
            signal_dates=dates[40:45],
        )


def test_sector_returns_use_median_and_require_ten_point_in_time_members() -> None:
    dates = _dates(2)
    bars_by_code = {
        f"600{index:03d}": _bars(
            f"600{index:03d}",
            [Decimal("100"), Decimal("100") + Decimal(index)],
            dates,
        )
        for index in range(1, 11)
    }
    memberships = tuple(
        _membership(code, "S1", dates) for code in bars_by_code
    )

    result = build_sector_return_series(
        dates=(dates[-1],),
        bars_by_code=bars_by_code,
        memberships=memberships,
        minimum_members=10,
    )

    assert result["S1"][dates[-1]] == Decimal("0.055")

    with pytest.raises(ValueError, match="SECTOR_MEMBERS_BELOW_10"):
        build_sector_return_series(
            dates=(dates[-1],),
            bars_by_code=dict(tuple(bars_by_code.items())[:9]),
            memberships=memberships[:9],
            minimum_members=10,
        )


def test_residual_builder_selects_bottom_ten_percent_and_execution_copies_core() -> None:
    dates = _dates(66)
    market_returns = [
        Decimal(index % 5 - 2) / Decimal("1000") for index in range(65)
    ]
    sector_excess = [
        Decimal((index * 2) % 7 - 3) / Decimal("1000") for index in range(65)
    ]
    index_prices = _prices_from_returns(market_returns)
    bars_by_code: dict[str, tuple[BuyPointBar, ...]] = {}
    memberships: list[SectorMembership] = []
    for stock_index in range(10):
        code = f"600{stock_index + 1:03d}"
        stock_returns = [
            market + sector
            for market, sector in zip(market_returns, sector_excess)
        ]
        if stock_index == 0:
            stock_returns[-5:] = [
                value - Decimal("0.05") for value in stock_returns[-5:]
            ]
        bars_by_code[code] = _bars(
            code,
            _prices_from_returns(stock_returns),
            dates,
        )
        memberships.append(_membership(code, "S1", dates))

    core = build_residual_signals(
        signal_date=dates[-1],
        bars_by_code=bars_by_code,
        memberships=tuple(memberships),
        index_closes={
            "sh.000001": dict(zip(dates, index_prices)),
        },
    )
    execution = build_execution_signals(core)

    selected = [row for row in core if row.in_candidate_pool]
    assert len(selected) == 1
    assert selected[0].code == "600001"
    assert selected[0].track_id == RESIDUAL_TRACK
    assert selected[0].residual_5d is not None
    assert selected[0].residual_5d < Decimal("-0.20")
    assert [row.track_id for row in execution] == [EXECUTION_TRACK] * len(core)
    assert [row.residual_5d for row in execution] == [
        row.residual_5d for row in core
    ]


def test_residual_builder_excludes_one_stock_with_a_calendar_gap() -> None:
    dates = _dates(66)
    market_returns = [
        Decimal(index % 5 - 2) / Decimal("1000") for index in range(65)
    ]
    sector_excess = [
        Decimal((index * 2) % 7 - 3) / Decimal("1000") for index in range(65)
    ]
    stock_returns = [
        market + sector
        for market, sector in zip(market_returns, sector_excess)
    ]
    bars_by_code = {
        f"600{stock_index + 1:03d}": _bars(
            f"600{stock_index + 1:03d}",
            _prices_from_returns(stock_returns),
            dates,
        )
        for stock_index in range(10)
    }
    mismatched_dates = tuple(
        trade_date
        for index, trade_date in enumerate(_dates(67, date(2025, 1, 1)))
        if index != 20
    )
    bars_by_code["600011"] = _bars(
        "600011",
        _prices_from_returns(stock_returns),
        mismatched_dates,
    )
    memberships = tuple(
        _membership(code, "S1", mismatched_dates)
        for code in bars_by_code
    )

    signals = build_residual_signals(
        signal_date=dates[-1],
        bars_by_code=bars_by_code,
        memberships=memberships,
        index_closes={
            "sh.000001": dict(zip(dates, _prices_from_returns(market_returns))),
        },
    )

    assert len(signals) == 10
    assert {row.code for row in signals} == set(bars_by_code) - {"600011"}


def test_execution_builder_rejects_non_core_signal() -> None:
    dates = _dates(6)
    reference = build_contrarian_signals(
        signal_date=dates[-1],
        bars_by_code={
            f"60000{index}": _bars(
                f"60000{index}",
                [Decimal("10")] * 6,
                dates,
            )
            for index in range(1, 6)
        },
        sector_by_code={f"60000{index}": "S1" for index in range(1, 6)},
    )

    with pytest.raises(ValueError, match="EXECUTION_SOURCE_TRACK_INVALID"):
        build_execution_signals(reference)
