from __future__ import annotations

from datetime import date, timedelta
import unittest

from a_share_stock_diagnosis.chip import calculate_chip_metrics
from a_share_stock_diagnosis.indicators import calculate_indicators
from a_share_stock_diagnosis.models import DailyBar


def bar(
    trade_date: date,
    price: float,
    *,
    turnover: float = 10.0,
    spread: float = 0.0,
) -> DailyBar:
    return DailyBar(
        trade_date=trade_date,
        open=price - spread / 4,
        close=price,
        high=price + spread / 2,
        low=price - spread / 2,
        volume=1000.0,
        amount=price * 1000.0,
        change_pct=0.0,
        turnover_rate=turnover,
    )


class IndicatorTests(unittest.TestCase):
    def test_indicators_use_latest_ordered_completed_bars(self) -> None:
        start = date(2026, 6, 29)
        bars = [bar(start + timedelta(days=i), 10.0 + i * 0.1, spread=0.4) for i in range(30)]

        indicators = calculate_indicators(list(reversed(bars)))

        self.assertAlmostEqual(indicators["ma5"], 12.7)
        self.assertAlmostEqual(indicators["ma10"], 12.45)
        self.assertAlmostEqual(indicators["ma20"], 11.95)
        self.assertAlmostEqual(indicators["atr14"], 0.4)
        self.assertAlmostEqual(indicators["high20"], 13.1)
        self.assertAlmostEqual(indicators["low10"], 11.8)

    def test_indicators_reject_short_or_duplicate_history(self) -> None:
        start = date(2026, 7, 1)
        short = [bar(start + timedelta(days=i), 10.0) for i in range(19)]
        with self.assertRaisesRegex(ValueError, "20"):
            calculate_indicators(short)
        duplicate = [bar(start + timedelta(days=i), 10.0) for i in range(20)]
        duplicate[-1] = bar(duplicate[-2].trade_date, 10.0)
        with self.assertRaisesRegex(ValueError, "重复"):
            calculate_indicators(duplicate)


class ChipTests(unittest.TestCase):
    def flat_bars(self, *, count: int = 20, price: float = 10.0, turnover: float = 10.0):
        start = date(2026, 7, 13)
        return [bar(start + timedelta(days=i), price, turnover=turnover) for i in range(count)]

    def test_flat_limit_bars_have_one_cost_and_percentage_units(self) -> None:
        metrics = calculate_chip_metrics(self.flat_bars())
        self.assertEqual(metrics.cost_90_low, 10.0)
        self.assertEqual(metrics.cost_90_high, 10.0)
        self.assertEqual(metrics.average_cost, 10.0)
        self.assertEqual(metrics.profit_ratio, 100.0)
        self.assertEqual(metrics.concentration, 0.0)
        self.assertEqual(metrics.method, "eastmoney-cyq-v1")

    def test_latest_half_turnover_moves_median_to_new_price(self) -> None:
        bars = self.flat_bars(turnover=0.0)
        bars[0] = bar(bars[0].trade_date, 10.0, turnover=100.0)
        bars[-1] = bar(bars[-1].trade_date, 12.0, turnover=50.0)
        metrics = calculate_chip_metrics(list(reversed(bars)))
        self.assertEqual(metrics.cost_90_low, 10.0)
        self.assertEqual(metrics.cost_90_high, 12.0)
        self.assertEqual(metrics.average_cost, 12.0)
        self.assertAlmostEqual(metrics.concentration, 9.0909, places=4)

    def test_chip_rejects_short_duplicate_or_zero_turnover_history(self) -> None:
        with self.assertRaisesRegex(ValueError, "20"):
            calculate_chip_metrics(self.flat_bars(count=19))
        duplicate = self.flat_bars()
        duplicate[-1] = bar(duplicate[-2].trade_date, 10.0)
        with self.assertRaisesRegex(ValueError, "重复"):
            calculate_chip_metrics(duplicate)
        with self.assertRaisesRegex(ValueError, "换手"):
            calculate_chip_metrics(self.flat_bars(turnover=0.0))


if __name__ == "__main__":
    unittest.main()
