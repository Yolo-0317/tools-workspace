#!/usr/bin/env python3
"""增长模型：周二/周五发表+转群提醒（微信 wechat-acp）。"""

from __future__ import annotations

import argparse
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_growth import is_distribution_day, send_publish_reminder


def main() -> int:
    parser = argparse.ArgumentParser(description="牛马也智能 · 发表/转群提醒")
    parser.add_argument(
        "--force",
        action="store_true",
        help="忽略是否转群日，强制发送",
    )
    args = parser.parse_args()
    if not args.force and not is_distribution_day():
        print("SKIP 非转群日（distribution.weekdays）", file=sys.stderr)
        return 0
    ok = send_publish_reminder(force=args.force)
    if not ok:
        print("WARN 提醒未发出（wechat-acp 或配置）", file=sys.stderr)
        return 1
    print("OK 发表/转群提醒已发送")
    return 0


if __name__ == "__main__":
    sys.exit(main())
