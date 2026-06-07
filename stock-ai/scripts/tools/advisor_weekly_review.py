#!/usr/bin/env python3
"""投顾周五周复盘 — 生成、落库、写 output/advisor_weekly/*.md"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()


def main() -> int:
    parser = argparse.ArgumentParser(description="投顾周五周复盘")
    parser.add_argument("--date", help="复盘基准日 YYYY-MM-DD（默认今日）")
    parser.add_argument("--no-ai", action="store_true", help="跳过 DeepSeek 投后陪伴段")
    parser.add_argument("--save", action="store_true", help="写入 MySQL + output 文件")
    parser.add_argument("--print-only", action="store_true", help="仅 stdout，不落库")
    args = parser.parse_args()

    review_date = date.fromisoformat(args.date[:10]) if args.date else None

    from stock_ai.advisor_weekly_review import (
        build_weekly_review_report,
        save_weekly_review,
        write_weekly_review_file,
    )

    report = build_weekly_review_report(
        review_date=review_date,
        with_ai=not args.no_ai,
    )

    if args.save and not args.print_only:
        try:
            save_weekly_review(report, review_date=review_date)
            path = write_weekly_review_file(report, root=ROOT)
            print(f"💾 MySQL advisor_weekly_reviews · 文件 {path}", file=sys.stderr)
        except Exception as exc:
            print(f"⚠️ 落库失败（仍输出正文）: {exc}", file=sys.stderr)
            write_weekly_review_file(report, root=ROOT)

    print(report["report_md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
