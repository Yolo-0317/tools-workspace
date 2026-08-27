#!/usr/bin/env python3
"""DeepSeek 写标题+正文 → 落缓存 → 可选 repush（配图排版走现有流水线）。"""

from __future__ import annotations

import argparse
import re
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_codex_client import generation_scope
from scripts.tools.wechat_mp_deepseek_writer import (
    generate_deepseek_mp_piece,
    is_deepseek_writer_configured,
    record_deepseek_writer_event,
    subject_from_topic,
)
from scripts.tools.wechat_mp_seo import clip_digest
from scripts.tools.wechat_mp_tv_body_cache import load_tv_body_cache, save_tv_body_cache
from scripts.tools.wechat_mp_repush_tv_review_draft import _topic_from_cache


def _digest_from_body(body: str) -> str:
    plain = re.sub(r"\s+", " ", (body or "").replace("\n", " ")).strip()
    return clip_digest(plain[:120] if plain else "话题讨论")


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepSeek 写公众号标题+正文并落缓存")
    parser.add_argument("--subject", default="", help="写作主题（优先于 topic-key）")
    parser.add_argument(
        "--topic-key",
        default="",
        help="如 dianji-shangshu；从选题/缓存拼主题",
    )
    parser.add_argument("--extra", default="", help="可选一句补充要求")
    parser.add_argument(
        "--no-observer-polish",
        action="store_true",
        help="跳过观察者润色（默认 DeepSeek 写完后自动改口吻）",
    )
    parser.add_argument("--slot-key", default="tv_review")
    args = parser.parse_args()

    if not is_deepseek_writer_configured():
        print(
            "❌ DeepSeek 写稿不可用（WECHAT_MP_WRITER_BACKEND / DEEPSEEK_API_KEY）",
            file=sys.stderr,
        )
        return 1

    topic: dict = {}
    if args.topic_key.strip():
        cache = load_tv_body_cache(topic_key=args.topic_key.strip())
        if cache:
            topic = _topic_from_cache(cache)
        else:
            topic = {
                "cover_slug": args.topic_key.strip(),
                "topic_key": args.topic_key.strip(),
            }

    subject = args.subject.strip() or subject_from_topic(topic)
    if not subject:
        print("❌ 需要 --subject 或 --topic-key", file=sys.stderr)
        return 1

    with generation_scope("tv_review"):
        record_deepseek_writer_event("tv_review")
        piece = generate_deepseek_mp_piece(
            subject,
            extra=args.extra,
            topic_key=str(topic.get("cover_slug") or topic.get("topic_key") or args.topic_key),
        )
        if not args.no_observer_polish:
            from scripts.tools.wechat_mp_deepseek_polish import polish_deepseek_observer_llm
            from scripts.tools.wechat_mp_deepseek_writer import is_dianji_subject

            dianji = is_dianji_subject(
                subject,
                topic_key=str(topic.get("cover_slug") or topic.get("topic_key") or ""),
            )
            piece = polish_deepseek_observer_llm(
                piece["title"],
                piece["body"],
                dianji=dianji,
            )
        title = piece["title"]
        body = piece["body"]

        from scripts.tools.wechat_mp_deepseek_polish import (
            polish_deepseek_observer_voice,
            scan_deepseek_observer_issues,
        )

        polished = polish_deepseek_observer_voice(title, body)
        title = polished["title"]
        body = polished["body"]
        issues = scan_deepseek_observer_issues(body)
        if "我" in title:
            issues.append("标题含第一人称「我」")
        if issues:
            print("⚠ Agent 观察者复检（请人工或 Agent 改缓存后 repush）：", file=sys.stderr)
            for item in issues[:8]:
                print(f"  · {item}", file=sys.stderr)
        digest = clip_digest(_digest_from_body(body))

        if topic:
            save_tv_body_cache(
                topic,
                body_core=body,
                title=title,
                digest=digest,
            )
            print(f"OK 已写入缓存 topic_key={topic.get('cover_slug') or args.topic_key}")
        else:
            print("OK DeepSeek 成稿（未落缓存，未提供 topic）")

        print(f"标题: {title}")
        print(f"摘要: {digest}")
        print(f"正文 {len(body)} 字")
        print("---")
        print(body)

    if args.repush and args.topic_key.strip():
        from scripts.tools.wechat_mp_repush_tv_review_draft import main as repush_main

        sys.argv = [
            "wechat_mp_repush_tv_review_draft",
            "--title-en",
            args.topic_key.strip(),
            "--slot-key",
            args.slot_key.strip(),
        ]
        return repush_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
