from __future__ import annotations

from datetime import date, datetime
import math
import unittest
from zoneinfo import ZoneInfo

from a_share_stock_diagnosis.models import DiagnosisResult
from a_share_stock_diagnosis.validation import (
    market_for_code,
    normalize_code,
    validate_holding,
)


class SymbolValidationTests(unittest.TestCase):
    def test_normalize_code_accepts_supported_stock_forms(self) -> None:
        cases = {
            "603011": "603011",
            "sh603011": "603011",
            "603011.SH": "603011",
            "sz000001": "000001",
            "300750.SZ": "300750",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_code(raw), expected)

    def test_normalize_code_rejects_malformed_or_unsupported_symbols(self) -> None:
        for raw in ("", "60301", "abc603011", "830001", "510300"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    normalize_code(raw)

    def test_market_for_code_distinguishes_supported_exchanges(self) -> None:
        self.assertEqual(market_for_code("603011"), "SH")
        self.assertEqual(market_for_code("688001"), "SH")
        self.assertEqual(market_for_code("000001"), "SZ")
        self.assertEqual(market_for_code("301001"), "SZ")


class HoldingValidationTests(unittest.TestCase):
    def test_no_holding_values_returns_none(self) -> None:
        self.assertIsNone(validate_holding(None, None, None))

    def test_holding_accepts_unknown_available_shares(self) -> None:
        value = validate_holding(500, 22.75, None)
        self.assertIsNotNone(value)
        assert value is not None
        self.assertEqual(value.shares, 500)
        self.assertEqual(value.cost_price, 22.75)
        self.assertIsNone(value.available_shares)

    def test_partial_holding_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "shares.*cost_price"):
            validate_holding(500, None, None)
        with self.assertRaisesRegex(ValueError, "shares.*cost_price"):
            validate_holding(None, 22.75, None)

    def test_holding_rejects_invalid_numbers(self) -> None:
        invalid_cases = (
            (-1, 22.75, 0),
            (500, 0.0, 500),
            (500, math.inf, 500),
            (500, 22.75, -1),
            (500, 22.75, 501),
            (550, 22.75, 500),
        )
        for values in invalid_cases:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    validate_holding(*values)


class DiagnosisResultTests(unittest.TestCase):
    def test_to_dict_serializes_dates_and_keeps_non_actionable_contract(self) -> None:
        result = DiagnosisResult(
            schema_version="1.0",
            symbol="603011",
            name="合锻智能",
            session="POST_MARKET",
            as_of=datetime(2026, 8, 10, 15, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
            diagnosis_trade_date=date(2026, 8, 10),
            data_freshness="completed_close",
            quote=None,
            latest_bar={"trade_date": date(2026, 8, 10), "close": 23.95},
            indicators={},
            chip_estimate=None,
            decision="NO_TRADE",
            actionable=False,
            reason="fixture",
            next_action="等待",
            levels={},
            holding=None,
            warnings=[],
            source_refs={},
            errors=[],
        )

        payload = result.to_dict()

        self.assertEqual(payload["as_of"], "2026-08-10T15:10:00+08:00")
        self.assertEqual(payload["diagnosis_trade_date"], "2026-08-10")
        self.assertEqual(payload["latest_bar"]["trade_date"], "2026-08-10")
        self.assertIs(payload["actionable"], False)


if __name__ == "__main__":
    unittest.main()
