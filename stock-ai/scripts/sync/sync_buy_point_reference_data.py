#!/usr/bin/env python3
"""Manually sync point-in-time references required by buy-point selection."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_ai.buy_point_selection.reference_data import (  # noqa: E402
    SQLReferenceRepository,
    sync_reference_data,
)
from stock_ai.buy_point_selection.reference_sources import ProviderFailure  # noqa: E402
from stock_ai.buy_point_selection.reference_sync import (  # noqa: E402
    AlternativeReferenceSyncRequest,
    sync_alternative_reference_data,
)
from stock_ai.market_codes import (  # noqa: E402
    is_sh_sz_main_board_code,
    normalize_code6,
)


def _date_arg(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须为 YYYY-MM-DD") from exc


def _end_arg(value: str) -> date | None:
    return None if value.strip().lower() == "latest" else _date_arg(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步买点选股点时参考数据")
    parser.add_argument("--start", type=_date_arg, required=True)
    parser.add_argument("--end", type=_end_arg, required=True)
    parser.add_argument(
        "--provider",
        choices=("cninfo-baostock", "tushare"),
        default="cninfo-baostock",
        help="参考数据提供器，默认使用巨潮资讯与 BaoStock",
    )
    return parser


def _engine():
    url = os.getenv("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    if not url:
        raise RuntimeError("未配置 MYSQL_URL")
    return create_engine(url, pool_pre_ping=True)


def _pro():
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("未配置 TUSHARE_TOKEN")
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api()


def _cninfo():
    from stock_ai.buy_point_selection.reference_cninfo import CninfoReferenceProvider

    return CninfoReferenceProvider()


def _baostock():
    from stock_ai.buy_point_selection.reference_baostock import BaoStockReferenceProvider

    return BaoStockReferenceProvider()


def _trade_dates(engine, start: date, end: date) -> tuple[date, ...]:
    if end < start:
        raise ValueError("结束日期不能早于开始日期")
    with engine.connect() as connection:
        values = connection.execute(
            text(
                "SELECT DISTINCT trade_date FROM stock_daily "
                "WHERE trade_date BETWEEN :start AND :end ORDER BY trade_date"
            ),
            {"start": start, "end": end},
        ).scalars()
        return tuple(values)


def _row_value(row: object, name: str):
    if isinstance(row, dict):
        return row[name]
    return getattr(row, name)


def _latest_observation_by_date(
    observed_dates: tuple[date, ...] | list[date],
    trade_dates: tuple[date, ...],
) -> dict[date, date | None]:
    """Resolve the latest non-future observation with one monotonic scan."""

    ordered = tuple(sorted(set(observed_dates)))
    pointer = 0
    latest = None
    resolved: dict[date, date | None] = {}
    for day in trade_dates:
        while pointer < len(ordered) and ordered[pointer] <= day:
            latest = ordered[pointer]
            pointer += 1
        resolved[day] = latest
    return resolved


def _universe_by_date(
    engine, trade_dates: tuple[date, ...], *, lookback_calendar_days: int = 180
) -> dict[date, frozenset[str]]:
    """Build each day's expected main-board universe with one bounded query."""

    if not trade_dates:
        return {}
    lookback_start = trade_dates[0] - timedelta(days=lookback_calendar_days)
    end_date = trade_dates[-1]
    with engine.connect() as connection:
        rows = list(
            connection.execute(
                text(
                    "SELECT ts_code, trade_date FROM stock_daily "
                    "WHERE trade_date BETWEEN :lookback_start AND :end_date "
                    "ORDER BY ts_code, trade_date"
                ),
                {"lookback_start": lookback_start, "end_date": end_date},
            ).mappings()
        )
    observed: dict[str, list[date]] = {}
    for row in rows:
        code = normalize_code6(str(_row_value(row, "ts_code")))
        if not is_sh_sz_main_board_code(code):
            continue
        raw_date = _row_value(row, "trade_date")
        trade_date = (
            raw_date
            if isinstance(raw_date, date)
            else date.fromisoformat(str(raw_date)[:10])
        )
        observed.setdefault(code, []).append(trade_date)
    universe: dict[date, set[str]] = {day: set() for day in trade_dates}
    for code, dates in observed.items():
        latest_by_date = _latest_observation_by_date(dates, trade_dates)
        for day, latest in latest_by_date.items():
            if latest is not None and latest >= day - timedelta(days=lookback_calendar_days):
                universe[day].add(code)
    return {day: frozenset(codes) for day, codes in universe.items()}


def _safe_cli_error(exc: Exception) -> str:
    return exc.error_code if isinstance(exc, ProviderFailure) else type(exc).__name__


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(ROOT / ".env", override=False)
    try:
        engine = _engine()
        trade_dates = _trade_dates(engine, args.start, args.end or date.today())
        if not trade_dates:
            raise RuntimeError("指定区间没有 MySQL 交易日")
        captured_at = datetime.now(timezone.utc)
        repository = SQLReferenceRepository(engine)
        if args.provider == "tushare":
            runs = sync_reference_data(
                _pro(),
                repository,
                trade_dates,
                captured_at=captured_at,
            )
        else:
            runs = sync_alternative_reference_data(
                AlternativeReferenceSyncRequest(
                    trade_dates=trade_dates,
                    universe_by_date=_universe_by_date(engine, trade_dates),
                    captured_at=captured_at,
                ),
                cninfo=_cninfo(),
                baostock=_baostock(),
                repository=repository,
            )
    except Exception as exc:  # noqa: BLE001 - CLI exposes a safe single-line failure
        print(f"点时参考数据同步失败：{_safe_cli_error(exc)}")
        return 2
    for run in runs:
        coverage = "n/a" if run.coverage_ratio is None else str(run.coverage_ratio)
        error = "" if run.error_code is None else f", error={run.error_code}"
        print(
            f"{run.dataset}[{run.provider}]: {run.status}, rows={run.row_count}, "
            f"coverage={coverage}, range={run.start_date.isoformat()}"
            f"..{run.end_date.isoformat()}{error}"
        )
    return 0 if all(run.status == "COMPLETE" for run in runs) else 2


if __name__ == "__main__":
    raise SystemExit(main())
