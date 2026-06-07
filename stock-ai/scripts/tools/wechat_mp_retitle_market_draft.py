#!/usr/bin/env python3
"""仅更新 market 草稿标题/摘要：从本地 body 缓存重建 HTML，禁止回写 API 拉取的 content。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    attach_cover_crop_fields,
    draft_update,
    mp_configured,
    pick_thumb_for_draft_kind,
)
from scripts.tools.wechat_mp_content import (
    _article_shell,
    _load_last_market_title,
    _market_digest,
    _market_title,
    _record_market_title,
    load_market_body_cache,
)
from scripts.tools.wechat_mp_draft_slots import get_slot_media_id

TZ = ZoneInfo("Asia/Shanghai")


def main() -> int:
    parser = argparse.ArgumentParser(description="安全更新 market 草稿标题（重建 UTF-8 HTML）")
    parser.add_argument("--edition", choices=("pre", "midday", "close"), default="pre")
    args = parser.parse_args()

    if not mp_configured():
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    cache = load_market_body_cache()
    if not cache:
        print(
            "❌ 无本地正文缓存 data/wechat_mp_market_body_cache.json；"
            "请先运行 wechat_mp_draft --kind market --edition …",
            file=sys.stderr,
        )
        return 1

    media_id = get_slot_media_id("market")
    if not media_id:
        print("❌ 无 market 槽位 media_id", file=sys.stderr)
        return 1

    body_text = str(cache.get("body_text") or "")
    now = datetime.now(TZ)
    peer = _load_last_market_title("close") if args.edition == "pre" else None
    new_title = _market_title(
        body_text,
        now=now,
        edition=args.edition,
        peer_title=peer,
    )
    new_digest = _market_digest(body_text, now=now, edition=args.edition)

    article = _article_shell(
        title=new_title,
        digest=new_digest,
        body_text=body_text,
        kind="market",
    )
    thumb, terr = pick_thumb_for_draft_kind("market")
    if terr:
        print(f"❌ 封面: {terr.get('errmsg')}", file=sys.stderr)
        return 1
    article["thumb_media_id"] = thumb or ""
    attach_cover_crop_fields(article, thumb_media_id=thumb or "")

    err = draft_update(media_id=media_id, article=article, index=0)
    if err:
        print(f"❌ 更新失败: {err}", file=sys.stderr)
        return 1

    _record_market_title(edition=args.edition, title=new_title)
    from scripts.tools.wechat_mp_content import _save_market_body_cache

    _save_market_body_cache(
        edition=args.edition,
        body_text=body_text,
        title=new_title,
        digest=new_digest,
    )

    old_title = str(cache.get("title") or "")
    print("OK 标题已安全更新（正文自本地缓存重建）")
    print(f"  旧: {old_title}")
    print(f"  新: {new_title}")
    print(f"  摘要: {new_digest}")
    if peer:
        print(f"  避开盘后: {peer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
