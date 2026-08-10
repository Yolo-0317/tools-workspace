#!/usr/bin/env python3
"""增长模型 CLI：大行情判定、周焦点、发表清单。"""

from __future__ import annotations

import argparse
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_draft_batch import resolve_scheduled_batch
from scripts.tools.wechat_mp_growth import format_growth_check_report


def main() -> int:
    parser = argparse.ArgumentParser(description="牛马也智能 · 增长模型检查")
    parser.add_argument(
        "--batch",
        choices=("evening", "weekend", "weekend_skip", "auto"),
        default="auto",
        help="auto=按日历解析",
    )
    args = parser.parse_args()
    batch = resolve_scheduled_batch() if args.batch == "auto" else args.batch
    print(format_growth_check_report(batch=batch if batch != "weekend_skip" else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
