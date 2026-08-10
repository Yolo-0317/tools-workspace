#!/usr/bin/env python3
"""Extract one EPUB chapter as a list of sentences for forced alignment."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EPUB = ROOT / "samples" / "epub" / "en" / "hp01.epub"

from chapters import en_epub_path, get_chapter  # noqa: E402

_PROTECTED = {
    "Mr.": "§MR§",
    "Mrs.": "§MRS§",
    "Ms.": "§MS§",
    "Dr.": "§DR§",
    "St.": "§ST§",
    "No.": "§NO§",
}


def _clean_html_paragraph(raw: str) -> str:
    raw = re.sub(
        r'<span[^>]*class="[^"]*drop[^"]*"[^>]*>([^<]*)</span>\s*',
        r"\1",
        raw,
        flags=re.I,
    )
    text = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _merge_flowing_paragraphs(raw_paragraphs: list[str]) -> list[str]:
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


def _ascii_quotes(text: str) -> str:
    return (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u2032", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _split_sentences(block: str) -> list[str]:
    text = re.sub(r"\s+", " ", _ascii_quotes(block.strip()))
    for k, v in _PROTECTED.items():
        text = text.replace(k, v)
    # Dialogue / ellipsis kept inside sentences.
    parts = re.split(r'(?<=[.!?…])\s+(?=[A-Z"\'(])', text)
    rev = {v: k for k, v in _PROTECTED.items()}

    def _restore(p: str) -> str:
        for v, k in rev.items():
            p = p.replace(v, k)
        return p.strip()

    def _refine(chunk: str) -> list[str]:
        chunk = _restore(chunk)
        if not chunk:
            return []
        extra: list[str] = []
        # "Foo!" "Bar …" — back-to-back dialogue.
        for pat in (
            r'(?<=[!?…][\'"])\s+(?=")',
            r'(?<=[.!?…][\'"])\s+(?=(?:Uncle|Aunt|Harry|Dudley|Mrs\.|Mr\.|He |She |The |Hagrid)\b)',
            r';\s+(?=(?:he|she|they|it)\b)',
            r'(?<=[.!?…][\'"])\s+(?=Got\s)',
            r'(?<=[.!?…])\s+(?=Got\s)',
            r'(?<=[.!?…][\'"])\s+(?=From\s)',
            r'(?<=[.!?…])\s+(?=From\s)',
        ):
            bits = re.split(pat, chunk)
            if len(bits) > 1:
                extra = [_restore(b) for b in bits if b.strip()]
                break
        return extra or [chunk]

    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.extend(_refine(p))
    return out


def _chapter_heading_en(html: str, chapter: int, title_en: str) -> str:
    """EPUB h2/h4 chapter banner (matches Stephen Fry's spoken intro)."""
    heads: list[str] = []
    for raw in re.findall(r"<h[1-5][^>]*>(.*?)</h[1-5]>", html, flags=re.S | re.I):
        text = _clean_html_paragraph(raw)
        if text:
            heads.append(text)
    if len(heads) >= 2 and heads[1]:
        title_part = heads[1].title() if heads[1].isupper() else heads[1]
        return f"Chapter {chapter} · {title_part}"
    return f"Chapter {chapter} · {title_en}"


def extract_chapter(epub_path: Path, book_id: str, chapter: int) -> dict:
    meta = get_chapter(book_id, chapter)
    rel, title = meta["en_file"], meta["title_en"]
    with zipfile.ZipFile(epub_path) as zf:
        html = zf.read(rel).decode("utf-8", errors="replace")

    heading = _chapter_heading_en(html, chapter, title)

    paragraphs: list[str] = []
    for raw in re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.S):
        text = _clean_html_paragraph(raw)
        if not text or ("The Boy Who Lived" in text and text.startswith("Chapter")):
            continue
        paragraphs.append(text)

    merged = _merge_flowing_paragraphs(paragraphs)
    body_sentences: list[str] = []
    sentence_paragraphs: list[int] = []
    for pi, block in enumerate(merged):
        sents = _split_sentences(block)
        body_sentences.extend(sents)
        sentence_paragraphs.extend([pi] * len(sents))

    sentences = [heading, *body_sentences]
    kinds = ["heading", *(["body"] * len(body_sentences))]

    return {
        "chapter": chapter,
        "title": title,
        "heading_en": heading,
        "paragraph_count": len(paragraphs),
        "merged_paragraph_count": len(merged),
        "sentence_count": len(sentences),
        "body_sentence_count": len(body_sentences),
        "merged_paragraphs": merged,
        "sentences": sentences,
        "kinds": kinds,
        "sentence_paragraphs": [-1, *sentence_paragraphs],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--epub", type=Path, default=None)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    epub = args.epub or en_epub_path(args.book)
    data = extract_chapter(epub, args.book, args.chapter)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Chapter {args.chapter}: {data['sentence_count']} sentences → {args.output}")


if __name__ == "__main__":
    main()
