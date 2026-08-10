"""Pure technical-indicator calculations over completed daily bars."""

from __future__ import annotations

import math
from typing import Sequence

from .models import DailyBar


def _ordered_bars(bars: Sequence[DailyBar]) -> list[DailyBar]:
    ordered = sorted(bars, key=lambda item: item.trade_date)
    if len(ordered) < 20:
        raise ValueError("指标计算至少需要 20 根日 K")
    dates = [item.trade_date for item in ordered]
    if len(dates) != len(set(dates)):
        raise ValueError("日线包含重复交易日")
    for item in ordered:
        prices = (item.open, item.close, item.high, item.low)
        if any(not math.isfinite(value) or value <= 0 for value in prices):
            raise ValueError("日线价格必须是正的有限数")
        if item.high < max(item.open, item.close, item.low) or item.low > min(
            item.open, item.close, item.high
        ):
            raise ValueError("日线 OHLC 关系无效")
    return ordered


def calculate_indicators(bars: Sequence[DailyBar]) -> dict[str, float]:
    ordered = _ordered_bars(bars)
    closes = [item.close for item in ordered]
    true_ranges = []
    for index in range(1, len(ordered)):
        current = ordered[index]
        previous_close = ordered[index - 1].close
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous_close),
                abs(current.low - previous_close),
            )
        )
    return {
        "ma5": sum(closes[-5:]) / 5,
        "ma10": sum(closes[-10:]) / 10,
        "ma20": sum(closes[-20:]) / 20,
        "atr14": sum(true_ranges[-14:]) / 14,
        "high20": max(item.high for item in ordered[-20:]),
        "low10": min(item.low for item in ordered[-10:]),
    }

