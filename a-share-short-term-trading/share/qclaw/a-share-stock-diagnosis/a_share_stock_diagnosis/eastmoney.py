"""Validated access to public Eastmoney quote and daily-bar endpoints."""

from __future__ import annotations

from datetime import date, datetime
import json
import math
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .models import DailyBar, Quote, Security
from .validation import market_for_code, normalize_code


SHANGHAI = ZoneInfo("Asia/Shanghai")
QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
DAILY_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
STOCK_LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class DataSourceError(RuntimeError):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class DataValidationError(DataSourceError):
    pass


class AmbiguousSymbolError(ValueError):
    def __init__(self, candidates: list[Security]) -> None:
        super().__init__("股票名称对应多个候选，请提供六位代码")
        self.candidates = candidates


class JsonHttpClient:
    def __init__(self, opener=urlopen) -> None:
        self._opener = opener

    def get_json(
        self,
        url: str,
        params: Mapping[str, str],
        timeout: float = 10.0,
    ) -> Any:
        if not url.startswith("https://"):
            raise DataSourceError("UNSAFE_URL", "行情地址不是 HTTPS")
        request = Request(
            f"{url}?{urlencode(params)}",
            headers={"User-Agent": "Mozilla/5.0 QClaw-A-Share-Diagnosis/1.0"},
        )
        try:
            with self._opener(request, timeout=timeout) as response:
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > MAX_RESPONSE_BYTES:
                    raise DataSourceError("RESPONSE_TOO_LARGE", "行情响应超过大小限制")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except DataSourceError:
            raise
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise DataSourceError("NETWORK_ERROR", "公开行情接口暂时不可用") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise DataSourceError("RESPONSE_TOO_LARGE", "行情响应超过大小限制")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DataSourceError("INVALID_JSON", "公开行情响应格式异常") from exc


def _secid(security: Security) -> str:
    return f"{1 if security.market == 'SH' else 0}.{security.code}"


