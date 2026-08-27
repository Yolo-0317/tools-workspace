#!/usr/bin/env python3
"""只重跑 normalize + 插图/评分注入后推草稿，不调用 DeepSeek 重写正文。"""

from __future__ import annotations

import argparse
import os
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_content import _article_shell
from scripts.tools.wechat_mp_draft_slots import upsert_draft_article
from scripts.tools.wechat_mp_seo import attach_publish_hints
from scripts.tools.wechat_mp_tv_body_cache import load_tv_body_cache
from scripts.tools.wechat_mp_tv_cover import pick_tv_draft_thumb
from scripts.tools.wechat_mp_tv_figures import (
    ensure_tv_stills,
    inject_tv_review_figures,
    normalize_tv_review_body,
)
from scripts.tools.wechat_mp_discussion_polish import finalize_discussion_body
from scripts.tools.wechat_mp_tv_topics import CURATED_HOT


def _topic_from_cache(cache: dict) -> dict:
    if str(cache.get("content_mode") or "").lower() == "discussion":
        slug = str(cache.get("cover_slug") or cache.get("topic_key") or "").strip()
        return {
            "content_mode": "discussion",
            "cover_slug": slug,
            "title_zh": str(cache.get("title_zh") or "").strip(),
            "title_en": "",
            "trend_title": str(cache.get("trend_title") or cache.get("title") or "").strip(),
            "platform": "话题",
            "type": "discussion",
            "from_trend": True,
            "research_urls": cache.get("research_urls") or [],
        }
    key = str(cache.get("topic_key") or cache.get("title_en") or "")
    for row in CURATED_HOT:
        if str(row.get("title_en") or "") == key:
            topic = dict(row)
            override = str(cache.get("title_override") or "").strip()
            if override:
                topic["title_override"] = override
            return topic
    from scripts.tools.wechat_mp_tv_topics import load_tv_trial_config

    for row in load_tv_trial_config().get("queue") or []:
        if isinstance(row, dict) and str(row.get("title_en") or "") == key:
            return dict(row)
    try:
        from scripts.tools.wechat_mp_tv_trend_topics import build_known_tv_topic

        known = build_known_tv_topic(key) or build_known_tv_topic(str(cache.get("title_en") or ""))
        if known:
            return known
    except Exception:
        pass
    raise RuntimeError(f"缓存 topic_key={key!r} 在 CURATED_HOT / trial queue 中未找到")


def main() -> int:
    parser = argparse.ArgumentParser(description="影视稿：从本地 body 缓存重推草稿（不重写正文）")
    parser.add_argument(
        "--title-en",
        default="Euphoria",
        help="与缓存 topic_key 一致，默认 Euphoria",
    )
    parser.add_argument(
        "--slot-key",
        default="tv_review",
        help="草稿槽位，话题定时稿用 hotspot_evening 等",
    )
    args = parser.parse_args()

    cache = load_tv_body_cache(topic_key=args.title_en)
    if not cache:
        print(
            "❌ 无本地正文缓存 data/wechat_mp_tv_body_cache.json；"
            "请先运行 wechat_mp_draft --kind tv_review 生成并缓存。",
            file=sys.stderr,
        )
        return 1

    topic = _topic_from_cache(cache)
    is_discussion = str(topic.get("content_mode") or "").lower() == "discussion"
    if is_discussion:
        from scripts.tools.wechat_mp_discussion_figures import inject_discussion_figures

        body_core = finalize_discussion_body(str(cache.get("body_core") or ""))
        from scripts.tools.wechat_mp_report_voice import scan_report_voice

        voice_hits = scan_report_voice(body_core)
        if voice_hits:
            print(f"❌ 正文含 {len(voice_hits)} 处分析报告腔：", file=sys.stderr)
            for label, pattern, snippet in voice_hits[:8]:
                print(f"  · [{label}] …{snippet}", file=sys.stderr)
            return 1
        body = inject_discussion_figures(body_core, topic)
        fig_count = body.count("[[fig:")
        if fig_count < 1 and os.getenv(
            "WECHAT_MP_DISCUSSION_REQUIRE_FIGURES", "1"
        ).strip().lower() not in {"0", "false", "no", "off"}:
            print(
                f"❌ 话题讨论稿正文配图不足 1 张可用事件图（当前 {fig_count}）；"
                "补 research_urls 或 WECHAT_MP_DISCUSSION_FIGURES_FORCE=1 重下",
                file=sys.stderr,
            )
            return 1
        body = body.rstrip()
    else:
        ensure_tv_stills(topic)
        body_core = str(cache.get("body_core") or "")
        body = inject_tv_review_figures(normalize_tv_review_body(body_core), topic)
    title = str(cache.get("title") or "")
    digest = str(cache.get("digest") or "")
    article = attach_publish_hints(
        _article_shell(
            title=title,
            digest=digest,
            body_text=body,
            kind="tv_review",
            engagement_kind="discussion" if is_discussion else None,
        ),
        "tv_review",
    )
    _, thumb, terr = pick_tv_draft_thumb(topic, force_reupload=True)
    if terr:
        print(f"❌ 封面: {terr.get('errmsg')}", file=sys.stderr)
        return 1
    media_id, action, err = upsert_draft_article(
        "tv_review",
        article,
        thumb_media_id=thumb or "",
        slot_key=args.slot_key.strip(),
    )
    if err:
        print(f"❌ 失败: {err}", file=sys.stderr)
        return 1
    print(f"OK {action} media_id={media_id} · 已从缓存重推（未调用 DeepSeek）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
