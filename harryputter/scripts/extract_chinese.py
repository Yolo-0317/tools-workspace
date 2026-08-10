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
DEFAULT_EPUB = ROOT / "samples" / "epub" / "zh" / "collection.epub"

from chapters import get_chapter, zh_epub_path  # noqa: E402


def _clean_html(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _open_quotes(text: str) -> int:
    """Count unclosed Chinese/ASCII quote pairs in *text*."""
    pairs = (("\u201c", "\u201d"), ("\u300c", "\u300d"), ('"', '"'), ("'", "'"))
    n = 0
    for left, right in pairs:
        n += text.count(left) - text.count(right)
    return max(0, n)


def _split_zh_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？…])", text)
    raw = [p.strip() for p in parts if p.strip()]
    if not raw:
        return []
    merged: list[str] = [raw[0]]
    for p in raw[1:]:
        prev = merged[-1]
        # Split mid-dialogue: next chunk closes quotes or continues the utterance.
        if _open_quotes(prev) > 0 or re.match(r"^[\u201d\u300d\"'…，,、：:；;]", p):
            merged[-1] = prev + p
        else:
            merged.append(p)
    return merged


def _extract_heading_zh(html: str, chapter: int, title_zh: str) -> str:
    for raw in re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.S):
        if "height:1em" in raw:
            continue
        text = _clean_html(raw)
        if text and re.match(r"^第[一二三四五六七八九十百零\d]+章", text) and len(text) < 48:
            return text.replace("\u3000", " · ")
    return f"第{chapter}章 · {title_zh}"


def extract_chapter(epub_path: Path, book_id: str, chapter: int) -> dict:
    meta = get_chapter(book_id, chapter)
    rel = meta["zh_file"]

    with zipfile.ZipFile(epub_path) as zf:
        html = zf.read(rel).decode("utf-8", errors="replace")

    heading_zh = _extract_heading_zh(html, chapter, meta["title_zh"])

    paragraphs: list[str] = []
    for raw in re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.S):
        if "height:1em" in raw:
            continue
        text = _clean_html(raw)
        if not text:
            continue
        if re.match(r"^第[一二三四五六七八九十百零\d]+章", text) and len(text) < 48:
            continue
        paragraphs.append(text)

    body_sentences: list[str] = []
    for para in paragraphs:
        body_sentences.extend(_split_zh_sentences(para))

    sentences = [heading_zh, *body_sentences]
    kinds = ["heading", *(["body"] * len(body_sentences))]

    return {
        "chapter": chapter,
        "title": meta["title_zh"],
        "heading_zh": heading_zh,
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "body_sentence_count": len(body_sentences),
        "paragraphs": paragraphs,
        "sentences": sentences,
        "kinds": kinds,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--epub", type=Path, default=None)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    epub = args.epub or zh_epub_path(args.book)
    data = extract_chapter(epub, args.book, args.chapter)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Chapter {args.chapter} ZH: {data['paragraph_count']} paragraphs, "
        f"{data['sentence_count']} sentences → {args.output}"
    )


if __name__ == "__main__":
    main()
