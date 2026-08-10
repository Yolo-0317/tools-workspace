"""Deterministic Eastmoney-style CYQ chip-distribution calculation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import math


@dataclass(frozen=True)
class ChipKline:
    trade_date: date
    open: float
    close: float
    high: float
    low: float
    turnover_rate: float


@dataclass(frozen=True)
class ChipMetrics:
    source_trade_date: date
    cost_90_low: float
    cost_90_high: float
    average_cost: float
    profit_ratio: float
    concentration: float
    input_bar_count: int
    method: str = "eastmoney-cyq-v1"

    def to_payload(self) -> dict[str, object]:
        values = asdict(self)
        values["source_trade_date"] = self.source_trade_date.isoformat()
        return values


def _validate_bar(bar: ChipKline) -> None:
    prices = (bar.open, bar.close, bar.high, bar.low)
    if any(not math.isfinite(value) or value <= 0 for value in prices):
        raise ValueError("OHLC prices must be finite and positive")
    if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(
        bar.open, bar.close, bar.high
    ):
        raise ValueError("OHLC price ordering is invalid")
    if not math.isfinite(bar.turnover_rate) or bar.turnover_rate < 0:
        raise ValueError("换手率必须是非负有限数")


def calculate_chip_metrics(bars: list[ChipKline]) -> ChipMetrics:
    """Calculate the latest CYQ distribution from at least 20 daily rows."""

    ordered = sorted(bars, key=lambda item: item.trade_date)
    if len(ordered) < 20:
        raise ValueError("筹码计算至少需要 20 根日 K")
    for bar in ordered:
        _validate_bar(bar)
    if not any(bar.turnover_rate > 0 for bar in ordered):
        raise ValueError("缺少有效换手率，不能计算筹码")

    factor = 150
    maximum = max(bar.high for bar in ordered)
    minimum = min(bar.low for bar in ordered)
    accuracy = max(0.01, (maximum - minimum) / (factor - 1))
    prices = [round(minimum + accuracy * index, 2) for index in range(factor)]
    chips = [0.0] * factor

    for bar in ordered:
        turnover = min(1.0, bar.turnover_rate / 100.0)
        chips = [value * (1.0 - turnover) for value in chips]
        average = (bar.open + bar.close + bar.high + bar.low) / 4.0
        high_index = min(factor - 1, math.floor((bar.high - minimum) / accuracy))
        low_index = max(0, math.ceil((bar.low - minimum) / accuracy))
        center_index = min(
            factor - 1, max(0, math.floor((average - minimum) / accuracy))
        )
        if bar.high == bar.low:
            chips[center_index] += (factor - 1) * turnover / 2.0
            continue
        slope = 2.0 / (bar.high - bar.low)
        for index in range(low_index, high_index + 1):
            price = minimum + accuracy * index
            if price <= average:
                weight = (
                    slope
                    if math.isclose(average, bar.low)
                    else (price - bar.low) / (average - bar.low) * slope
                )
            else:
                weight = (
                    slope
                    if math.isclose(bar.high, average)
                    else (bar.high - price) / (bar.high - average) * slope
                )
            chips[index] += max(0.0, weight) * turnover

    total = sum(chips)
    if total <= 0:
        raise ValueError("缺少有效换手率，不能计算筹码")

    def cost_at(fraction: float) -> float:
        threshold = total * fraction
        accumulated = 0.0
        for price, value in zip(prices, chips):
            if accumulated + value > threshold:
                return price
            accumulated += value
        return prices[-1]

    current_close = ordered[-1].close
    profitable = sum(
        value for price, value in zip(prices, chips) if current_close >= price
    )
    cost_low = cost_at(0.05)
    cost_high = cost_at(0.95)
    denominator = cost_low + cost_high
    concentration = 0.0 if denominator == 0 else (cost_high - cost_low) / denominator
    return ChipMetrics(
        source_trade_date=ordered[-1].trade_date,
        cost_90_low=round(cost_low, 2),
        cost_90_high=round(cost_high, 2),
        average_cost=round(cost_at(0.50), 2),
        profit_ratio=round(profitable / total * 100.0, 4),
        concentration=round(concentration * 100.0, 4),
        input_bar_count=len(ordered),
    )
