from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from io import StringIO
import json
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

from a_share_stock_diagnosis.calendar import BundledTradingCalendar
from a_share_stock_diagnosis.cli import run
from a_share_stock_diagnosis.eastmoney import AmbiguousSymbolError, DataSourceError
from a_share_stock_diagnosis.models import DailyBar, Quote, Security


SHANGHAI = ZoneInfo("Asia/Shanghai")
SKILL_ROOT = Path(__file__).resolve().parents[1]


def complete_bars(end: date) -> list[DailyBar]:
    start = end - timedelta(days=29)
    return [
        DailyBar(
            trade_date=start + timedelta(days=index),
            open=9.9,
            close=10.0,
            high=10.2,
            low=9.8,
            volume=1000.0,
            amount=10000.0,
            change_pct=0.0,
            turnover_rate=10.0,
        )
        for index in range(30)
    ]


class FixtureClient:
    def __init__(self, now: datetime, *, failure: Exception | None = None) -> None:
        self.now = now
        self.failure = failure

    def resolve_symbol(self, value: str) -> Security:
        if self.failure is not None:
            raise self.failure
        return Security("603011", "SH", "合锻智能")

    def fetch_daily_bars(self, security: Security, limit: int = 210) -> list[DailyBar]:
        return complete_bars(date(2026, 8, 10))

    def fetch_quote(self, security: Security) -> Quote:
        return Quote(
            security.code,
            security.name,
            10.1,
            10.0,
            10.2,
            9.8,
            10.0,
            1.0,
            5.0,
            self.now,
        )


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 10, 15, 10, tzinfo=SHANGHAI)
        self.calendar = BundledTradingCalendar.load(
            SKILL_ROOT / "data" / "sse_trade_calendar_2026.json"
        )

    def invoke(self, argv, client=None):
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = run(
                argv,
                client=client or FixtureClient(self.now),
                calendar=self.calendar,
                now=self.now,
            )
        payload = json.loads(stdout.getvalue())
        return status, payload, stdout.getvalue(), stderr.getvalue()

    def test_code_invocation_emits_one_non_actionable_json_document(self) -> None:
        status, payload, raw, stderr = self.invoke(["--symbol", "603011", "--output", "json"])
        self.assertEqual(status, 0)
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["symbol"], "603011")
        self.assertEqual(payload["decision"], "WAIT_ENTRY")
        self.assertIs(payload["actionable"], False)
        self.assertEqual(raw.count("\n"), 1)
        self.assertEqual(stderr, "")

    def test_holding_arguments_are_used_but_not_echoed_outside_json(self) -> None:
        status, payload, raw, _ = self.invoke(
            [
                "--symbol",
                "合锻智能",
                "--shares",
                "500",
                "--cost-price",
                "9.50",
                "--available-shares",
                "500",
            ]
        )
        self.assertEqual(status, 0)
        self.assertEqual(payload["holding"]["shares"], 500)
        self.assertIs(payload["actionable"], False)
        self.assertEqual(json.loads(raw)["holding"]["cost_price"], 9.5)

    def test_partial_holding_and_naive_at_return_safe_validation_json(self) -> None:
        for argv in (
            ["--symbol", "603011", "--shares", "500"],
            ["--symbol", "603011", "--at", "2026-08-10T10:00:00"],
        ):
            with self.subTest(argv=argv):
                status, payload, _, _ = self.invoke(argv)
                self.assertEqual(status, 2)
                self.assertEqual(payload["decision"], "NO_TRADE")
                self.assertEqual(payload["errors"][0]["code"], "INVALID_INPUT")
                self.assertIs(payload["actionable"], False)

    def test_ambiguous_symbol_lists_candidates_without_guessing(self) -> None:
        candidates = [Security("600001", "SH", "测试股份"), Security("000001", "SZ", "测试银行")]
        client = FixtureClient(self.now, failure=AmbiguousSymbolError(candidates))
        status, payload, _, _ = self.invoke(["--symbol", "测试"], client)
        self.assertEqual(status, 2)
        self.assertEqual(payload["errors"][0]["code"], "AMBIGUOUS_SYMBOL")
        self.assertEqual([item["code"] for item in payload["candidates"]], ["600001", "000001"])

    def test_data_source_failure_is_safe_and_does_not_expose_exception_details(self) -> None:
        client = FixtureClient(
            self.now,
            failure=DataSourceError("NETWORK_ERROR", "公开行情接口暂时不可用"),
        )
        status, payload, raw, _ = self.invoke(["--symbol", "603011"], client)
        self.assertEqual(status, 3)
        self.assertEqual(payload["errors"][0]["code"], "NETWORK_ERROR")
        self.assertNotIn("Traceback", raw)
        self.assertIs(payload["actionable"], False)


if __name__ == "__main__":
    unittest.main()
