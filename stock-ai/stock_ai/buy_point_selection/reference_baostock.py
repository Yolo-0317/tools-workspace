"""BaoStock adapter for dated security names and trade status."""

from __future__ import annotations

from contextlib import contextmanager, redirect_stdout
from datetime import date
from decimal import Decimal
from io import StringIO
from typing import Any

from .reference_sources import IndexBar, ProviderFailure, SecurityStatus


def _code6(value: object) -> str:
    raw = str(value or "").strip().split(".")[-1]
    if not raw.isdigit():
        raise ValueError("BaoStock code must end in digits")
    return raw.zfill(6)


def _is_sh_sz_equity(value: object) -> bool:
    raw = str(value or "").strip().lower()
    parts = raw.split(".")
    if len(parts) != 2 or not parts[1].isdigit():
        return False
    market, code = parts
    return (market == "sh" and code.startswith("6")) or (
        market == "sz" and code.startswith(("0", "300", "301"))
    )


class BaoStockReferenceProvider:
    provider_name = "BAOSTOCK"

    def __init__(
        self,
        *,
        sdk: Any | None = None,
        socket_context: Any | None = None,
        sdk_constants: Any | None = None,
        socket_timeout_seconds: float = 15.0,
        query_page_size: int = 10000,
    ) -> None:
        if sdk is None:
            import baostock as bs
            import baostock.common.contants as bs_constants
            import baostock.common.context as bs_context

            sdk = bs
            socket_context = socket_context or bs_context
            sdk_constants = sdk_constants or bs_constants
        if socket_timeout_seconds <= 0:
            raise ValueError("socket_timeout_seconds must be positive")
        if query_page_size <= 0:
            raise ValueError("query_page_size must be positive")
        self._sdk = sdk
        self._socket_context = socket_context
        self._sdk_constants = sdk_constants
        self._socket_timeout_seconds = socket_timeout_seconds
        self._query_page_size = query_page_size
        self._session_active = False

    @contextmanager
    def session(self):
        if self._session_active:
            yield self
            return
        previous_page_size = None
        if self._sdk_constants is not None:
            previous_page_size = self._sdk_constants.BAOSTOCK_PER_PAGE_COUNT
            self._sdk_constants.BAOSTOCK_PER_PAGE_COUNT = self._query_page_size
        try:
            with redirect_stdout(StringIO()):
                self._login()
        except Exception:
            if previous_page_size is not None:
                self._sdk_constants.BAOSTOCK_PER_PAGE_COUNT = previous_page_size
            raise
        self._session_active = True
        try:
            yield self
        finally:
            with redirect_stdout(StringIO()):
                self._logout()
            self._session_active = False
            if previous_page_size is not None:
                self._sdk_constants.BAOSTOCK_PER_PAGE_COUNT = previous_page_size

    def fetch_security_statuses(self, day: date) -> tuple[SecurityStatus, ...]:
        with redirect_stdout(StringIO()):
            if self._session_active:
                return self._query_security_statuses(day)
            with self.session():
                return self._query_security_statuses(day)

    def fetch_index_bars(
        self, code: str, start: date, end: date
    ) -> tuple[IndexBar, ...]:
        if end < start:
            raise ValueError("index history end precedes start")
        with redirect_stdout(StringIO()):
            if self._session_active:
                return self._query_index_bars(code, start, end)
            with self.session():
                return self._query_index_bars(code, start, end)

    def _login(self) -> None:
        try:
            login = self._sdk.login()
        except Exception as exc:
            raise ProviderFailure(
                self.provider_name, "login", "PROVIDER_UNAVAILABLE"
            ) from exc
        if str(getattr(login, "error_code", "")) != "0":
            raise ProviderFailure(
                self.provider_name, "login", "PROVIDER_AUTH_FAILED"
            )
        socket = getattr(self._socket_context, "default_socket", None)
        if socket is not None:
            socket.settimeout(self._socket_timeout_seconds)

    def _logout(self) -> None:
        try:
            self._sdk.logout()
        except Exception:
            pass

    def _query_security_statuses(self, day: date) -> tuple[SecurityStatus, ...]:
        try:
            result = self._sdk.query_all_stock(day=day.isoformat())
            if str(getattr(result, "error_code", "")) != "0":
                raise ProviderFailure(
                    self.provider_name, "query_all_stock", "PROVIDER_UNAVAILABLE"
                )
            fields = [str(value) for value in getattr(result, "fields", ())]
            required = {"code", "tradeStatus", "code_name"}
            if not required.issubset(fields):
                raise ProviderFailure(
                    self.provider_name,
                    "query_all_stock",
                    "PROVIDER_SCHEMA_CHANGED",
                )
            positions = {name: fields.index(name) for name in required}
            rows: list[SecurityStatus] = []
            seen: set[str] = set()
            while result.next():
                raw = list(result.get_row_data())
                if len(raw) != len(fields):
                    raise ProviderFailure(
                        self.provider_name,
                        "query_all_stock",
                        "PROVIDER_SCHEMA_CHANGED",
                    )
                raw_code = raw[positions["code"]]
                if not _is_sh_sz_equity(raw_code):
                    continue
                code = _code6(raw_code)
                if code in seen:
                    raise ProviderFailure(
                        self.provider_name,
                        "query_all_stock",
                        "PROVIDER_SCHEMA_CHANGED",
                    )
                seen.add(code)
                rows.append(
                    SecurityStatus(
                        code=code,
                        name=str(raw[positions["code_name"]]).strip(),
                        trade_status=str(raw[positions["tradeStatus"]]).strip(),
                        trade_date=day,
                    )
                )
            return tuple(sorted(rows, key=lambda row: row.code))
        except ProviderFailure:
            raise
        except Exception as exc:
            raise ProviderFailure(
                self.provider_name, "query_all_stock", "PROVIDER_UNAVAILABLE"
            ) from exc

    def _query_index_bars(
        self, code: str, start: date, end: date
    ) -> tuple[IndexBar, ...]:
        try:
            result = self._sdk.query_history_k_data_plus(
                code,
                "date,close,pctChg",
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                frequency="d",
                adjustflag="3",
            )
            if str(getattr(result, "error_code", "")) != "0":
                raise ProviderFailure(
                    self.provider_name,
                    "query_history_k_data_plus",
                    "PROVIDER_UNAVAILABLE",
                )
            fields = [str(value) for value in getattr(result, "fields", ())]
            required = {"date", "close", "pctChg"}
            if not required.issubset(fields):
                raise ProviderFailure(
                    self.provider_name,
                    "query_history_k_data_plus",
                    "PROVIDER_SCHEMA_CHANGED",
                )
            positions = {name: fields.index(name) for name in required}
            rows: list[IndexBar] = []
            seen: set[date] = set()
            while result.next():
                raw = list(result.get_row_data())
                if len(raw) != len(fields):
                    raise ProviderFailure(
                        self.provider_name,
                        "query_history_k_data_plus",
                        "PROVIDER_SCHEMA_CHANGED",
                    )
                trade_date = date.fromisoformat(str(raw[positions["date"]]))
                close = Decimal(str(raw[positions["close"]]))
                pct_chg = Decimal(str(raw[positions["pctChg"]] or "0"))
                if (
                    trade_date in seen
                    or not start <= trade_date <= end
                    or close <= 0
                ):
                    raise ProviderFailure(
                        self.provider_name,
                        "query_history_k_data_plus",
                        "PROVIDER_SCHEMA_CHANGED",
                    )
                seen.add(trade_date)
                rows.append(IndexBar(code, trade_date, close, pct_chg))
            return tuple(sorted(rows, key=lambda value: value.trade_date))
        except ProviderFailure:
            raise
        except Exception as exc:
            raise ProviderFailure(
                self.provider_name,
                "query_history_k_data_plus",
                "PROVIDER_UNAVAILABLE",
            ) from exc
