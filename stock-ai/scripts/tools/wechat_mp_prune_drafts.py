#!/usr/bin/env python3
"""清理公众号草稿箱：删除本脚本产生的多余草稿（保留三槽位）。"""

from __future__ import annotations

import argparse
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    draft_delete,
    draft_first_title,
    list_all_drafts,
    mp_configured,
)
from scripts.tools.wechat_mp_content import is_obsolete_draft_title
from scripts.tools.wechat_mp_draft_slots import (
    DRAFT_KINDS,
    get_slot_media_id,
    is_managed_draft_title,
    prune_extra_managed_drafts,
)


def prune_obsolete_drafts(*, dry_run: bool = False) -> int:
    """删除旧版标题 + 非槽位的管理类草稿。"""
    items, err = list_all_drafts()
    if err:
        print(f"❌ 拉取草稿列表失败: {err}", file=sys.stderr)
        return 1

    keep = {mid for k in DRAFT_KINDS if (mid := get_slot_media_id(k))}
    to_delete: list[tuple[str, str, str]] = []

    for it in items:
        media_id = str(it.get("media_id") or "")
        title = draft_first_title(it)
        reason = ""
        if media_id in keep:
            continue
        if is_obsolete_draft_title(title):
            reason = "旧版标题"
        elif is_managed_draft_title(title):
            reason = "重复槽位"
        else:
            continue
        to_delete.append((media_id, title, reason))

    if not to_delete:
        print("OK 无待清理草稿")
        return 0

    print(f"将{'预览' if dry_run else '删除'} {len(to_delete)} 篇：")
    for media_id, title, reason in to_delete:
        print(f"  · [{reason}] {title}")
        print(f"    media_id={media_id}")
        if dry_run:
            continue
        derr = draft_delete(media_id=media_id)
        if derr:
            if derr.get("errcode") == 53407:
                print(
                    "    ⚠️ 该稿处于「定时发布」状态，API 无法删除。"
                    "请登录 mp.weixin.qq.com → 内容与互动 → 草稿箱 →"
                    "找到本篇 → 取消定时发表 → 再执行本脚本。",
                    file=sys.stderr,
                )
            else:
                print(f"    ❌ {derr}", file=sys.stderr)
            return 1

    if dry_run:
        print("（dry-run 未实际删除）")
    else:
        print(f"OK 已删除 {len(to_delete)} 篇")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="清理公众号多余/废弃草稿")
    parser.add_argument("--dry-run", action="store_true", help="只列出将删除的草稿")
    args = parser.parse_args()

    if not mp_configured():
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    return prune_obsolete_drafts(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
