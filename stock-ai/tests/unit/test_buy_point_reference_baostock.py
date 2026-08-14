from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from stock_ai.buy_point_selection.reference_baostock import BaoStockReferenceProvider
from stock_ai.buy_point_selection.reference_sources import ProviderFailure


class Result:
    def __init__(self, error_code: str = "0", error_msg: str = "") -> None:
        self.error_code = error_code
        self.error_msg = error_msg


class QueryResult(Result):
    def __init__(self, rows, *, fields=None, fail_during_iteration=False) -> None:
        super().__init__()
        self.fields = fields or ["code", "tradeStatus", "code_name"]
        self._rows = list(rows)
        self._index = -1
        self._fail_during_iteration = fail_during_iteration

    def next(self):
        self._index += 1
        if self._fail_during_iteration and self._index == 1:
            raise RuntimeError("socket closed with secret provider detail")
        return self._index < len(self._rows)

    def get_row_data(self):
        return list(self._rows[self._index])


class FakeBaoStock:
    def __init__(
        self,
        rows=(),
        *,
        login_code="0",
        query_code="0",
        fields=None,
        fail_during_iteration=False,
    ) -> None:
        self.login_code = login_code
        self.query_code = query_code
        self.rows = rows
        self.fields = fields
        self.fail_during_iteration = fail_during_iteration
        self.login_calls = 0
        self.logout_calls = 0
        self.requested_days = []

    def login(self):
        self.login_calls += 1
        return Result(self.login_code, "login detail")

    def logout(self):
        self.logout_calls += 1
        return Result()

    def query_all_stock(self, *, day):
        self.requested_days.append(day)
        result = QueryResult(
            self.rows,
            fields=self.fields,
            fail_during_iteration=self.fail_during_iteration,
        )
        result.error_code = self.query_code
        return result


def test_baostock_adapter_logs_out_and_preserves_requested_day() -> None:
    """Catches current-day fallback or a successful query leaking its SDK session."""
    sdk = FakeBaoStock(
        rows=[("sh.600001", "1", "*ST 示例"), ("sz.000002", "0", "普通股份")]
    )

    rows = BaoStockReferenceProvider(sdk=sdk).fetch_security_statuses(
        date(2025, 8, 6)
    )

    assert [(row.code, row.name, row.trade_status) for row in rows] == [
        ("000002", "普通股份", "0"),
        ("600001", "*ST 示例", "1"),
    ]
    assert all(row.trade_date == date(2025, 8, 6) for row in rows)
    assert sdk.requested_days == ["2025-08-06"]
    assert sdk.login_calls == 1 and sdk.logout_calls == 1


def test_baostock_maps_fields_by_name_not_position() -> None:
    """Catches an upstream field reorder assigning names to trade status."""
    sdk = FakeBaoStock(
        rows=[("普通股份", "sh.600001", "0")],
        fields=["code_name", "code", "tradeStatus"],
    )

    row = BaoStockReferenceProvider(sdk=sdk).fetch_security_statuses(
        date(2025, 8, 6)
    )[0]

    assert (row.code, row.name, row.trade_status) == ("600001", "普通股份", "0")


@pytest.mark.parametrize(
    ("sdk", "error_code"),
    [
        (FakeBaoStock(login_code="10001001"), "PROVIDER_AUTH_FAILED"),
        (FakeBaoStock(query_code="10002007"), "PROVIDER_UNAVAILABLE"),
        (
            FakeBaoStock(rows=[("sh.600001", "1", "普通股份")], fields=["code"]),
            "PROVIDER_SCHEMA_CHANGED",
        ),
    ],
)
def test_baostock_failures_use_safe_codes(sdk, error_code: str) -> None:
    """Catches raw SDK messages being persisted or malformed rows marked complete."""
    with pytest.raises(ProviderFailure) as caught:
        BaoStockReferenceProvider(sdk=sdk).fetch_security_statuses(date(2025, 8, 6))

    assert caught.value.error_code == error_code
    assert error_code in str(caught.value)


def test_baostock_logs_out_when_iteration_fails() -> None:
    """Catches a half-read provider result leaving the shared session open."""
    sdk = FakeBaoStock(
        rows=[("sh.600001", "1", "普通股份"), ("sh.600002", "1", "普通股份")],
        fail_during_iteration=True,
    )

    with pytest.raises(ProviderFailure) as caught:
        BaoStockReferenceProvider(sdk=sdk).fetch_security_statuses(date(2025, 8, 6))

    assert caught.value.error_code == "PROVIDER_UNAVAILABLE"
    assert sdk.logout_calls == 1


def test_baostock_rejects_duplicate_codes() -> None:
    """Catches duplicated rows inflating the daily coverage numerator."""
    sdk = FakeBaoStock(
        rows=[("sh.600001", "1", "普通股份"), ("sh.600001", "1", "普通股份")]
    )

    with pytest.raises(ProviderFailure) as caught:
        BaoStockReferenceProvider(sdk=sdk).fetch_security_statuses(date(2025, 8, 6))

    assert caught.value.error_code == "PROVIDER_SCHEMA_CHANGED"


def test_baostock_ignores_index_rows_before_six_digit_duplicate_check() -> None:
    """Catches sh.000001 index colliding with the sz.000001 listed company."""
    sdk = FakeBaoStock(
        rows=[
            ("sh.000001", "1", "上证综合指数"),
            ("sz.000001", "1", "平安银行"),
            ("sh.600001", "1", "普通股份"),
            ("sz.399001", "1", "深证成份指数"),
        ]
    )

    rows = BaoStockReferenceProvider(sdk=sdk).fetch_security_statuses(
        date(2025, 8, 6)
    )

    assert [(row.code, row.name) for row in rows] == [
        ("000001", "平安银行"),
        ("600001", "普通股份"),
    ]


def test_baostock_sets_a_bounded_timeout_on_the_sdk_socket() -> None:
    class Socket:
        def __init__(self) -> None:
            self.timeouts = []

        def settimeout(self, value):
            self.timeouts.append(value)

    socket = Socket()
    sdk = FakeBaoStock(rows=[("sh.600001", "1", "普通股份")])
    provider = BaoStockReferenceProvider(
        sdk=sdk,
        socket_context=SimpleNamespace(default_socket=socket),
        socket_timeout_seconds=12.5,
    )

    provider.fetch_security_statuses(date(2025, 8, 6))

    assert socket.timeouts == [12.5]


def test_baostock_suppresses_sdk_console_noise(capsys) -> None:
    class NoisyBaoStock(FakeBaoStock):
        def login(self):
            print("login success with provider noise")
            return super().login()

        def logout(self):
            print("logout success with provider noise")
            return super().logout()

    provider = BaoStockReferenceProvider(
        sdk=NoisyBaoStock(rows=[("sh.600001", "1", "普通股份")])
    )

    provider.fetch_security_statuses(date(2025, 8, 6))

    assert capsys.readouterr().out == ""


def test_baostock_session_reuses_one_login_across_many_dates() -> None:
    sdk = FakeBaoStock(rows=[("sh.600001", "1", "普通股份")])
    provider = BaoStockReferenceProvider(sdk=sdk)

    with provider.session():
        provider.fetch_security_statuses(date(2025, 8, 5))
        provider.fetch_security_statuses(date(2025, 8, 6))

    assert sdk.login_calls == 1
    assert sdk.logout_calls == 1
    assert sdk.requested_days == ["2025-08-05", "2025-08-06"]
