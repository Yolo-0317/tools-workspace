#!/usr/bin/env python3
"""情绪周期日检自动采集 → MySQL（看板 emotion 页）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
load_dotenv()

from stock_ai.emotion_cycle_compute import sync_emotion_cycle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="情绪周期日检自动入库")
    parser.add_argument("--date", help="交易日 YYYY-MM-DD，默认按 slot 推断")
    parser.add_argument(
        "--slot",
        default="eod",
        choices=["pre_market", "intraday", "eod"],
        help="pre_market=盘前 / intraday=盘中 / eod=收盘",
    )
    args = parser.parse_args()

    try:
        stats = sync_emotion_cycle(trade_date=args.date, checklist_slot=args.slot)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    if stats.get("skipped"):
        out = {"ok": True, **stats}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    out = {"ok": True, **stats}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
