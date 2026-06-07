#!/usr/bin/env python3
"""把橙果 Level 2 课文合并进 books.json（爱贝 JSON + manual JSON，图与文分离）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "books.json"
ORT_DIR = ROOT / "backend" / "teaching" / "ort_oxford_owl"
sys.path.insert(0, str(ORT_DIR))

from chengguo_maps import CHENGGUO_LEVEL2  # noqa: E402

IBEI_JSON = ORT_DIR / "chengguo_level2_ibei.json"
MANUAL_JSON = ORT_DIR / "chengguo_level2_manual.json"


def _load_lines_map(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for book in data.get("books") or []:
        bid = book.get("id") or ""
        lines = [str(ln).strip() for ln in book.get("lines") or [] if str(ln).strip()]
        if bid and lines:
            out[bid] = lines
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ibei = _load_lines_map(IBEI_JSON)
    manual = _load_lines_map(MANUAL_JSON)
    raw = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
    existing = {b["id"]: b for b in raw.get("books") or []}

    added, updated, skipped = 0, 0, 0
    for _pdf, book_id, title in CHENGGUO_LEVEL2:
        lines = ibei.get(book_id) or manual.get(book_id)
        if not lines:
            print(f"SKIP {book_id}: no lines (run fetch_chengguo_ibei_lines.py or edit manual JSON)")
            skipped += 1
            continue
        entry = {
            "id": book_id,
            "title": title,
            "ort_level": "2",
            "book_band": "Red",
            "series": "Oxford Reading Tree · Stage 2",
            "lines": lines,
        }
        if book_id in existing:
            existing[book_id].update(entry)
            updated += 1
        else:
            existing[book_id] = entry
            added += 1
        print(f"ok {book_id}: {len(lines)} lines")

    if skipped:
        print(f"warning: {skipped} books without text", file=sys.stderr)

    raw["books"] = list(existing.values())
    note = raw.get("note") or ""
    if "Level 2" not in note:
        raw["note"] = note.replace(
            "Stage 1 / Level 1+ / Level 3",
            "Stage 1 / Level 1+ / Level 2（Red）/ Level 3",
        )

    if args.dry_run:
        print(f"dry-run: would add {added}, update {updated}")
        return 0

    BOOKS_JSON.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {BOOKS_JSON} (+{added} ~{updated})")
    return 0 if skipped == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
