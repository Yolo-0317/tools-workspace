from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

from a_share_stock_diagnosis.calendar import BundledTradingCalendar
from a_share_stock_diagnosis.session import classify_session


SHANGHAI = ZoneInfo("Asia/Shanghai")
SKILL_ROOT = Path(__file__).resolve().parents[1]


class BundledCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calendar = BundledTradingCalendar.load(
            SKILL_ROOT / "data" / "sse_trade_calendar_2026.json"
        )

    def test_calendar_confirms_open_closed_and_unknown_dates(self) -> None:
        self.assertIs(self.calendar.status(date(2026, 8, 10)), True)
        self.assertIs(self.calendar.status(date(2026, 8, 9)), False)
        self.assertIs(self.calendar.status(date(2026, 2, 16)), False)
        self.assertIsNone(self.calendar.status(date(2027, 1, 4)))

    def test_calendar_finds_neighboring_confirmed_trade_dates(self) -> None:
        self.assertEqual(
            self.calendar.latest_on_or_before(date(2026, 8, 9)),
            date(2026, 8, 7),
        )
        self.assertEqual(
            self.calendar.next_on_or_after(date(2026, 2, 16)),
            date(2026, 2, 24),
        )


class SessionClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calendar = BundledTradingCalendar.load(
            SKILL_ROOT / "data" / "sse_trade_calendar_2026.json"
        )

    def test_open_day_clock_ranges(self) -> None:
        cases = (
            ((9, 0), "PRE_MARKET", date(2026, 8, 7)),
            ((9, 30), "INTRADAY", date(2026, 8, 10)),
            ((11, 30), "MIDDAY_BREAK", date(2026, 8, 10)),
            ((13, 0), "INTRADAY", date(2026, 8, 10)),
            ((15, 0), "POST_MARKET", date(2026, 8, 10)),
        )
        for (hour, minute), expected_session, expected_date in cases:
            with self.subTest(hour=hour, minute=minute):
                context = classify_session(
                    datetime(2026, 8, 10, hour, minute, tzinfo=SHANGHAI),
                    self.calendar,
                )
                self.assertEqual(context.session, expected_session)
                self.assertTrue(context.calendar_confirmed)
                self.assertEqual(context.diagnosis_trade_date, expected_date)

    def test_confirmed_holiday_is_non_trading_day(self) -> None:
        context = classify_session(
            datetime(2026, 2, 16, 10, 0, tzinfo=SHANGHAI),
            self.calendar,
        )
        self.assertEqual(context.session, "NON_TRADING_DAY")
        self.assertTrue(context.calendar_confirmed)
        self.assertEqual(context.next_trade_date, date(2026, 2, 24))

    def test_unknown_weekday_is_not_assumed_open(self) -> None:
        context = classify_session(
            datetime(2027, 1, 4, 10, 0, tzinfo=SHANGHAI),
            self.calendar,
        )
        self.assertEqual(context.session, "NON_TRADING_DAY")
        self.assertFalse(context.calendar_confirmed)
        self.assertIsNone(context.diagnosis_trade_date)

    def test_naive_datetime_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "时区"):
            classify_session(datetime(2026, 8, 10, 10, 0), self.calendar)


if __name__ == "__main__":
    unittest.main()
