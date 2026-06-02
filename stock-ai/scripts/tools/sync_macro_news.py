#!/usr/bin/env python3
"""东财 7×24 快讯同步到 MySQL + Cursor AI 解读（launchd 每 15 分钟）。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.fetch_eastmoney_macro_news import fetch_macro_news
from scripts.tools.news_ai_interpret import save_news_ai_snapshot
from scripts.tools.news_db import (
    record_fetch_run,
    refresh_sentiment_for_recent,
    upsert_news_items,
)

TZ = ZoneInfo("Asia/Shanghai")


def sync_once(*, limit: int = 40, news_limit: int = 8, skip_ai: bool = False) -> int:
    os.environ.setdefault("LLM_BACKEND", "cursor")

    started = datetime.now(TZ)
    item_count = 0
    new_count = 0
    error_msg: str | None = None
    ok = False
    items = []

    try:
        items = fetch_macro_news(limit=limit, include_home=True)
        item_count, new_count = upsert_news_items(items, now=started)
        refreshed = refresh_sentiment_for_recent(hours=72)
        ok = True
        print(
            f"OK 快讯同步 {started.strftime('%H:%M:%S')} "
            f"抓取 {item_count} 条，新增 {new_count} 条"
            + (f"，情绪标记刷新 {refreshed} 条" if refreshed else "")
        )
    except Exception as exc:  # noqa: BLE001
        error_msg = str(exc)
        print(f"⚠️ 快讯同步失败: {exc}", file=sys.stderr)

    finished = datetime.now(TZ)
    record_fetch_run(
        started_at=started,
        finished_at=finished,
        item_count=item_count,
        new_count=new_count,
        ok=ok,
        error_msg=error_msg,
    )

    if skip_ai or not items:
        return 0

    try:
        ai_summary = save_news_ai_snapshot(items, news_limit=news_limit, now=started)
        first_line = ai_summary.splitlines()[0] if ai_summary else "（空）"
        print(f"OK AI 解读 {first_line}")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ AI 解读失败: {exc}", file=sys.stderr)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="同步东财宏观快讯到 MySQL 并生成 AI 解读")
    parser.add_argument("--limit", type=int, default=40, help="单次抓取条数上限")
    parser.add_argument("--news-limit", type=int, default=8, help="AI 解读使用的国内要闻条数")
    parser.add_argument("--skip-ai", action="store_true", help="仅同步快讯，跳过 AI")
    args = parser.parse_args()
    return sync_once(limit=args.limit, news_limit=args.news_limit, skip_ai=args.skip_ai)


if __name__ == "__main__":
    raise SystemExit(main())
