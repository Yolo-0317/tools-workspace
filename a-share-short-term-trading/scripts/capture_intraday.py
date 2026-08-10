#!/usr/bin/env python3
"""Capture quote and fund-flow evidence for one intraday symbol."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.capture import capture_quote_and_fund
from short_term_trading.evidence import CaptureRecorder, SqlAlchemyEvidenceRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture intraday quote and fund-flow snapshots")
    parser.add_argument("--code", required=True)
    args = parser.parse_args()
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        parser.error("MYSQL_URL is required")
    capture_quote_and_fund(args.code, CaptureRecorder(SqlAlchemyEvidenceRepository(mysql_url)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
