#!/usr/bin/env python3
"""Manually sync point-in-time references required by buy-point selection."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
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


def _date_arg(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须为 YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步买点选股点时参考数据")
    parser.add_argument("--start", type=_date_arg, required=True)
    parser.add_argument("--end", type=_date_arg, required=True)
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(ROOT / ".env", override=False)
    try:
        engine = _engine()
        trade_dates = _trade_dates(engine, args.start, args.end)
        if not trade_dates:
            raise RuntimeError("指定区间没有 MySQL 交易日")
        runs = sync_reference_data(
            _pro(),
            SQLReferenceRepository(engine),
            trade_dates,
            captured_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001 - CLI exposes a safe single-line failure
        print(f"点时参考数据同步失败：{type(exc).__name__}: {exc}")
        return 2
    for run in runs:
        print(
            f"{run.dataset}: {run.status}, rows={run.row_count}, "
            f"range={run.start_date.isoformat()}..{run.end_date.isoformat()}"
        )
    return 0 if all(run.status == "COMPLETE" for run in runs) else 2


if __name__ == "__main__":
    raise SystemExit(main())
