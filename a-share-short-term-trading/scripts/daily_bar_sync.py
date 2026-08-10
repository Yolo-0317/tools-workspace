#!/usr/bin/env python3
"""Synchronize a small critical-symbol daily-bar set into MySQL."""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.daily_sync import SqlAlchemyDailyBarRepository, synchronize_critical_daily_bars


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync critical A-share daily bars")
    parser.add_argument("--scope", choices=("critical", "universe"), required=True)
    parser.add_argument("--codes", default="")
    parser.add_argument("--target-date", default="auto")
    parser.add_argument("--lookback-bars", type=int, default=120)
    parser.add_argument("--repair-days", type=int, default=3)
    parser.add_argument("--source-policy", default="mysql_then_opencli")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", choices=("json",), default="json")
    args = parser.parse_args()

    if args.scope != "critical":
        parser.error("universe is check-only and is not implemented in the MVP")
    if args.source_policy != "mysql_then_opencli":
        parser.error("MVP only supports mysql_then_opencli")
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        parser.error("MYSQL_URL is required")
    target = None if args.target_date == "auto" else date.fromisoformat(args.target_date)
    codes = [code.strip() for code in args.codes.split(",") if code.strip()]
    repository = SqlAlchemyDailyBarRepository(mysql_url)
    result = synchronize_critical_daily_bars(
        repository,
        codes,
        target_date=target,
        lookback_bars=args.lookback_bars,
        repair_days=args.repair_days,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result["status"] in {"READY", "UPDATED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
