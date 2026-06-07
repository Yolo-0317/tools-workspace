#!/usr/bin/env python3
"""每日公众号草稿：固定五槽位（优先更新旧稿，并清理重复）。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    get_material_image_meta,
    mp_configured,
    pick_thumb_for_draft_kind,
)
from scripts.tools.wechat_mp_content import DRAFT_KINDS, build_article
from scripts.tools.wechat_mp_draft_slots import upsert_draft_article


def _resolve_kinds(raw: str) -> list[str]:
    from scripts.tools.wechat_mp_content import DAILY_DRAFT_KINDS

    text = (raw or "all").strip().lower()
    if text == "all":
        return list(DAILY_DRAFT_KINDS)
    kinds = [k.strip() for k in text.split(",") if k.strip()]
    bad = [k for k in kinds if k not in DRAFT_KINDS]
    if bad:
        raise ValueError(f"未知 kind: {', '.join(bad)}；可选: {', '.join(DRAFT_KINDS)}, all")
    return kinds


def _build_for_kind(
    kind: str,
    *,
    edition: str | None,
    market_title: str | None,
    variant: str | None,
) -> dict[str, str]:
    if kind == "news" and market_title:
        return build_article(kind, peer_market_title=market_title)
    if kind in {"market", "sector"}:
        return build_article(kind, edition=edition)
    if kind == "temp":
        return build_article(kind, variant=variant)
    if kind == "workspace":
        return build_article(kind, variant=variant)
    return build_article(kind)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/更新公众号图文草稿（五槽日更 + temp 临时槽）")
    parser.add_argument(
        "--kind",
        default="all",
        help="单篇或逗号组合，如 market,temp；all=日更五篇（不含 temp）",
    )
    parser.add_argument(
        "--variant",
        default=None,
        metavar="NAME",
        help="稿变体：temp 默认 lark_cli；workspace 可选 english_buddy（见 wechat_mp_temp_article.list_temp_variants）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印标题与正文预览")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="草稿后 freepublish（需 WECHAT_MP_AUTO_PUBLISH=1 或显式传参）",
    )
    parser.add_argument(
        "--edition",
        choices=("pre", "midday", "close"),
        default=None,
        help="A股评论时段（仅 market）：pre 盘前 / midday 午间 / close 盘后；"
        "午间/盘后配合 dragons 时自动选 intraday/eod 数据槽",
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
    parser.add_argument(
        "--preview-html",
        type=Path,
        default=None,
        metavar="PATH",
        help="仅 market：写出本地手机预览 HTML（含插图 file://）",
    )
    args = parser.parse_args()

    try:
        kinds = _resolve_kinds(args.kind)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.list_materials:
        from scripts.tools.wechat_mp_list_materials import main as list_main

        _argv = sys.argv
        sys.argv = [_argv[0]]
        try:
            return list_main()
        finally:
            sys.argv = _argv

    if args.preview_html:
        if "market" not in kinds or len(kinds) != 1:
            print("❌ --preview-html 仅用于 --kind market", file=sys.stderr)
            return 1
        from scripts.tools.wechat_mp_content import build_market_article
        from scripts.tools.wechat_mp_figures import write_market_preview_html

        article = build_market_article(edition=args.edition)
        out = write_market_preview_html(article, out_path=args.preview_html)
        print(f"✅ 预览 HTML: {out}")
        print(f"标题: {article['title']}")
        print(f"摘要: {article['digest']}")
        return 0

    if args.prune_only:
        from scripts.tools.wechat_mp_prune_drafts import prune_obsolete_drafts

        return prune_obsolete_drafts(dry_run=args.dry_run)

    if not mp_configured() and not args.dry_run:
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    if args.dry_run:
        ok = True
        market_title: str | None = None
        for kind in kinds:
            try:
                edition = args.edition if kind == "market" else None
                article = _build_for_kind(
                    kind,
                    edition=edition,
                    market_title=market_title,
                    variant=args.variant,
                )
            except Exception as exc:
                print(f"❌ [{kind}] {exc}", file=sys.stderr)
                ok = False
                continue
            if kind == "market":
                market_title = article.get("title") or None
            print(f"=== {kind} ===")
            if kind == "temp" and args.variant:
                print(f"variant: {args.variant}")
            if kind == "market" and args.edition:
                print(f"edition: {args.edition}")
            print(f"标题: {article['title']}")
            print(f"摘要: {article['digest']}")
            from scripts.tools.wechat_mp_seo import print_publish_hints

            print_publish_hints(
                kind,
                article,
                edition=args.edition if kind == "market" else None,
            )
            from scripts.tools.wechat_mp_traffic_checklist import print_traffic_checklist

            print_traffic_checklist(
                kind,
                article,
                edition=args.edition if kind == "market" else None,
            )
            from scripts.tools.wechat_mp_publish_checklist import print_manual_publish_checklist

            print_manual_publish_checklist()
            pi = article.get("product_info") or {}
            fk = (pi.get("footer_product_info") or {}).get("product_key")
            if fk:
                print(f"文末商品: product_key={fk[:24]}…")
            print(article["content"][:1200])
            print()
        return 0 if ok else 1

    if args.force_new:
        from scripts.tools.wechat_mp_draft_slots import SLOTS_PATH

        if SLOTS_PATH.is_file():
            SLOTS_PATH.unlink()
            print("已清空槽位缓存，将全部新建", file=sys.stderr)

    if "dragons" in kinds:
        os.environ.setdefault("WECHAT_MP_DRAGON_SLOT", "eod")

    ok_count = 0
    market_title: str | None = None
    for kind in kinds:
        try:
            edition = args.edition if kind == "market" else None
            article = _build_for_kind(
                kind,
                edition=edition,
                market_title=market_title,
                variant=args.variant,
            )
        except Exception as exc:
            print(f"❌ [{kind}] 跳过: {exc}", file=sys.stderr)
            continue

        if kind == "market":
            market_title = article.get("title") or None

        from scripts.tools.wechat_mp_public import check_public_compliance

        compliance = check_public_compliance(
            article.get("body_text") or "",
            title=str(article.get("title") or ""),
        )
        if compliance:
            print(
                f"❌ [{kind}] 合规检查未通过: {'、'.join(compliance)}",
                file=sys.stderr,
            )
            strict = os.getenv("WECHAT_MP_STRICT_COMPLIANCE", "1").strip().lower()
            if strict not in ("0", "false", "no", "off"):
                continue

        thumb, terr = pick_thumb_for_draft_kind(kind)
        if kind == "workspace" and (args.variant or "").strip().lower() == "english_buddy":
            from scripts.tools.wechat_mp_english_buddy_article import (
                pick_english_buddy_workspace_thumb,
            )

            thumb, terr = pick_english_buddy_workspace_thumb()
            if not thumb:
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
        from scripts.tools.wechat_mp_seo import format_hashtag_line

        tags = article.get("recommended_hashtags") or []
        if tags:
            print(f"  {format_hashtag_line(list(tags))}")

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
        "提示: 草稿箱保持 market/news/top5/dragons/workspace/temp 各 1 篇，请在 mp.weixin.qq.com 审阅"
    )
    print(
        "提示: 推稿前已做合规扫描；可用 wechat_mp_eval --kind all --traffic 查看评分与阅读量清单",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
