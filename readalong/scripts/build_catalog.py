#!/usr/bin/env python3
"""Build output/catalog.json — scan samples + manifests for chapter readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from chapters import ROOT, audio_path, audio_rel, chapter_pad, load_book

OUT = ROOT / "output" / "catalog.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    args = parser.parse_args()

    book_id = args.book
    book = load_book(book_id)
    items = []
    for ch in book["chapters"]:
        cid = ch["id"]
        pad = chapter_pad(cid)
        mp3 = audio_path(book_id, cid)
        manifest = ROOT / "output" / f"ch{pad}.json"
        entry = {
            "id": cid,
            "pad": pad,
            "title_en": ch["title_en"],
            "title_zh": ch["title_zh"],
            "audio": audio_rel(book_id, cid),
            "manifest": f"output/ch{pad}.json",
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
    catalog = {
        "book_id": book_id,
        "book_title_en": book["book_title_en"],
        "book_title_zh": book["book_title_zh"],
        "chapter_count": book["chapter_count"],
        "ready_count": ready,
        "chapters": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} — {ready}/{len(items)} chapters ready")


if __name__ == "__main__":
    main()
