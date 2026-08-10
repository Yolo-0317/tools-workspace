#!/usr/bin/env python3
"""Verify a frozen EOD plan against persisted intraday evidence snapshots."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.diagnosis import TradePlanDraft
from short_term_trading.evidence import SqlAlchemyEvidenceRepository
from short_term_trading.intraday import IntradayRiskGate, verify_intraday_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an intraday A-share trade plan")
    parser.add_argument("--plan-json", required=True, help="EOD plan JSON file")
    parser.add_argument("--market-status", choices=("ALLOW", "LIMITED", "FREEZE"), required=True)
    parser.add_argument("--maximum-shares", type=int, required=True)
    parser.add_argument("--portfolio-approved", action="store_true")
    parser.add_argument("--is-holding", action="store_true")
    args = parser.parse_args()
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        parser.error("MYSQL_URL is required")
    with open(args.plan_json, encoding="utf-8") as file:
        plan = TradePlanDraft(**json.load(file))
    now = datetime.now(timezone.utc)
    repository = SqlAlchemyEvidenceRepository(mysql_url)
    code = plan.code
    decision = verify_intraday_plan(
        plan,
        quote=repository.get_latest_valid_snapshot(code, "quote"),
        fund_flow=repository.get_latest_valid_snapshot(code, "fund_flow"),
        sector=repository.get_latest_valid_snapshot(code, "sector"),
        chip=repository.get_latest_valid_snapshot(code, "chip"),
        order_books=repository.get_valid_snapshots_since(code, "order_book", now - timedelta(minutes=5)),
        risk_gate=IntradayRiskGate(args.market_status, args.portfolio_approved, args.maximum_shares),
        now=now,
        is_holding=args.is_holding,
    )
    print(json.dumps(decision.to_dict(), ensure_ascii=False))
    return 0 if decision.status in {"BUY_ALLOWED", "WAIT_ENTRY", "EXIT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
