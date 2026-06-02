#!/usr/bin/env python3
"""每日公众号草稿：固定四槽位（优先更新旧稿，并清理重复）。"""

from __future__ import annotations

import argparse
import os
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    get_material_image_meta,
    mp_configured,
    pick_thumb_for_draft_kind,
)
from scripts.tools.wechat_mp_content import DRAFT_KINDS, build_article
from scripts.tools.wechat_mp_draft_slots import upsert_draft_article


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/更新公众号图文草稿（四槽位）")
    parser.add_argument(
        "--kind",
        choices=[*DRAFT_KINDS, "all"],
        default="all",
        help="market / top5 / dragons / workspace；all=四篇",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印标题与正文预览")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="草稿后 freepublish（需 WECHAT_MP_AUTO_PUBLISH=1 或显式传参）",
    )
    parser.add_argument("--list-materials", action="store_true", help="列出素材库图片后退出")
    parser.add_argument(
        "--prune-only",
        action="store_true",
        help="只清理多余草稿，不写入内容",
    )
    parser.add_argument(
        "--force-new",
        action="store_true",
        help="忽略槽位，强制新建（仍会清理多余旧稿）",
    )
    args = parser.parse_args()

    if args.list_materials:
        from scripts.tools.wechat_mp_list_materials import main as list_main

        _argv = sys.argv
        sys.argv = [_argv[0]]
        try:
            return list_main()
        finally:
            sys.argv = _argv

    kinds = list(DRAFT_KINDS) if args.kind == "all" else [args.kind]

    if args.prune_only:
        from scripts.tools.wechat_mp_prune_drafts import prune_obsolete_drafts

        return prune_obsolete_drafts(dry_run=args.dry_run)

    if not mp_configured() and not args.dry_run:
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    if args.dry_run:
        ok = True
        for kind in kinds:
            try:
                article = build_article(kind)
            except Exception as exc:
                print(f"❌ [{kind}] {exc}", file=sys.stderr)
                ok = False
                continue
            print(f"=== {kind} ===")
            print(f"标题: {article['title']}")
            print(f"摘要: {article['digest']}")
            print(article["content"][:1200])
            print()
        return 0 if ok else 1

    if args.force_new:
        from scripts.tools.wechat_mp_draft_slots import SLOTS_PATH

        if SLOTS_PATH.is_file():
            SLOTS_PATH.unlink()
            print("已清空槽位缓存，将全部新建", file=sys.stderr)

    ok_count = 0
    for kind in kinds:
        try:
            article = build_article(kind)
        except Exception as exc:
            print(f"❌ [{kind}] 跳过: {exc}", file=sys.stderr)
            continue

        thumb, terr = pick_thumb_for_draft_kind(kind)
        if terr:
            print(f"❌ [{kind}] 封面: {terr.get('errmsg')}", file=sys.stderr)
            continue
        meta, _ = get_material_image_meta(thumb or "")
        if meta:
            print(
                f"封面 [{kind}]: {meta.get('name')} {meta.get('width')}x{meta.get('height')}",
                file=sys.stderr,
            )

        media_id, action, err = upsert_draft_article(
            kind, article, thumb_media_id=thumb or ""
        )
        if err:
            print(f"❌ [{kind}] 失败: {err}", file=sys.stderr)
            continue
        ok_count += 1
        verb = "已更新" if action == "updated" else "已新建"
        cover_hint = meta.get("name") if meta else ""
        print(f"OK [{kind}] {verb} media_id={media_id} · {article['title']} · 封面={cover_hint}")

        if args.publish or os.getenv("WECHAT_MP_AUTO_PUBLISH", "").lower() in {
            "1",
            "true",
            "yes",
        }:
            from scripts.tools.wechat_mp_client import freepublish_submit

            pub_id, pub_err = freepublish_submit(media_id=media_id or "")
            if pub_err:
                print(f"⚠️ [{kind}] 发布失败: {pub_err}", file=sys.stderr)
            else:
                print(f"OK [{kind}] publish_id={pub_id}")

    if ok_count == 0:
        return 1

    from scripts.tools.wechat_mp_prune_drafts import prune_obsolete_drafts

    prune_obsolete_drafts(dry_run=False)
    print(
        "提示: 草稿箱保持 market / top5 / dragons / workspace 各 1 篇，请在 mp.weixin.qq.com 审阅"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