def _finite_number(value: Any, field: str, *, positive: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DataValidationError("INVALID_FIELD", f"行情字段 {field} 无效") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        raise DataValidationError("INVALID_FIELD", f"行情字段 {field} 无效")
    return result


class EastmoneyClient:
    def __init__(self, transport: Any | None = None) -> None:
        self.transport = transport or JsonHttpClient()

    def _quote_payload(self, security: Security) -> dict[str, Any]:
        payload = self.transport.get_json(
            QUOTE_URL,
            {
                "secid": _secid(security),
                "fltt": "2",
                "fields": "f43,f44,f45,f46,f57,f58,f60,f86,f168,f170",
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise DataValidationError("MISSING_QUOTE", "未获得有效实时行情")
        return data

    def resolve_symbol(self, value: str) -> Security:
        try:
            code = normalize_code(value)
        except ValueError:
            return self._resolve_name(value)
        placeholder = Security(code=code, market=market_for_code(code), name="")
        data = self._quote_payload(placeholder)
        if str(data.get("f57") or "") != code:
            raise DataValidationError("SYMBOL_MISMATCH", "行情代码与请求不一致")
        name = str(data.get("f58") or "").strip()
        if not name:
            raise DataValidationError("MISSING_NAME", "行情未返回股票名称")
        return Security(code=code, market=placeholder.market, name=name)

    def _resolve_name(self, value: str) -> Security:
        query = str(value).strip()
        if not query:
            raise ValueError("股票名称不能为空")
        payload = self.transport.get_json(
            STOCK_LIST_URL,
            {
                "pn": "1",
                "pz": "6000",
                "po": "1",
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fid": "f12",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                "fields": "f12,f13,f14",
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        rows = data.get("diff") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise DataValidationError("MISSING_SYMBOL_LIST", "未获得有效证券列表")
        candidates: list[Security] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("f12") or "")
            name = str(row.get("f14") or "").strip()
            if query not in name:
                continue
            try:
                normalized = normalize_code(code)
            except ValueError:
                continue
            candidates.append(Security(normalized, market_for_code(normalized), name))
        exact = [item for item in candidates if item.name == query]
        if len(exact) == 1:
            return exact[0]
        selected = exact or candidates
        if not selected:
            raise DataValidationError("SYMBOL_NOT_FOUND", "未找到匹配的沪深 A 股")
        if len(selected) > 1:
            raise AmbiguousSymbolError(selected[:10])
        return selected[0]

    def fetch_quote(self, security: Security) -> Quote:
        data = self._quote_payload(security)
        if str(data.get("f57") or "") != security.code:
            raise DataValidationError("SYMBOL_MISMATCH", "行情代码与请求不一致")
        name = str(data.get("f58") or "").strip()
        price = _finite_number(data.get("f43"), "price", positive=True)
        high = _finite_number(data.get("f44"), "high", positive=True)
        low = _finite_number(data.get("f45"), "low", positive=True)
        open_ = _finite_number(data.get("f46"), "open", positive=True)
        previous_close = _finite_number(data.get("f60"), "previous_close", positive=True)
        if high < max(price, open_, low) or low > min(price, open_, high):
            raise DataValidationError("INVALID_OHLC", "实时行情价格关系无效")
        timestamp = int(_finite_number(data.get("f86"), "timestamp", positive=True))
        return Quote(
            code=security.code,
            name=name or security.name,
            price=price,
            open=open_,
            high=high,
            low=low,
            previous_close=previous_close,
            change_pct=_finite_number(data.get("f170"), "change_pct"),
            turnover_rate=_finite_number(data.get("f168"), "turnover_rate"),
            as_of=datetime.fromtimestamp(timestamp, tz=SHANGHAI),
        )

    def fetch_daily_bars(self, security: Security, limit: int = 210) -> list[DailyBar]:
        if not 20 <= limit <= 1000:
            raise ValueError("日线数量必须在 20..1000")
        payload = self.transport.get_json(
            DAILY_URL,
            {
                "secid": _secid(security),
                "klt": "101",
                "fqt": "0",
                "lmt": str(limit),
                "end": "20500101",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or str(data.get("code") or "") != security.code:
            raise DataValidationError("SYMBOL_MISMATCH", "日线代码与请求不一致")
        rows = data.get("klines")
        if not isinstance(rows, list) or not rows:
            raise DataValidationError("MISSING_DAILY_BARS", "未获得有效日线")
        bars = [self._parse_bar(item) for item in rows]
        dates = [item.trade_date for item in bars]
        if len(dates) != len(set(dates)):
            raise DataValidationError("DUPLICATE_DATES", "日线包含重复交易日")
        return sorted(bars, key=lambda item: item.trade_date)

    @staticmethod
    def _parse_bar(row: Any) -> DailyBar:
        values = str(row).split(",")
        if len(values) < 11:
            raise DataValidationError("INVALID_KLINE", "日线字段数量不足")
        try:
            trade_date = date.fromisoformat(values[0])
        except ValueError as exc:
            raise DataValidationError("INVALID_KLINE_DATE", "日线日期无效") from exc
        open_ = _finite_number(values[1], "open", positive=True)
        close = _finite_number(values[2], "close", positive=True)
        high = _finite_number(values[3], "high", positive=True)
        low = _finite_number(values[4], "low", positive=True)
        if high < max(open_, close, low) or low > min(open_, close, high):
            raise DataValidationError("INVALID_OHLC", "日线价格关系无效")
        volume = _finite_number(values[5], "volume")
        amount = _finite_number(values[6], "amount")
        turnover = _finite_number(values[10], "turnover_rate")
        if min(volume, amount, turnover) < 0:
            raise DataValidationError("INVALID_KLINE", "日线成交字段不能为负")
        return DailyBar(
            trade_date=trade_date,
            open=open_,
            close=close,
            high=high,
            low=low,
            volume=volume,
            amount=amount,
            change_pct=_finite_number(values[8], "change_pct"),
            turnover_rate=turnover,
        )
