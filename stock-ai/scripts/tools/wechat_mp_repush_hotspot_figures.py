#!/usr/bin/env python3
"""热点深评：只换配图/封面后重推草稿，不调用 Composer 重写正文。"""

from __future__ import annotations

import argparse
import os
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import fetch_draft_news_item, mp_configured
from scripts.tools.wechat_mp_content import _article_shell, disclaimer_for_kind
from scripts.tools.wechat_mp_discussion_figures import (
    discussion_body_figure_target,
    ensure_discussion_cover,
    ensure_discussion_figures,
    inject_discussion_figures,
    strip_discussion_figures,
)
from scripts.tools.wechat_mp_discussion_polish import finalize_discussion_body
from scripts.tools.wechat_mp_draft_slots import get_slot_media_id, upsert_draft_article
from scripts.tools.wechat_mp_eval import strip_html
from scripts.tools.wechat_mp_hotspot_body_cache import (
    load_hotspot_body_cache,
    topic_from_cache,
)
from scripts.tools.wechat_mp_monetization import split_disclaimer
from scripts.tools.wechat_mp_public import strip_information_notices
from scripts.tools.wechat_mp_seo import attach_publish_hints
from scripts.tools.wechat_mp_tv_cover import pick_discussion_draft_thumb


def _topic_from_env() -> dict:
    hint = os.getenv("WECHAT_MP_HOTSPOT_TOPIC", "").strip()
    if not hint:
        raise RuntimeError("请设置 WECHAT_MP_HOTSPOT_TOPIC 或提供 --topic")
    slug = __import__("re").sub(r"[^\w\-]+", "-", hint[:28]).strip("-").lower() or "hotspot"
    return {
        "title_zh": hint,
        "trend_title": hint,
        "cover_slug": slug,
        "from_trend": True,
        "research_urls": [],
    }


def _body_from_draft_html(html: str) -> str:
    plain = strip_html(html or "")
    core, _disc = split_disclaimer(plain)
    core = strip_information_notices(core)
    core = finalize_discussion_body(core)
    from scripts.tools.wechat_mp_discussion_figures import strip_discussion_figures

    return strip_discussion_figures(core)


def main() -> int:
    parser = argparse.ArgumentParser(description="热点深评：从缓存或草稿重推配图（不重写正文）")
    parser.add_argument(
        "--slot-key",
        default="hotspot_afternoon",
        help="草稿槽位，默认 hotspot_afternoon",
    )
    parser.add_argument(
        "--topic",
        default="",
        help="话题标题（与 WECHAT_MP_HOTSPOT_TOPIC 二选一）",
    )
    parser.add_argument(
        "--force-figures",
        action="store_true",
        help="强制重新下载配图（等同 WECHAT_MP_DISCUSSION_FIGURES_FORCE=1）",
    )
    args = parser.parse_args()

    if not mp_configured():
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    if args.force_figures:
        os.environ["WECHAT_MP_DISCUSSION_FIGURES_FORCE"] = "1"

    topic_hint = (args.topic or os.getenv("WECHAT_MP_HOTSPOT_TOPIC") or "").strip()
    cache = load_hotspot_body_cache(topic_key=topic_hint or None, slot_key=args.slot_key)
    topic = topic_from_cache(cache) if cache else (_topic_from_env() if topic_hint else None)

    if cache:
        body_core = finalize_discussion_body(str(cache.get("body_core") or ""))
        title = str(cache.get("title") or "")
        digest = str(cache.get("digest") or "")
        topic = topic_from_cache(cache)
        print(f"· 正文来源: 本地缓存 ({cache.get('topic_key') or topic.get('cover_slug')})")
    else:
        media_id = get_slot_media_id(args.slot_key)
        if not media_id:
            print(f"❌ 槽位 {args.slot_key} 无 media_id，且无本地正文缓存", file=sys.stderr)
            return 1
        news, err = fetch_draft_news_item(media_id=media_id)
        if err:
            print(f"❌ 拉取草稿失败: {err.get('errmsg')}", file=sys.stderr)
            return 1
        title = str(news.get("title") or "")
        digest = str(news.get("digest") or "")
        body_core = _body_from_draft_html(str(news.get("content") or ""))
        if not topic:
            topic = {
                "title_zh": title,
                "trend_title": title,
                "cover_slug": __import__("re")
                .sub(r"[^\w\-]+", "-", title[:28])
                .strip("-")
                .lower()
                or "hotspot",
                "from_trend": True,
                "research_urls": [],
            }
        print(f"· 正文来源: 微信草稿 media_id={media_id[:12]}…")

    if not body_core.strip():
        print("❌ 正文为空", file=sys.stderr)
        return 1

    # 先一次性拉取/整理 still，再插正文、做封面，避免 FORCE 二次重扫删乱文件
    ensure_discussion_figures(topic, max_images=3)
    os.environ.pop("WECHAT_MP_DISCUSSION_FIGURES_FORCE", None)
    ensure_discussion_cover(topic)
    body = inject_discussion_figures(strip_discussion_figures(body_core), topic)
    fig_count = body.count("[[fig:")
    figure_target = discussion_body_figure_target()
    if fig_count < figure_target and os.getenv(
        "WECHAT_MP_DISCUSSION_REQUIRE_FIGURES", "1"
    ).strip().lower() not in {"0", "false", "no", "off"}:
        print(
            f"❌ 配图不足 {figure_target} 张（当前 {fig_count}）；可设 WECHAT_MP_DISCUSSION_FIGURES_FORCE=1",
            file=sys.stderr,
        )
        return 1

    body = f"{body}\n\n{disclaimer_for_kind('hotspot')}"
    article = attach_publish_hints(
        _article_shell(
            title=title,
            digest=digest,
            body_text=body,
            kind="hotspot",
            engagement_kind="discussion",
        ),
        "hotspot",
    )
    thumb, terr = pick_discussion_draft_thumb(topic, force_reupload=True)
    if terr:
        print(f"❌ 封面: {terr.get('errmsg')}", file=sys.stderr)
        return 1
    media_id, action, err = upsert_draft_article(
        "hotspot",
        article,
        thumb_media_id=thumb or "",
        slot_key=args.slot_key.strip(),
    )
    if err:
        print(f"❌ 失败: {err}", file=sys.stderr)
        return 1
    print(f"OK {action} media_id={media_id} · 配图 {fig_count} 张 · 未调用 Composer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
