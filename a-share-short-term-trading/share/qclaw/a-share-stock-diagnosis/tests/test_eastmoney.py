from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from a_share_stock_diagnosis.cache import PublicDataCache
from a_share_stock_diagnosis.eastmoney import (
    AmbiguousSymbolError,
    DataSourceError,
    DataValidationError,
    EastmoneyClient,
    JsonHttpClient,
    MAX_RESPONSE_BYTES,
    QUOTE_URL,
)
from a_share_stock_diagnosis.models import Security


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FixtureTransport:
    def __init__(self, *, search=None, quote=None, daily=None) -> None:
        self.search = search
        self.quote = quote
        self.daily = daily

    def get_json(self, url, params, timeout=10.0):
        if "clist" in url:
            return self.search
        if "kline" in url:
            return self.daily
        return self.quote


class FailingTransport:
    def get_json(self, url, params, timeout=10.0):
        raise DataSourceError("NETWORK_ERROR", "fixture offline")


class FakeResponse:
    def __init__(self, body: bytes, content_length: int | None = None) -> None:
        self.body = body
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size: int) -> bytes:
        return self.body[:size]


class JsonHttpClientTests(unittest.TestCase):
    def test_http_client_parses_utf8_json_and_rejects_non_https(self) -> None:
        client = JsonHttpClient(lambda request, timeout: FakeResponse(b'{"ok":true}'))
        self.assertEqual(client.get_json(QUOTE_URL, {"q": "中文"}), {"ok": True})
        with self.assertRaisesRegex(DataSourceError, "HTTPS"):
            client.get_json("http://push2.eastmoney.com/data", {})

    def test_http_client_rejects_invalid_or_oversized_responses(self) -> None:
        invalid = JsonHttpClient(lambda request, timeout: FakeResponse(b"not-json"))
        with self.assertRaises(DataSourceError) as invalid_error:
            invalid.get_json(QUOTE_URL, {})
        self.assertEqual(invalid_error.exception.code, "INVALID_JSON")

        oversized = JsonHttpClient(
            lambda request, timeout: FakeResponse(b"{}", MAX_RESPONSE_BYTES + 1)
        )
        with self.assertRaises(DataSourceError) as size_error:
            oversized.get_json(QUOTE_URL, {})
        self.assertEqual(size_error.exception.code, "RESPONSE_TOO_LARGE")

    def test_http_client_uses_bounded_curl_fallback_after_urllib_transport_failure(self) -> None:
        def failing_opener(request, timeout):
            raise OSError("fixture transport closed")

        def successful_runner(arguments, **kwargs):
            self.assertIn("--max-filesize", arguments)
            self.assertNotIn("shell", kwargs)
            return subprocess.CompletedProcess(arguments, 0, b'{"ok":true}', b"")

        client = JsonHttpClient(failing_opener, curl_path="/usr/bin/curl", runner=successful_runner)
        self.assertEqual(client.get_json(QUOTE_URL, {}), {"ok": True})


class EastmoneyClientTests(unittest.TestCase):
    def test_six_digit_code_bypasses_search(self) -> None:
        client = EastmoneyClient(FixtureTransport(search=None, quote=load_fixture("quote_603011.json")))
        security = client.resolve_symbol("603011")
        self.assertEqual(security.code, "603011")
        self.assertEqual(security.market, "SH")
        self.assertEqual(security.name, "合锻智能")

    def test_exact_unique_name_resolves_supported_stock(self) -> None:
        client = EastmoneyClient(FixtureTransport(search=load_fixture("search_unique.json")))
        self.assertEqual(
            client.resolve_symbol("合锻智能"),
            Security(code="603011", market="SH", name="合锻智能"),
        )

    def test_ambiguous_name_returns_candidates_instead_of_guessing(self) -> None:
        client = EastmoneyClient(FixtureTransport(search=load_fixture("search_ambiguous.json")))
        with self.assertRaises(AmbiguousSymbolError) as caught:
            client.resolve_symbol("测试")
        self.assertEqual([item.code for item in caught.exception.candidates], ["600001", "000001"])

    def test_quote_scaling_and_timestamp(self) -> None:
        client = EastmoneyClient(FixtureTransport(quote=load_fixture("quote_603011.json")))
        quote = client.fetch_quote(Security("603011", "SH", "合锻智能"))
        self.assertEqual(quote.price, 23.95)
        self.assertEqual(quote.high, 24.84)
        self.assertEqual(quote.code, "603011")
        self.assertIsNotNone(quote.as_of.utcoffset())

    def test_daily_rows_preserve_turnover_and_sort_dates(self) -> None:
        client = EastmoneyClient(FixtureTransport(daily=load_fixture("daily_603011.json")))
        bars = client.fetch_daily_bars(Security("603011", "SH", "合锻智能"))
        self.assertEqual(len(bars), 3)
        self.assertEqual(bars[-1].trade_date.isoformat(), "2026-08-10")
        self.assertEqual(bars[-1].turnover_rate, 18.32)

    def test_mismatched_or_invalid_market_payload_is_rejected(self) -> None:
        wrong_code = load_fixture("daily_603011.json")
        wrong_code["data"]["code"] = "000001"
        invalid_ohlc = load_fixture("daily_603011.json")
        invalid_ohlc["data"]["klines"][-1] = (
            "2026-08-10,23.46,23.95,22.00,22.71,180000,430000000,9.39,5.60,1.27,18.32"
        )
        for payload in (wrong_code, invalid_ohlc, {"data": {"code": "603011", "klines": []}}):
            with self.subTest(payload=payload):
                client = EastmoneyClient(FixtureTransport(daily=payload))
                with self.assertRaises(DataValidationError):
                    client.fetch_daily_bars(Security("603011", "SH", "合锻智能"))

    def test_public_symbol_and_daily_cache_supports_a_second_offline_read(self) -> None:
        with TemporaryDirectory() as directory:
            cache = PublicDataCache(Path(directory))
            online = EastmoneyClient(
                FixtureTransport(
                    search=load_fixture("search_unique.json"),
                    daily=load_fixture("daily_603011.json"),
                ),
                cache=cache,
            )
            security = online.resolve_symbol("合锻智能")
            expected_bars = online.fetch_daily_bars(security)

            offline = EastmoneyClient(FailingTransport(), cache=cache)
            self.assertEqual(offline.resolve_symbol("合锻智能"), security)
            self.assertEqual(offline.fetch_daily_bars(security), expected_bars)


class PublicDataCacheTests(unittest.TestCase):
    def test_cache_expires_and_rejects_non_public_kinds(self) -> None:
        with TemporaryDirectory() as directory:
            cache = PublicDataCache(Path(directory))
            cache.write("symbols", "603011", {"code": "603011"})
            self.assertEqual(
                cache.read("symbols", "603011", max_age=timedelta(hours=24)),
                {"code": "603011"},
            )
            with self.assertRaises(ValueError):
                cache.write("holdings", "603011", {"shares": 500})

    def test_cache_files_never_receive_holding_fields(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cache = PublicDataCache(root)
            cache.write("daily", "603011-2026-08-10", load_fixture("daily_603011.json"))
            stored = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.json"))
            self.assertNotIn("shares", stored)
            self.assertNotIn("cost_price", stored)
            self.assertNotIn("available_shares", stored)


if __name__ == "__main__":
    unittest.main()
