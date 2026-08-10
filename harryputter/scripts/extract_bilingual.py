#!/usr/bin/env python3
"""Extract bilingual chapter → paragraph-level clips + align to audio."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bilingual_clips import fixes_path  # noqa: E402
from chapters import bilingual_pdf_path, bilingual_epub_path, sentences_path, zh_extract_path  # noqa: E402


def _write_outputs(data: dict, book_id: str, chapter: int, write_fixes: bool) -> None:
    ch_pad = f"{chapter:02d}"

    sentences_out = sentences_path(book_id, chapter)
    sentences_doc = {
        "chapter": data["chapter"],
        "title": data["title"],
        "heading_en": data["heading_en"],
        "sentence_count": data["sentence_count"],
        "body_sentence_count": data["body_sentence_count"],
        "sentences": data["sentences"],
        "kinds": data["kinds"],
        "source": data["source"],
        "granularity": data.get("granularity", "paragraph"),
    }
    sentences_out.parent.mkdir(parents=True, exist_ok=True)
    sentences_out.write_text(json.dumps(sentences_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    zh_out = zh_extract_path(book_id, chapter)
    zh_doc = {
        "chapter": data["chapter"],
        "title": data["title_zh"],
        "heading_zh": data["heading_zh"],
        "sentence_count": data["sentence_count"],
        "body_sentence_count": data["body_sentence_count"],
        "sentences": data["zh_sentences"],
        "kinds": data["kinds"],
        "source": data["source"],
        "zh_variant": data["zh_variant"],
        "granularity": data.get("granularity", "paragraph"),
    }
    zh_out.write_text(json.dumps(zh_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if write_fixes:
        fixes = {
            "comment": f"{book_id} ch{ch_pad} · paragraph bilingual_clips ({data['source']})",
            "source": data["source"],
            "granularity": data.get("granularity", "paragraph"),
            "zh_variant": data.get("zh_variant", "zh-cn"),
            "bilingual_clips": data["bilingual_clips"],
        }
        fpath = fixes_path(book_id, chapter)
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(json.dumps(fixes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {fpath} ({len(data['bilingual_clips'])} paragraph clips)")

    print(
        f"{book_id} ch{chapter}: {data['paragraph_pairs']} paragraph pairs → "
        f"{data['sentence_count']} clips → {sentences_out}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--source", choices=("auto", "pdf", "epub"), default="auto")
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--epub", type=Path, default=None)
    parser.add_argument("--write-fixes", action="store_true", default=True)
    parser.add_argument("--no-write-fixes", dest="write_fixes", action="store_false")
    args = parser.parse_args()

    pdf = args.pdf or bilingual_pdf_path(args.book)
    epub = args.epub or bilingual_epub_path(args.book)

    if args.source == "pdf" or (args.source == "auto" and pdf.is_file()):
        from bilingual_pdf import extract_chapter as extract_pdf  # noqa: E402

        if not pdf.is_file():
            raise SystemExit(f"Bilingual PDF missing: {pdf}")
        data = extract_pdf(pdf, args.book, args.chapter)
    elif args.source == "epub" or (args.source == "auto" and epub.is_file()):
        from bilingual_epub import extract_chapter as extract_epub  # noqa: E402

        if not epub.is_file():
            raise SystemExit(f"Bilingual EPUB missing: {epub}")
        data = extract_epub(epub, args.book, args.chapter)
    else:
        raise SystemExit(
            f"No bilingual source found.\n"
            f"  PDF: {pdf}\n"
            f"  EPUB: {epub}\n"
            f"Run: BOOK={args.book} ./scripts/import_downloads.sh"
        )

    _write_outputs(data, args.book, args.chapter, args.write_fixes)


if __name__ == "__main__":
    main()
