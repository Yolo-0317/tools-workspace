from __future__ import annotations

from datetime import date, timedelta

import pytest

from short_term_trading.chip import ChipKline, calculate_chip_metrics


def flat_bars(
    *,
    count: int = 20,
    price: float = 10.0,
    turnover_rate: float = 10.0,
) -> list[ChipKline]:
    start = date(2026, 7, 13)
    return [
        ChipKline(
            trade_date=start + timedelta(days=index),
            open=price,
            close=price,
            high=price,
            low=price,
            turnover_rate=turnover_rate,
        )
        for index in range(count)
    ]


def test_flat_limit_bars_produce_price_costs_and_percentage_units() -> None:
    metrics = calculate_chip_metrics(flat_bars())

    assert metrics.source_trade_date == date(2026, 8, 1)
    assert metrics.cost_90_low == 10.0
    assert metrics.cost_90_high == 10.0
    assert metrics.average_cost == 10.0
    assert metrics.profit_ratio == 100.0
    assert metrics.concentration == 0.0
    assert metrics.input_bar_count == 20
    assert metrics.method == "eastmoney-cyq-v1"


def test_latest_half_turnover_moves_median_cost_to_the_new_price() -> None:
    bars = flat_bars(count=20, price=10.0, turnover_rate=0.0)
    bars[0] = ChipKline(date(2026, 7, 13), 10.0, 10.0, 10.0, 10.0, 100.0)
    bars[-1] = ChipKline(date(2026, 8, 1), 12.0, 12.0, 12.0, 12.0, 50.0)

    metrics = calculate_chip_metrics(list(reversed(bars)))

    assert metrics.cost_90_low == 10.0
    assert metrics.cost_90_high == 12.0
    assert metrics.average_cost == 12.0
    assert metrics.profit_ratio == 100.0
    assert metrics.concentration == pytest.approx(9.0909, abs=0.0001)


def test_fewer_than_twenty_rows_are_rejected() -> None:
    with pytest.raises(ValueError, match="20"):
        calculate_chip_metrics(flat_bars(count=19))


def test_invalid_ohlc_is_rejected() -> None:
    bars = flat_bars()
    bars[-1] = ChipKline(date(2026, 8, 1), 10.0, 10.0, 9.0, 10.0, 10.0)

    with pytest.raises(ValueError, match="OHLC"):
        calculate_chip_metrics(bars)


def test_zero_effective_turnover_is_rejected() -> None:
    with pytest.raises(ValueError, match="换手"):
        calculate_chip_metrics(flat_bars(turnover_rate=0.0))
