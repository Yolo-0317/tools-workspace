#!/usr/bin/env python3
"""Verify EPUB sentence extraction vs raw chapter HTML (harryputter QA)."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from chapters import en_epub_path, get_chapter, manifest_path  # noqa: E402
from extract_sentences import extract_chapter  # noqa: E402


def _plain_body_words(epub_path: Path, rel: str) -> tuple[int, int]:
    with zipfile.ZipFile(epub_path) as zf:
        html = zf.read(rel).decode("utf-8", errors="replace")
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    if not body:
        return 0, 0
    text = re.sub(r"<[^>]+>", " ", body.group(1))
    text = unescape(text).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return len(text), len(text.split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--chapter", type=int, action="append", required=True)
    parser.add_argument("--epub", type=Path, default=None)
    parser.add_argument("--sentences", type=Path, help="output/chNN_sentences.json to compare")
    args = parser.parse_args()

    book_id = args.book
    epub_path = args.epub or en_epub_path(book_id)

    ok = True
    for ch in args.chapter:
        meta = get_chapter(book_id, ch)
        data = extract_chapter(epub_path, book_id, ch)
        chars, words = _plain_body_words(epub_path, meta["en_file"])
        merged_chars = len(" ".join(data["merged_paragraphs"]))
        merged_words = len(" ".join(data["merged_paragraphs"]).split())
        ratio = merged_words / words if words else 0

        line = (
            f"Ch{ch:02d} {meta['title_en']}: "
            f"html≈{words}w → merged≈{merged_words}w ({ratio:.1%}), "
            f"sentences={data['sentence_count']}, paras={data['paragraph_count']}"
        )
        if ratio < 0.95:
            print(f"WARN {line}")
            ok = False
        else:
            print(f"OK   {line}")

        manifest = manifest_path(book_id, ch)
        if manifest.is_file():
            m = json.loads(manifest.read_text(encoding="utf-8"))
            lines = m.get("lines") or []
            total = m.get("total_sentences") or data["sentence_count"]
            interp = sum(1 for ln in lines if ln.get("interpolated"))
            high = sum(1 for ln in lines if ln.get("confidence", 0) >= 0.75)
            if len(lines) < total:
                print(f"  WARN manifest {len(lines)}/{total} lines (missing {total - len(lines)})")
                ok = False
            else:
                print(f"  manifest {len(lines)}/{total} lines, high≥0.75: {high}, interpolated: {interp}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
