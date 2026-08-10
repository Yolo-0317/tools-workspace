"""Deterministic Eastmoney-style CYQ estimation over public daily bars."""

from __future__ import annotations

import math
from typing import Sequence

from .models import ChipMetrics, DailyBar


def _validate_and_order(bars: Sequence[DailyBar]) -> list[DailyBar]:
    ordered = sorted(bars, key=lambda item: item.trade_date)
    if len(ordered) < 20:
        raise ValueError("筹码计算至少需要 20 根日 K")
    dates = [item.trade_date for item in ordered]
    if len(dates) != len(set(dates)):
        raise ValueError("日线包含重复交易日")
    for item in ordered:
        prices = (item.open, item.close, item.high, item.low)
        if any(not math.isfinite(value) or value <= 0 for value in prices):
            raise ValueError("OHLC 价格必须是正的有限数")
        if item.high < max(item.open, item.close, item.low) or item.low > min(
            item.open, item.close, item.high
        ):
            raise ValueError("OHLC 价格关系无效")
        if not math.isfinite(item.turnover_rate) or item.turnover_rate < 0:
            raise ValueError("换手率必须是非负有限数")
    if not any(item.turnover_rate > 0 for item in ordered):
        raise ValueError("缺少有效换手率，不能计算筹码")
    return ordered


def calculate_chip_metrics(bars: Sequence[DailyBar]) -> ChipMetrics:
    ordered = _validate_and_order(bars)
    bucket_count = 150
    maximum = max(item.high for item in ordered)
    minimum = min(item.low for item in ordered)
    accuracy = max(0.01, (maximum - minimum) / (bucket_count - 1))
    prices = [round(minimum + accuracy * index, 2) for index in range(bucket_count)]
    chips = [0.0] * bucket_count

    for item in ordered:
        turnover = min(1.0, item.turnover_rate / 100.0)
        chips = [value * (1.0 - turnover) for value in chips]
        average = (item.open + item.close + item.high + item.low) / 4.0
        high_index = min(bucket_count - 1, math.floor((item.high - minimum) / accuracy))
        low_index = max(0, math.ceil((item.low - minimum) / accuracy))
        center_index = min(
            bucket_count - 1,
            max(0, math.floor((average - minimum) / accuracy)),
        )
        if item.high == item.low:
            chips[center_index] += (bucket_count - 1) * turnover / 2.0
            continue
        slope = 2.0 / (item.high - item.low)
        for index in range(low_index, high_index + 1):
            price = minimum + accuracy * index
            if price <= average:
                weight = (
                    slope
                    if math.isclose(average, item.low)
                    else (price - item.low) / (average - item.low) * slope
                )
            else:
                weight = (
                    slope
                    if math.isclose(item.high, average)
                    else (item.high - price) / (item.high - average) * slope
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
    profitable = sum(value for price, value in zip(prices, chips) if current_close >= price)
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
