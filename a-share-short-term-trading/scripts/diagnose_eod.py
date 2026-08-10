#!/usr/bin/env python3
"""Build an end-of-day trade-plan draft from local daily bars and a chip snapshot."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.daily_sync import SqlAlchemyDailyBarRepository, normalize_code
from short_term_trading.diagnosis import RiskProfile, build_eod_trade_plan
from short_term_trading.evidence import SqlAlchemyEvidenceRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an EOD A-share trade-plan draft")
    parser.add_argument("--code", required=True)
    parser.add_argument("--risk-budget", type=float, default=500.0)
    parser.add_argument("--ticket-limit", type=float, default=4000.0)
    parser.add_argument("--remaining-exposure", type=float, default=4000.0)
    args = parser.parse_args()
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        parser.error("MYSQL_URL is required")
    code = normalize_code(args.code)
    daily_repository = SqlAlchemyDailyBarRepository(mysql_url)
    evidence_repository = SqlAlchemyEvidenceRepository(mysql_url)
    plan = build_eod_trade_plan(
        code,
        daily_repository.get_recent_bars(code, 120),
        evidence_repository.get_latest_valid_snapshot(code, "chip"),
        profile=RiskProfile(args.risk_budget, args.ticket_limit, args.remaining_exposure),
        now=datetime.now(timezone.utc),
    )
    print(json.dumps(plan.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
