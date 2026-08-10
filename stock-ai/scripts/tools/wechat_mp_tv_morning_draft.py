#!/usr/bin/env python3
"""11:00 话题讨论稿：选题预览 / 成稿 / 推草稿。"""

from __future__ import annotations

import argparse
import json
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()


def main() -> int:
    parser = argparse.ArgumentParser(description="11:00 热搜话题讨论稿")
    parser.add_argument("--preview", action="store_true", help="预览选题榜")
    parser.add_argument("--pick", action="store_true", help="打印今日选题 JSON")
    parser.add_argument("--dry-run", action="store_true", help="只构建不推送")
    parser.add_argument("--push", action="store_true", help="推草稿箱")
    args = parser.parse_args()

    if args.preview:
        from scripts.tools.wechat_mp_tv_morning_discussion import preview_morning_discussion

        print(preview_morning_discussion())
        return 0

    if args.pick:
        from scripts.tools.wechat_mp_tv_morning_discussion import pick_morning_discussion_topic

        print(json.dumps(pick_morning_discussion_topic(), ensure_ascii=False, indent=2))
        return 0

    if args.dry_run or args.push:
        import os

        os.environ.setdefault("WECHAT_MP_TV_PICK_MODE", "discussion")
        if args.dry_run:
            from scripts.tools.wechat_mp_content import build_article

            art = build_article("tv_review")
            print(f"标题: {art['title']}")
            print(f"摘要: {art['digest']}")
            print(art.get("body_text", "")[:800])
            return 0
        from scripts.tools.wechat_mp_draft_batch import run_batch

        return run_batch("tv_trial", dry_run=False, notify=True)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
