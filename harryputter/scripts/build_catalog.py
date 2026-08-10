#!/usr/bin/env python3
"""Build per-book catalogs and output/library.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from chapters import (
    KNOWN_BOOKS,
    LIBRARY_PATH,
    audio_path,
    audio_rel,
    book_output_dir,
    catalog_path,
    catalog_rel,
    chapter_pad,
    load_book,
    manifest_path,
    manifest_rel,
)

ROOT = Path(__file__).resolve().parents[1]
LEGACY_CATALOG = ROOT / "output" / "catalog.json"


def build_book_catalog(book_id: str) -> dict:
    book = load_book(book_id)
    items = []
    for ch in book["chapters"]:
        cid = ch["id"]
        pad = chapter_pad(cid)
        mp3 = audio_path(book_id, cid)
        manifest = manifest_path(book_id, cid)
        entry = {
            "id": cid,
            "pad": pad,
            "title_en": ch["title_en"],
            "title_zh": ch["title_zh"],
            "audio": audio_rel(book_id, cid),
            "manifest": manifest_rel(book_id, cid),
            "has_audio": mp3.is_file(),
            "has_manifest": manifest.is_file(),
            "ready": mp3.is_file() and manifest.is_file(),
            "duration_sec": None,
            "aligned_lines": None,
        }
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            entry["duration_sec"] = data.get("duration")
            entry["aligned_lines"] = data.get("aligned_sentences") or len(data.get("lines", []))
            if data.get("audio"):
                entry["audio"] = data["audio"]
        items.append(entry)

    ready = sum(1 for x in items if x["ready"])
    return {
        "book_id": book_id,
        "book_title_en": book["book_title_en"],
        "book_title_zh": book["book_title_zh"],
        "chapter_count": book["chapter_count"],
        "ready_count": ready,
        "chapters": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default=None, help="single book (default: all known)")
    args = parser.parse_args()

    book_ids = [args.book] if args.book else list(KNOWN_BOOKS)
    library_books = []
    default_book = "hp01"

    for book_id in book_ids:
        catalog = build_book_catalog(book_id)
        out = catalog_path(book_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {out} — {catalog['ready_count']}/{catalog['chapter_count']} chapters ready")
        library_books.append(
            {
                "book_id": book_id,
                "book_title_en": catalog["book_title_en"],
                "book_title_zh": catalog["book_title_zh"],
                "chapter_count": catalog["chapter_count"],
                "ready_count": catalog["ready_count"],
                "catalog": catalog_rel(book_id),
            }
        )
    best = max(library_books, key=lambda b: (b["ready_count"], b["book_id"] == "hp01"))
    if best["ready_count"] > 0:
        default_book = best["book_id"]

    library = {
        "default_book_id": default_book,
        "books": library_books,
    }
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIBRARY_PATH.write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {LIBRARY_PATH}")

    # Legacy single-book catalog (default book) for old clients
    legacy_src = catalog_path(default_book)
    if legacy_src.is_file():
        LEGACY_CATALOG.write_text(legacy_src.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
