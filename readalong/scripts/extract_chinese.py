#!/usr/bin/env python3
"""Extract Chinese chapter text from the collected HP epub."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EPUB = ROOT / "samples" / "book_zh.epub"

# Book 1 chapter 1 — 第一章　大难不死的男孩
CHAPTER_FILES: dict[int, str] = {
    1: "index_split_005.html",
}


def _clean_html(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _split_zh_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？…])", text)
    return [p.strip() for p in parts if p.strip()]


def extract_chapter(epub_path: Path, chapter: int) -> dict:
    rel = CHAPTER_FILES.get(chapter)
    if not rel:
        raise SystemExit(f"Chapter {chapter} not mapped in CHAPTER_FILES")

    with zipfile.ZipFile(epub_path) as zf:
        html = zf.read(rel).decode("utf-8", errors="replace")

    paragraphs: list[str] = []
    for raw in re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.S):
        if "height:1em" in raw:
            continue
        text = _clean_html(raw)
        if not text:
            continue
        if re.match(r"^第[一二三四五六七八九十百]+章", text) and len(text) < 40:
            continue
        paragraphs.append(text)

    sentences: list[str] = []
    for para in paragraphs:
        sentences.extend(_split_zh_sentences(para))

    return {
        "chapter": chapter,
        "title": "大难不死的男孩",
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "paragraphs": paragraphs,
        "sentences": sentences,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epub", type=Path, default=DEFAULT_EPUB)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    data = extract_chapter(args.epub, args.chapter)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Chapter {args.chapter} ZH: {data['paragraph_count']} paragraphs, "
        f"{data['sentence_count']} sentences → {args.output}"
    )


if __name__ == "__main__":
    main()
