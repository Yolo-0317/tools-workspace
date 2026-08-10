#!/usr/bin/env python3
"""只读核对公众号已发表记录，并同步栀夏正式发表台账。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import list_all_freepublish
from scripts.tools.wechat_mp_virtual_ledger import (
    HISTORY_PATH,
    PENDING_PATH,
    match_pending_publication,
    record_verified_publication,
)


def _load_pending(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"栀夏待发表记录无效: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"栀夏待发表记录结构无效: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="同步栀夏正式发表计数（只读公众号）")
    parser.add_argument("--pending", type=Path, default=PENDING_PATH)
    parser.add_argument("--history", type=Path, default=HISTORY_PATH)
    args = parser.parse_args()
    try:
        pending = _load_pending(args.pending)
        if not pending:
            print("NO_PENDING")
            return 0
        publications, error = list_all_freepublish()
        if error:
            print(f"错误: 拉取已发表记录失败: {error}", file=sys.stderr)
            return 1
        publication = match_pending_publication(pending, publications)
        if publication is None:
            print("NO_MATCH")
            return 0
        ledger = record_verified_publication(
            pending=pending,
            publication=publication,
            ledger_path=args.history,
        )
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    article_id = str(publication.get("article_id") or "")
    post = next(item for item in ledger["posts"] if item["article_id"] == article_id)
    print(f"SYNCED {post['post_no']} · {post['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
