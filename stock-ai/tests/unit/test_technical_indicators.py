from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
import math

import pytest

from stock_ai.technical_indicators import (
    IndicatorInputError,
    compute_technical_indicators,
)


@dataclass(frozen=True)
class Bar:
    trade_date: date
    high: float
    low: float
    close: float
    amount_qian: float


def _bars(
    closes: list[float],
    *,
    half_range: float = 1.0,
    amounts: list[float] | None = None,
) -> list[Bar]:
    start = date(2026, 1, 1)
    resolved_amounts = amounts or [100_000.0] * len(closes)
    return [
        Bar(
            trade_date=start + timedelta(days=index),
            high=close + half_range,
            low=close - half_range,
            close=close,
            amount_qian=resolved_amounts[index],
        )
        for index, close in enumerate(closes)
    ]


def test_monotonic_exponential_prices_have_maximum_trend_r2() -> None:
    bars = _bars([100.0 * math.exp(0.01 * index) for index in range(60)])

    snapshot = compute_technical_indicators(bars)

    assert snapshot.trend_r2_20 == pytest.approx(1.0, abs=1e-10)
    assert snapshot.trend_slope_20 == pytest.approx(0.01, abs=1e-10)


def test_constant_true_range_produces_literal_atr() -> None:
    snapshot = compute_technical_indicators(_bars([100.0] * 60))

    assert snapshot.atr14 == pytest.approx(2.0)
    assert snapshot.atr_pct == pytest.approx(0.02)


def test_all_up_closes_produce_rsi_100_and_adx_100() -> None:
    snapshot = compute_technical_indicators(_bars([100.0 + index for index in range(60)]))

    assert snapshot.rsi14 == pytest.approx(100.0)
    assert snapshot.adx14 == pytest.approx(100.0)


def test_return_breakout_and_volume_metrics_use_literal_windows() -> None:
    closes = [80.0] * 39 + [100.0] * 20 + [110.0]
    amounts = [100_000.0] * 50 + [200_000.0] * 5 + [100_000.0] * 4 + [300_000.0]
    bars = _bars(closes, half_range=0.0, amounts=amounts)

    snapshot = compute_technical_indicators(bars)

    assert snapshot.return20 == pytest.approx(0.10)
    assert snapshot.breakout_pct == pytest.approx(0.10)
    assert snapshot.average_amount5 == pytest.approx(120_000.0)
    assert snapshot.amount_ratio == pytest.approx(2.5)
    assert snapshot.advance_amount5 == pytest.approx(200_000.0)
    assert snapshot.pullback_amount5 == pytest.approx(140_000.0)
    assert snapshot.pullback_amount_ratio == pytest.approx(0.7)


def test_requires_at_least_60_bars() -> None:
    with pytest.raises(IndicatorInputError, match="60"):
        compute_technical_indicators(_bars([100.0] * 59))


def test_rejects_duplicate_dates() -> None:
    bars = _bars([100.0] * 60)
    bars[-1] = replace(bars[-1], trade_date=bars[-2].trade_date)

    with pytest.raises(IndicatorInputError, match="duplicate"):
        compute_technical_indicators(bars)


@pytest.mark.parametrize(
    ("field", "value"),
    (("high", math.nan), ("low", math.inf), ("close", math.nan), ("amount_qian", math.inf)),
)
def test_rejects_non_finite_values(field: str, value: float) -> None:
    bars = _bars([100.0] * 60)
    bars[-1] = replace(bars[-1], **{field: value})

    with pytest.raises(IndicatorInputError, match="finite"):
        compute_technical_indicators(bars)


def test_rejects_zero_close() -> None:
    bars = _bars([100.0] * 60)
    bars[-1] = replace(bars[-1], close=0.0)

    with pytest.raises(IndicatorInputError, match="close"):
        compute_technical_indicators(bars)


def test_rejects_zero_advance_amount() -> None:
    amounts = [100_000.0] * 50 + [0.0] * 5 + [100_000.0] * 5

    with pytest.raises(IndicatorInputError, match="advance amount"):
        compute_technical_indicators(_bars([100.0] * 60, amounts=amounts))
