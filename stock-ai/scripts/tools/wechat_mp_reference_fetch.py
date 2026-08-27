#!/usr/bin/env python3
"""参考文素材库：联网抓取公开报道开头片段，落盘供提炼（存片段+规律，不整篇转载）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_discussion_research import (
    _fetch_html,
    _parse_article_page,
    _strip_html,
)
from scripts.tools.wechat_mp_reference_corpus import CORPUS_ROOT

_ROOT = Path(__file__).resolve().parents[2]
_P_BLOCK_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.I | re.S)
_SKIP_P = re.compile(r"(来源|编辑|版权所有|点击查看|分享到|责任编辑|原标题|document\.|getElement)")


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    tail = path.split("/")[-1] or "page"
    tail = re.sub(r"[^\w\-]+", "-", tail)[:48].strip("-")
    return tail or "page"


def _extract_opening_paragraphs(html: str, *, max_paras: int = 5) -> list[str]:
    out: list[str] = []
    for pm in _P_BLOCK_RE.finditer(html):
        text = _strip_html(pm.group(1)).strip()
        if len(text) < 28:
            continue
        if _SKIP_P.search(text):
            continue
        if re.search(r"https?://", text):
            continue
        if re.search(r"[{};]|function\s*\(", text):
            continue
        if text in out:
            continue
        out.append(text)
        if len(out) >= max_paras:
            break
    return out


def fetch_reference_snippet(url: str, *, timeout: float = 16.0) -> dict[str, Any]:
    url = (url or "").strip()
    if not url.startswith("http"):
        raise ValueError(f"无效 URL: {url}")
    html = _fetch_html(url, timeout=timeout)
    hit = _parse_article_page(url, html)
    paragraphs = _extract_opening_paragraphs(html)
    title = (hit.title if hit else "") or ""
    opening_80 = paragraphs[0][:80] if paragraphs else (hit.snippet[:80] if hit else "")
    return {
        "url": url,
        "title": title,
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "opening_paragraphs": paragraphs,
        "opening_80": opening_80,
        "meta_snippet": (hit.snippet if hit else "")[:400],
    }


def archive_path(series: str, episode_slug: str, url: str) -> Path:
    return (
        CORPUS_ROOT
        / series
        / "archive"
        / episode_slug
        / f"{_slug_from_url(url)}.json"
    )


def save_archive(
    series: str,
    episode_slug: str,
    url: str,
    payload: dict[str, Any],
    *,
    tier: str = "",
    take: str = "",
) -> Path:
    path = archive_path(series, episode_slug, url)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    if tier:
        body["tier"] = tier
    if take:
        body["take"] = take
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def cmd_fetch(args: argparse.Namespace) -> int:
    try:
        payload = fetch_reference_snippet(args.url)
    except Exception as exc:
        print(f"❌ 抓取失败: {exc}", file=sys.stderr)
        return 1
    if args.save and args.series and args.slug:
        path = save_archive(
            args.series,
            args.slug,
            args.url,
            payload,
            tier=args.tier or "",
            take=args.take or "",
        )
        print(f"OK 已归档 {path}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_archive_episode(args: argparse.Namespace) -> int:
    from scripts.tools.wechat_mp_reference_corpus import _load_series

    data = _load_series(args.series)
    row = (data.get("episodes") or {}).get(args.slug)
    if not row:
        print(f"无 slug={args.slug}", file=sys.stderr)
        return 1
    links = list(row.get("links") or [])
    if args.tier:
        links = [x for x in links if x.get("tier") == args.tier]
    if not links:
        print("无链接可归档", file=sys.stderr)
        return 1
    ok = 0
    for item in links:
        url = str(item.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        try:
            payload = fetch_reference_snippet(url)
            path = save_archive(
                args.series,
                args.slug,
                url,
                payload,
                tier=str(item.get("tier") or ""),
                take=str(item.get("take") or ""),
            )
            print(f"OK {path.name} · {payload.get('opening_80') or ''}")
            ok += 1
        except Exception as exc:
            print(f"⚠ 跳过 {url}: {exc}", file=sys.stderr)
    print(f"完成 {ok}/{len(links)}")
    return 0 if ok else 1


def cmd_search(args: argparse.Namespace) -> int:
    from scripts.tools.wechat_mp_discussion_research import fetch_discussion_research

    topic = {
        "trend_title": args.query,
        "title_zh": "",
        "hook": "",
        "platform": "话题",
        "type": "discussion",
    }
    hits = fetch_discussion_research(topic, limit=args.limit)
    if not hits:
        print("无结果", file=sys.stderr)
        return 1
    for hit in hits:
        print(f"- {hit.title}")
        print(f"  {hit.url}")
        if hit.snippet:
            print(f"  {hit.snippet[:120]}…")
    print("\n加入 sources.json 后运行: archive-episode --tier B_voice")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="参考文爆款素材：联网抓开头片段")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="抓取单 URL 开头片段")
    p_fetch.add_argument("--url", required=True)
    p_fetch.add_argument("--series", default="dianji-zhongguo")
    p_fetch.add_argument("--slug", default="")
    p_fetch.add_argument("--tier", default="B_voice")
    p_fetch.add_argument("--take", default="")
    p_fetch.add_argument("--save", action="store_true", help="写入 archive/")
    p_fetch.set_defaults(func=cmd_fetch)

    p_arch = sub.add_parser("archive-episode", help="按 sources.json 批量归档")
    p_arch.add_argument("--series", default="dianji-zhongguo")
    p_arch.add_argument("--slug", required=True)
    p_arch.add_argument("--tier", default="", help="如 B_voice 只归档范本档")
    p_arch.set_defaults(func=cmd_archive_episode)

    p_search = sub.add_parser("search", help="同题公开报道检索（候选链接）")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=8)
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
