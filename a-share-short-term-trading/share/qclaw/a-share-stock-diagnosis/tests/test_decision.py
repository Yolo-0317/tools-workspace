from __future__ import annotations

from datetime import date, datetime, timedelta
import unittest
from zoneinfo import ZoneInfo

from a_share_stock_diagnosis.decision import (
    build_entry_levels,
    diagnose,
    round_sell_quantity,
)
from a_share_stock_diagnosis.models import (
    ChipMetrics,
    DailyBar,
    HoldingInput,
    Quote,
    Security,
    SessionContext,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def flat_bars(*, end: date, count: int = 30, price: float = 10.0) -> list[DailyBar]:
    start = end - timedelta(days=count - 1)
    return [
        DailyBar(
            trade_date=start + timedelta(days=index),
            open=9.9,
            close=price,
            high=10.2,
            low=9.8,
            volume=1000.0,
            amount=10000.0,
            change_pct=0.0,
            turnover_rate=10.0,
        )
        for index in range(count)
    ]


def quote(price: float, *, now: datetime) -> Quote:
    return Quote(
        code="603011",
        name="合锻智能",
        price=price,
        open=10.0,
        high=max(10.2, price),
        low=min(9.8, price),
        previous_close=10.0,
        change_pct=(price / 10.0 - 1.0) * 100,
        turnover_rate=5.0,
        as_of=now,
    )


class LevelTests(unittest.TestCase):
    def test_entry_levels_use_resistance_support_and_atr(self) -> None:
        levels = build_entry_levels(
            {
                "ma5": 19.6,
                "ma10": 19.5,
                "ma20": 19.0,
                "atr14": 1.0,
                "high20": 20.0,
                "low10": 18.0,
            },
            ChipMetrics(date(2026, 8, 10), 18.5, 19.0, 18.8, 60.0, 2.0, 210),
        )
        self.assertEqual(levels["resistance"], 20.0)
        self.assertEqual(levels["trigger"], 20.1)
        self.assertEqual(levels["entry_ceiling"], 20.6)
        self.assertEqual(levels["support"], 19.5)
        self.assertEqual(levels["invalidation"], 19.4)
        self.assertEqual(levels["first_reduce"], 21.5)
        self.assertAlmostEqual(levels["risk_fraction"], 0.03482587)

    def test_sell_quantity_is_board_lot_and_never_exceeds_available(self) -> None:
        self.assertEqual(round_sell_quantity(260, 500), 200)
        self.assertEqual(round_sell_quantity(900, 550), 500)
        self.assertEqual(round_sell_quantity(50, 500), 0)


class DiagnosisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.security = Security("603011", "SH", "合锻智能")
        self.now = datetime(2026, 8, 10, 10, 0, tzinfo=SHANGHAI)
        self.intraday = SessionContext(
            session="INTRADAY",
            local_now=self.now,
            calendar_confirmed=True,
            diagnosis_trade_date=date(2026, 8, 10),
            next_trade_date=date(2026, 8, 10),
            reason="fixture",
        )
        self.post = SessionContext(
            session="POST_MARKET",
            local_now=self.now.replace(hour=15, minute=10),
            calendar_confirmed=True,
            diagnosis_trade_date=date(2026, 8, 10),
            next_trade_date=date(2026, 8, 11),
            reason="fixture",
        )

    def test_complete_static_data_produces_wait_entry_but_not_actionable(self) -> None:
        result = diagnose(
            self.security,
            self.post,
            flat_bars(end=date(2026, 8, 10)),
            None,
            None,
            as_of=self.post.local_now,
        )
        self.assertEqual(result.decision, "WAIT_ENTRY")
        self.assertFalse(result.actionable)
        self.assertGreaterEqual(result.levels["risk_fraction"], 0.015)
        self.assertLessEqual(result.levels["risk_fraction"], 0.05)

    def test_wrong_date_or_unknown_calendar_fails_closed(self) -> None:
        wrong_date = diagnose(
            self.security,
            self.post,
            flat_bars(end=date(2026, 8, 7)),
            None,
            None,
            as_of=self.post.local_now,
        )
        self.assertEqual(wrong_date.decision, "NO_TRADE")

        unknown = SessionContext(
            "NON_TRADING_DAY", self.now, False, None, None, "unknown"
        )
        no_calendar = diagnose(
            self.security,
            unknown,
            flat_bars(end=date(2026, 8, 7)),
            None,
            None,
            as_of=self.now,
        )
        self.assertEqual(no_calendar.decision, "NO_TRADE")
        self.assertFalse(no_calendar.actionable)

    def test_holding_rules_cover_hold_reduce_exit_and_t_plus_one(self) -> None:
        bars = flat_bars(end=date(2026, 8, 7))
        holding = HoldingInput(500, 9.5, 500)
        cases = (
            (10.1, "HOLD", 0),
            (9.98, "REDUCE", 200),
            (9.95, "EXIT", 500),
            (10.9, "REDUCE", 200),
        )
        for price, expected_decision, expected_sell in cases:
            with self.subTest(price=price):
                result = diagnose(
                    self.security,
                    self.intraday,
                    bars,
                    quote(price, now=self.now),
                    holding,
                    as_of=self.now,
                )
                self.assertEqual(result.decision, expected_decision)
                self.assertEqual(result.holding["suggested_sell_shares"], expected_sell)
                self.assertFalse(result.actionable)

        unavailable = diagnose(
            self.security,
            self.intraday,
            bars,
            quote(9.98, now=self.now),
            HoldingInput(500, 9.5, 0),
            as_of=self.now,
        )
        self.assertEqual(unavailable.decision, "OBSERVE")
        self.assertEqual(unavailable.holding["suggested_sell_shares"], 0)

    def test_unknown_available_or_missing_intraday_quote_never_emits_sell_quantity(self) -> None:
        bars = flat_bars(end=date(2026, 8, 7))
        unknown_available = diagnose(
            self.security,
            self.intraday,
            bars,
            quote(9.98, now=self.now),
            HoldingInput(500, 9.5, None),
            as_of=self.now,
        )
        self.assertEqual(unknown_available.decision, "OBSERVE")
        self.assertIsNone(unknown_available.holding["suggested_sell_shares"])

        missing_quote = diagnose(
            self.security,
            self.intraday,
            bars,
            None,
            HoldingInput(500, 9.5, 500),
            as_of=self.now,
        )
        self.assertEqual(missing_quote.decision, "OBSERVE")
        self.assertIsNone(missing_quote.holding["suggested_sell_shares"])


if __name__ == "__main__":
    unittest.main()
