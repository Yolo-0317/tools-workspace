#!/usr/bin/env python3
"""Extract chapter text from the sample EPUB."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EPUB = ROOT / "samples" / "book.epub"
CHAPTER_FILES = {
    1: "OEBPS/hp01_watermarkval001_en-ushtml",
}


def _clean_html_paragraph(raw: str) -> str:
    # Merge drop-cap spans: <span class="drop">M</span>r. -> Mr.
    raw = re.sub(
        r'<span[^>]*class="[^"]*drop[^"]*"[^>]*>([^<]*)</span>\s*',
        r"\1",
        raw,
        flags=re.I,
    )
    text = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _merge_flowing_paragraphs(raw_paragraphs: list[str]) -> list[str]:
    """Merge EPUB <p> fragments that break mid-sentence across lines."""
    merged: list[str] = []
    buf = ""
    for para in raw_paragraphs:
        piece = para.strip()
        if not piece:
            continue
        buf = f"{buf} {piece}".strip() if buf else piece
        if re.search(r'[.!?…][\'")\]]*\s*$', buf):
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)
    return merged


def _split_sentences(full_text: str) -> list[str]:
    """Best-effort sentence split for stats only; alignment uses merged_paragraphs."""
    text = re.sub(r"\s+", " ", full_text.strip())
    protected = {
        "Mr.": "§MR§",
        "Mrs.": "§MRS§",
        "Ms.": "§MS§",
        "Dr.": "§DR§",
    }
    for k, v in protected.items():
        text = text.replace(k, v)
    parts = re.split(r'(?<=[.!?…])\s+(?=[A-Z"\'])', text)
    out: list[str] = []
    rev = {v: k for k, v in protected.items()}
    for p in parts:
        p = p.strip()
        if not p:
            continue
        for v, k in rev.items():
            p = p.replace(v, k)
        out.append(p)
    return out


def extract_chapter(epub_path: Path, chapter: int) -> dict:
    rel = CHAPTER_FILES[chapter]
    with zipfile.ZipFile(epub_path) as zf:
        html = zf.read(rel).decode("utf-8", errors="replace")

    paragraphs: list[str] = []
    for raw in re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.S):
        text = _clean_html_paragraph(raw)
        if not text:
            continue
        if text.startswith("Chapter ") and "The Boy Who Lived" in text:
            continue
        paragraphs.append(text)

    merged = _merge_flowing_paragraphs(paragraphs)
    sentences: list[str] = []
    for block in merged:
        sentences.extend(_split_sentences(block))

    return {
        "chapter": chapter,
        "title": "The Boy Who Lived",
        "paragraph_count": len(paragraphs),
        "merged_paragraph_count": len(merged),
        "sentence_count": len(sentences),
        "paragraphs": paragraphs,
        "merged_paragraphs": merged,
        "sentences": sentences,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epub", type=Path, default=DEFAULT_EPUB)
    parser.add_argument("--chapter", type=int, default=1)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    data = extract_chapter(args.epub, args.chapter)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {args.output} — {data['paragraph_count']} paragraphs, "
        f"{data['sentence_count']} sentences"
    )


if __name__ == "__main__":
    main()
