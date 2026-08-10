"""Stable JSON command line interface for QClaw/OpenClaw."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from .cache import PublicDataCache
from .calendar import BundledTradingCalendar
from .decision import diagnose
from .eastmoney import AmbiguousSymbolError, DataSourceError, EastmoneyClient
from .session import classify_session
from .validation import validate_holding


SHANGHAI = ZoneInfo("Asia/Shanghai")
SKILL_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="无 MySQL 的 A 股个股与手工持仓诊断",
        exit_on_error=False,
    )
    parser.add_argument("--symbol", required=True, help="六位 A 股代码或股票名称")
    parser.add_argument("--shares", type=int)
    parser.add_argument("--cost-price", type=float)
    parser.add_argument("--available-shares", type=int)
    parser.add_argument("--output", choices=("json",), default="json")
    parser.add_argument("--at", help="仅用于复现测试的带时区 ISO 时间")
    return parser


def _error_payload(
    symbol: str,
    code: str,
    message: str,
    *,
    candidates: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "symbol": symbol,
        "name": "",
        "session": "UNAVAILABLE",
        "as_of": datetime.now(SHANGHAI).isoformat(),
        "diagnosis_trade_date": None,
        "data_freshness": "unavailable",
        "quote": None,
        "latest_bar": None,
        "indicators": {},
        "chip_estimate": None,
        "decision": "NO_TRADE",
        "actionable": False,
        "reason": message,
        "next_action": "修正输入或恢复数据源后重新诊断",
        "levels": {},
        "holding": None,
        "warnings": [],
        "source_refs": {},
        "errors": [{"code": code, "message": message}],
    }
    if candidates is not None:
        payload["candidates"] = candidates
    return payload


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def run(
    argv: Sequence[str] | None = None,
    *,
    client: Any | None = None,
    calendar: Any | None = None,
    now: datetime | None = None,
) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        selected_now = now or datetime.now(SHANGHAI)
        if args.at:
            selected_now = datetime.fromisoformat(args.at)
        if selected_now.tzinfo is None or selected_now.utcoffset() is None:
            raise ValueError("--at 必须包含时区")
        holding = validate_holding(args.shares, args.cost_price, args.available_shares)
    except (argparse.ArgumentError, ValueError) as exc:
        symbol = getattr(locals().get("args", None), "symbol", "")
        _emit(_error_payload(symbol, "INVALID_INPUT", str(exc)))
        return 2

    selected_client = client or EastmoneyClient(cache=PublicDataCache())
    selected_calendar = calendar or BundledTradingCalendar.load(
        SKILL_ROOT / "data" / "sse_trade_calendar_2026.json"
    )
    try:
        security = selected_client.resolve_symbol(args.symbol)
        context = classify_session(selected_now, selected_calendar)
        bars = selected_client.fetch_daily_bars(security, limit=210)
        current_quote = None
        if context.session == "INTRADAY" or holding is not None:
            try:
                current_quote = selected_client.fetch_quote(security)
            except DataSourceError:
                current_quote = None
        result = diagnose(
            security,
            context,
            bars,
            current_quote,
            holding,
            as_of=selected_now,
        )
        _emit(result.to_dict())
        return 0
    except AmbiguousSymbolError as exc:
        candidates = [
            {"code": item.code, "market": item.market, "name": item.name}
            for item in exc.candidates
        ]
        _emit(
            _error_payload(
                args.symbol,
                "AMBIGUOUS_SYMBOL",
                "股票名称对应多个候选，请提供六位代码",
                candidates=candidates,
            )
        )
        return 2
    except DataSourceError as exc:
        _emit(_error_payload(args.symbol, exc.code, exc.safe_message))
        return 3
    except (OSError, ValueError) as exc:
        _emit(_error_payload(args.symbol, "RUNTIME_CONFIGURATION_ERROR", str(exc)))
        return 3
    except Exception:
        print("诊断发生未预期错误，详细异常未写入标准输出", file=sys.stderr)
        _emit(_error_payload(args.symbol, "UNEXPECTED_RUNTIME_ERROR", "诊断运行异常"))
        return 4


def main() -> int:
    return run()
