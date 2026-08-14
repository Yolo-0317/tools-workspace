"""BaoStock adapter for dated security names and trade status."""

from __future__ import annotations

from datetime import date
from typing import Any

from .reference_sources import ProviderFailure, SecurityStatus


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

    def __init__(self, *, sdk: Any | None = None) -> None:
        if sdk is None:
            import baostock as bs

            sdk = bs
        self._sdk = sdk

    def fetch_security_statuses(self, day: date) -> tuple[SecurityStatus, ...]:
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

        try:
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
        finally:
            try:
                self._sdk.logout()
            except Exception:
                pass
