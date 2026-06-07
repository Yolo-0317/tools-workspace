#!/usr/bin/env python3
"""带货种草公众号草稿：Markdown 正文 → HTML 草稿 + 文末 CPS 返佣。

成稿模板：jianxuan-v1（见 data/wechat_mp_commerce_template.json、.cursor/skills/wechat-mp-commerce-drafts/template-jianxuan.md）
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    add_permanent_image,
    attach_cover_crop_fields,
    freepublish_submit,
    mp_account_profile,
    mp_configured,
    pick_thumb_from_material_library,
    text_to_html,
)
from scripts.tools.wechat_mp_commerce_slots import COMMERCE_SLOTS, upsert_commerce_draft
from scripts.tools.wechat_mp_content import _clip_wechat_title
from scripts.tools.wechat_format import normalize_wechat_spacing, strip_markdown_for_wechat
from scripts.tools.wechat_mp_monetization import (
    comment_settings,
    polish_for_traffic,
    split_disclaimer,
)
from scripts.tools.wechat_mp_product import attach_footer_product
from scripts.tools.wechat_mp_prose import demote_numbered_section_lines, humanize_mp_text
from scripts.tools.wechat_mp_public import sanitize_public_mp_text

TITLE_MAX = 32
DIGEST_MAX = 128
COMMERCE_TEMPLATE_VERSION = "jianxuan-v1"

COMMERCE_DISCLAIMER = (
    "本文为个人体验与信息整理，部分链接含推广合作（佣金）。"
    "请按需购买，理性消费。"
)
_COMMERCE_DISCLAIMER_PREFIX = "本文为个人体验与信息整理"

_DISCLOSURE_HINTS = ("推广", "佣金", "合作", "返佣", "赞助")
# 仅补摘要；正文不插模板句，文末 COMMERCE_DISCLAIMER 兜底
_DIGEST_DISCLOSURE_SUFFIX = "（文内有合作推广。）"
_DIGEST_DISCLOSURE_ONLY = "文内有合作推广，按需购买。"
_LEGACY_BODY_DISCLOSURE = "本文含推广链接，下单可能产生佣金"
_VERTICALS = tuple(
    k
    for k in (
        "tech",
        "home",
        "mother",
        "outdoor",
        "office",
        "beauty",
        "guide",
        "review",
        "trend",
    )
)

_COMMERCE_DROP_LINE_RE = re.compile(
    r"^(.*(?:全网最低|史上最强|100%有效|根治|必买|错过亏|躺赚).*)$",
    re.I,
)
_NUMBERED_ITEM_RE = re.compile(r"^\d+\.\s+")
_BULLET_ITEM_RE = re.compile(r"^[-*]\s+")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def commerce_humanize_enabled() -> bool:
    return _env("WECHAT_MP_COMMERCE_HUMANIZE", "0").lower() in ("1", "true", "yes", "on")


def commerce_masthead_enabled() -> bool:
    return _env("WECHAT_MP_COMMERCE_MASTHEAD", "1").lower() in ("1", "true", "yes", "on")


def commerce_thumb_name() -> str:
    return _env("WECHAT_MP_COMMERCE_THUMB", "封面-财经屏-双封面")


def commerce_auto_publish_enabled(*, cli_publish: bool | None = None) -> bool:
    if cli_publish is True:
        return True
    if cli_publish is False:
        return False
    return _env("WECHAT_MP_COMMERCE_AUTO_PUBLISH", "0").lower() in ("1", "true", "yes", "on")


def commerce_cover_path() -> Path | None:
    """草稿列表封面：默认简选头像，可 WECHAT_MP_COMMERCE_THUMB_PATH 覆盖。"""
    from scripts.tools.wechat_mp_masthead import ROOT as _ROOT

    explicit = _env("WECHAT_MP_COMMERCE_THUMB_PATH")
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None
    for path in (
        _ROOT / "assets" / "wechat_mp" / "commerce" / "avatar.png",
        Path.home() / "Pictures" / "简选小电头像.png",
        Path.home() / "picture" / "简选小电头像.png",
        Path.home() / "picture" / "avatar.png",
    ):
        if path.is_file():
            return path
    return None


def pick_commerce_thumb_media_id() -> tuple[str | None, dict[str, Any] | None]:
    """优先本地头像上传封面；否则回退素材库名称匹配。"""
    cover = commerce_cover_path()
    if cover is not None:
        media_id, err = add_permanent_image(cover)
        if media_id and not err:
            return media_id, None
        if err:
            return None, err
    return pick_thumb_from_material_library(
        name_sub=commerce_thumb_name(),
        use_global_preset=False,
    )


def _clip_digest(text: str, *, max_len: int = DIGEST_MAX) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _reflow_commerce_lists(text: str) -> str:
    """有序/无序列表拆成独立段，供 text_to_html 逐段排版。"""
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _NUMBERED_ITEM_RE.match(stripped) or _BULLET_ITEM_RE.match(stripped):
            if out and out[-1] != "":
                out.append("")
            if _BULLET_ITEM_RE.match(stripped):
                out.append("· " + _BULLET_ITEM_RE.sub("", stripped).strip())
            else:
                out.append(stripped)
            continue
        out.append(line)
    return "\n".join(out)


def _prepare_commerce_core(text: str) -> str:
    text = strip_markdown_for_wechat(text)
    text = _reflow_commerce_lists(text)
    return normalize_wechat_spacing(text)


def sanitize_commerce_mp_text(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if _COMMERCE_DROP_LINE_RE.match(line.strip()):
            continue
        lines.append(line)
    merged = "\n".join(lines)
    return sanitize_public_mp_text(merged)


def _ensure_disclosure(body: str, digest: str) -> tuple[str, str]:
    """缺披露词时只补摘要；正文不改，文末统一免责。"""
    combined = f"{digest}\n{body}"
    if any(h in combined for h in _DISCLOSURE_HINTS):
        return body, digest
    digest = (digest or "").strip()
    if digest:
        digest = _clip_digest(f"{digest.rstrip()}{_DIGEST_DISCLOSURE_SUFFIX}")
    else:
        digest = _clip_digest(_DIGEST_DISCLOSURE_ONLY)
    return body, digest


def build_commerce_article(
    *,
    title: str,
    digest: str,
    body_md: str,
    vertical: str = "home",
    slot: str = "guide",
    author: str | None = None,
) -> dict[str, Any]:
    """Markdown 正文 → 草稿 API 字段（对齐财经号 _article_shell：先拆免责再转 HTML）。"""
    vert = (vertical or "home").strip().lower()
    if vert not in _VERTICALS:
        vert = "home"

    slot_key = (slot or "guide").strip().lower()
    raw_title = _clip_wechat_title(title, max_len=TITLE_MAX)
    raw_digest = _clip_digest(digest)
    if commerce_seo_enabled():
        from scripts.tools.wechat_mp_seo import enrich_digest, enrich_title_for_search

        raw_title = enrich_title_for_search(
            raw_title,
            "commerce",
            edition=slot_key,
            max_len=TITLE_MAX,
            clip_fn=lambda t: _clip_wechat_title(t, max_len=TITLE_MAX),
        )
        raw_digest = enrich_digest(raw_digest, "commerce", edition=slot_key)
    body = (body_md or "").strip()
    body = demote_numbered_section_lines(body)
    if commerce_humanize_enabled():
        body = humanize_mp_text(body)
    body, raw_digest = _ensure_disclosure(body, raw_digest)
    body = sanitize_commerce_mp_text(body)
    body = polish_for_traffic(body, kind="commerce")
    commerce_tags: list[str] = []
    if commerce_seo_enabled():
        from scripts.tools.wechat_mp_seo import insert_hashtags_after_intro, recommended_hashtags

        commerce_tags = recommended_hashtags("commerce", edition=slot_key)
        body = insert_hashtags_after_intro(body, commerce_tags)
    full_body = f"{body.rstrip()}\n\n{COMMERCE_DISCLAIMER}"

    core, disc_tail = split_disclaimer(full_body)
    if not disc_tail and _COMMERCE_DISCLAIMER_PREFIX in full_body:
        core, _, disc_tail = full_body.partition(_COMMERCE_DISCLAIMER_PREFIX)
        disc_tail = _COMMERCE_DISCLAIMER_PREFIX + disc_tail

    from scripts.tools.wechat_mp_figures import inject_commerce_figures

    core = _prepare_commerce_core(core)
    core = inject_commerce_figures(core, vertical=vert)
    disc_plain = strip_markdown_for_wechat(disc_tail) if disc_tail else ""

    upload = mp_configured()
    html_core = text_to_html(core, upload_figures=upload, article_kind="commerce")
    if disc_plain:
        from scripts.tools.wechat_mp_rich_html import disclaimer_html

        html_disc = disclaimer_html(disc_plain.strip(), kind="commerce")
    else:
        html_disc = ""

    content = html_core
    if commerce_masthead_enabled():
        from scripts.tools.wechat_mp_masthead import masthead_html

        head = masthead_html("commerce", upload_images=upload)
        if head:
            content = f"{head}{content}"

    article: dict[str, Any] = {
        "title": raw_title,
        "author": (author or _env("WECHAT_MP_AUTHOR", "R2D2")),
        "digest": raw_digest,
        "content": content,
        "body_text": full_body,
    }
    article.update(comment_settings())
    article = attach_footer_product(article, kind=vert)
    if html_disc:
        article["content"] = f"{article.get('content') or ''}{html_disc}"
    if commerce_seo_enabled():
        from scripts.tools.wechat_mp_seo import attach_publish_hints

        article = attach_publish_hints(article, "commerce", edition=slot_key)
        if commerce_tags:
            article["recommended_hashtags"] = commerce_tags
    return article


def main() -> int:
    parser = argparse.ArgumentParser(description="带货种草公众号草稿（独立于五槽财经稿）")
    parser.add_argument("--title", required=True, help="标题（≤32 字）")
    parser.add_argument("--digest", default="", help="摘要（≤128 字，建议含推广披露）")
    parser.add_argument("--body-file", type=Path, help="Markdown 正文文件")
    parser.add_argument("--body", default="", help="正文（与 --body-file 二选一）")
    parser.add_argument(
        "--vertical",
        default="home",
        choices=_VERTICALS,
        help="垂直领域（默认 home 小家电；影响返佣 auto-pick 搜索词）",
    )
    parser.add_argument(
        "--slot",
        default="guide",
        choices=COMMERCE_SLOTS,
        help="草稿槽位 guide|review|trend",
    )
    parser.add_argument("--author", default=None)
    parser.add_argument("--dry-run", action="store_true", help="只打印预览，不写草稿箱")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="草稿后 freepublish 直接发表（或 WECHAT_MP_COMMERCE_AUTO_PUBLISH=1）",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="只推草稿箱，不发表（覆盖 WECHAT_MP_COMMERCE_AUTO_PUBLISH）",
    )
    args = parser.parse_args()

    if args.body_file:
        body_md = args.body_file.read_text(encoding="utf-8")
    else:
        body_md = args.body or ""
    if not body_md.strip():
        print("❌ 需要 --body-file 或 --body", file=sys.stderr)
        return 1

    if not args.dry_run and not mp_configured(profile="commerce"):
        print(
            "❌ 未配置 WECHAT_MP_COMMERCE_APPID/SECRET（或回退 WECHAT_MP_APPID/SECRET）",
            file=sys.stderr,
        )
        return 1

    ctx = nullcontext() if args.dry_run else mp_account_profile("commerce")
    with ctx:
        article = build_commerce_article(
            title=args.title,
            digest=args.digest,
            body_md=body_md,
            vertical=args.vertical,
            slot=args.slot,
            author=args.author,
        )

        print(f"标题: {article.get('title')}")
        print(f"摘要: {article.get('digest')}")
        print(f"垂直: {args.vertical}  槽位: {args.slot}")
        if commerce_seo_enabled():
            from scripts.tools.wechat_mp_seo import print_publish_hints

            print_publish_hints("commerce", article, edition=args.slot)
        if args.dry_run:
            preview = str(article.get("body_text") or "")[:1200]
            print("--- 正文预览 ---")
            print(preview)
            html = str(article.get("content") or "")
            if "mp-common-cpsad" in html:
                print("--- CPS: 已注入 HTML ---")
                assert "部分链接含推广合作" not in html.split("mp-common-cpsad")[1].split("<p")[0][:80]
            return 0

        thumb_id, terr = pick_commerce_thumb_media_id()
        if terr or not thumb_id:
            print(
                f"❌ 封面失败（本地 avatar 或素材库 {commerce_thumb_name()}）: {terr}",
                file=sys.stderr,
            )
            return 1
        article = attach_cover_crop_fields(article, thumb_media_id=thumb_id)

        media_id, action, err = upsert_commerce_draft(
            args.slot,
            article,
            thumb_media_id=thumb_id,
        )
        if err:
            print(f"❌ 草稿失败: {err}", file=sys.stderr)
            return 1
        print(f"✅ 带货草稿 {action}: slot={args.slot} media_id={media_id}")

        cli_publish = False if args.no_publish else (True if args.publish else None)
        if commerce_auto_publish_enabled(cli_publish=cli_publish):
            pub_id, pub_err = freepublish_submit(media_id=media_id or "")
            if pub_err:
                print(f"⚠️ 发表失败: {pub_err}", file=sys.stderr)
                return 1
            print(f"✅ 已提交发表 publish_id={pub_id}")
            print(
                "提示: API 发表无法勾选原创/#话题；若需原创请改 --no-publish 后管理员后台发布",
                file=sys.stderr,
            )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
