"""Pure technical indicators shared by selection and proxy backtests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Protocol, Sequence


class IndicatorInputError(ValueError):
    """Raised when completed daily bars cannot produce trustworthy indicators."""


class BarLike(Protocol):
    trade_date: date
    high: float
    low: float
    close: float
    amount_qian: float


@dataclass(frozen=True)
class TechnicalIndicatorSnapshot:
    adx14: float
    rsi14: float
    atr14: float
    atr_pct: float
    trend_r2_20: float
    trend_slope_20: float
    return20: float
    breakout_pct: float
    average_amount5: float
    amount_ratio: float
    advance_amount5: float
    pullback_amount5: float
    pullback_amount_ratio: float


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _wilder_latest(values: Sequence[float], period: int) -> float:
    value = _mean(values[:period])
    for current in values[period:]:
        value = ((period - 1) * value + current) / period
    return value


def _directional_index(bars: Sequence[BarLike], period: int = 14) -> float:
    true_ranges: list[float] = []
    plus_moves: list[float] = []
    minus_moves: list[float] = []
    for previous, current in zip(bars, bars[1:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
        up_move = current.high - previous.high
        down_move = previous.low - current.low
        plus_moves.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_moves.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    smoothed_range = sum(true_ranges[:period])
    smoothed_plus = sum(plus_moves[:period])
    smoothed_minus = sum(minus_moves[:period])

    def dx() -> float:
        if smoothed_range == 0:
            return 0.0
        plus_di = 100.0 * smoothed_plus / smoothed_range
        minus_di = 100.0 * smoothed_minus / smoothed_range
        total = plus_di + minus_di
        return 0.0 if total == 0 else 100.0 * abs(plus_di - minus_di) / total

    dx_values = [dx()]
    for index in range(period, len(true_ranges)):
        smoothed_range = smoothed_range - smoothed_range / period + true_ranges[index]
        smoothed_plus = smoothed_plus - smoothed_plus / period + plus_moves[index]
        smoothed_minus = smoothed_minus - smoothed_minus / period + minus_moves[index]
        dx_values.append(dx())
    return _wilder_latest(dx_values, period)


def _relative_strength_index(closes: Sequence[float], period: int = 14) -> float:
    changes = [current - previous for previous, current in zip(closes, closes[1:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = _wilder_latest(gains, period)
    average_loss = _wilder_latest(losses, period)
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def _log_trend(closes: Sequence[float]) -> tuple[float, float]:
    values = [math.log(value) for value in closes[-20:]]
    x_values = tuple(range(20))
    x_mean = _mean(x_values)
    y_mean = _mean(values)
    xx = sum((x - x_mean) ** 2 for x in x_values)
    xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
    slope = xy / xx
    fitted = [y_mean + slope * (x - x_mean) for x in x_values]
    total = sum((y - y_mean) ** 2 for y in values)
    residual = sum((y - estimate) ** 2 for y, estimate in zip(values, fitted))
    r_squared = 1.0 if total == 0 else max(0.0, min(1.0, 1.0 - residual / total))
    return slope, r_squared


def _validated_bars(bars: Sequence[BarLike]) -> tuple[BarLike, ...]:
    resolved = tuple(bars)
    if len(resolved) < 60:
        raise IndicatorInputError("at least 60 completed bars are required")
    try:
        dates = [bar.trade_date for bar in resolved]
        numeric_rows = [
            (float(bar.high), float(bar.low), float(bar.close), float(bar.amount_qian))
            for bar in resolved
        ]
    except (AttributeError, TypeError, ValueError) as exc:
        raise IndicatorInputError("bars have invalid fields") from exc
    if len(set(dates)) != len(dates):
        raise IndicatorInputError("duplicate trade dates")
    if any(current <= previous for previous, current in zip(dates, dates[1:])):
        raise IndicatorInputError("trade dates must be strictly increasing")
    if any(not math.isfinite(value) for row in numeric_rows for value in row):
        raise IndicatorInputError("bar values must be finite")
    if any(close <= 0 for _, _, close, _ in numeric_rows):
        raise IndicatorInputError("close must be positive")
    if any(high < low for high, low, _, _ in numeric_rows):
        raise IndicatorInputError("high must not be below low")
    if any(amount < 0 for _, _, _, amount in numeric_rows):
        raise IndicatorInputError("amount must not be negative")
    return resolved


def compute_technical_indicators(
    bars: Sequence[BarLike],
) -> TechnicalIndicatorSnapshot:
    """Compute completed-bar indicators without external numerical dependencies."""

    resolved = _validated_bars(bars)
    closes = [float(bar.close) for bar in resolved]
    true_ranges = [
        max(
            float(current.high) - float(current.low),
            abs(float(current.high) - float(previous.close)),
            abs(float(current.low) - float(previous.close)),
        )
        for previous, current in zip(resolved, resolved[1:])
    ]
    atr14 = _wilder_latest(true_ranges, 14)
    trend_slope_20, trend_r2_20 = _log_trend(closes)
    prior_high20 = max(float(bar.high) for bar in resolved[-21:-1])
    if prior_high20 <= 0:
        raise IndicatorInputError("prior high must be positive")

    amounts = [float(bar.amount_qian) for bar in resolved]
    average_amount5 = _mean(amounts[-6:-1])
    advance_amount5 = _mean(amounts[-10:-5])
    pullback_amount5 = _mean(amounts[-5:])
    if average_amount5 <= 0:
        raise IndicatorInputError("average amount must be positive")
    if advance_amount5 <= 0:
        raise IndicatorInputError("advance amount must be positive")

    latest_close = closes[-1]
    return TechnicalIndicatorSnapshot(
        adx14=_directional_index(resolved),
        rsi14=_relative_strength_index(closes),
        atr14=atr14,
        atr_pct=atr14 / latest_close,
        trend_r2_20=trend_r2_20,
        trend_slope_20=trend_slope_20,
        return20=latest_close / closes[-21] - 1.0,
        breakout_pct=latest_close / prior_high20 - 1.0,
        average_amount5=average_amount5,
        amount_ratio=amounts[-1] / average_amount5,
        advance_amount5=advance_amount5,
        pullback_amount5=pullback_amount5,
        pullback_amount_ratio=pullback_amount5 / advance_amount5,
    )
