#!/usr/bin/env python3
"""[已废弃] 战报微信推送已移除，本脚本不再使用。"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "⚠️  QClaw daily_briefing 补丁已废弃；请使用 sync_macro_news + com.user.stock-macro-news-sync",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
