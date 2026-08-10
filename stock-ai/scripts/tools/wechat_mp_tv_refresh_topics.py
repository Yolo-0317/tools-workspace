#!/usr/bin/env python3
"""刷新影视试跑选题队列（网络 curated + 可选 TMDB trending）。"""

from __future__ import annotations

import argparse
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_tv_topics import format_topic_brief, refresh_tv_queue, rank_topics, CURATED_HOT
from scripts.tools.wechat_mp_tv_trend_topics import preview_tv_trends


def main() -> int:
    parser = argparse.ArgumentParser(description="刷新 HBO/Netflix 影视试跑选题")
    parser.add_argument("--no-tmdb", action="store_true", help="不拉 TMDB trending")
    parser.add_argument("--list", action="store_true", help="只列出 curated 排名，不写文件")
    parser.add_argument("--trends", action="store_true", help="只预览微博/百度影视热搜选题")
    args = parser.parse_args()

    if args.trends:
        print(preview_tv_trends(limit=10))
        return 0

    if args.list:
        for i, t in enumerate(rank_topics(CURATED_HOT), start=1):
            print(f"{i}. {format_topic_brief(t)}")
            print(f"   hook: {t.get('hook')}")
        return 0

    cfg = refresh_tv_queue(include_tmdb=not args.no_tmdb)
    queue = cfg.get("queue") or []
    print(f"✅ 已写入 {len(queue)} 条到 data/wechat_mp_tv_trial.json")
    for i, t in enumerate(queue[:10], start=1):
        print(f"{i}. {format_topic_brief(t)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
