#!/usr/bin/env python3
"""Fix L2 ORT books after The Wobbly Tooth: JPG OCR + pages[] + image paths.

  cd english-buddy && .venv/bin/python3 scripts/fix_l2_ort_after_wobbly.py
  .venv/bin/python3 scripts/fix_l2_ort_after_wobbly.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "books.json"
ORT_PUBLIC = ROOT / "frontend" / "public" / "ort"
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from extract_ort_pdf_lines import ocr_story_lines  # noqa: E402

SKIP = frozenset({"ort_the_band"})

AFTER_WOBBLY = [
    "ort_the_foggy_day",
    "ort_biffs_aeroplane",
    "ort_floppy_the_hero",
    "ort_the_chase",
    "ort_the_big_egg",
    "ort_poor_floppy",
    "ort_put_it_back",
    "ort_in_a_bit",
    "ort_a_present_for_mum",
    "ort_a_hole_in_the_sand",
    "ort_monkey_tricks",
    "ort_hey_presto",
    "ort_its_the_weather",
    "ort_naughty_children",
    "ort_a_sinking_feeling",
    "ort_creepy_crawly",
    "ort_what_is_it",
    "ort_the_lost_puppy",
    "ort_new_trees",
    "ort_up_and_down",
    "ort_the_little_dragon",
]

GARBAGE_RE = re.compile(
    r"^(WELCOME TO|CIVIC |GAS BILL|J\.LOWE|RHESUS|PARK KEEPER|Bone Meal|www\.|Scene\.|"
    r"DO NOT ON GLASS|d1 N|el\. 4lcr|• )",
    re.I,
)


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def clean_line(s: str) -> str:
    t = s.strip()
    if not t:
        return ""
    if GARBAGE_RE.search(t):
        return ""
    if len(t) <= 12 and t.isupper() and not any(c in t for c in '."\'?!'):
        return ""
    # trim sign junk suffix
    t = re.sub(r"\s+(SHOP|al r)\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+v SHOP\s*$", "", t, flags=re.I)
    # fix missing open quote before said
    if re.search(r'[^"]\s*said\b', t, re.I) and not t.startswith('"'):
        t = '"' + t
    # normalize ellipsis
    t = t.replace("..", ".")
    return t.strip()


def ocr_book_from_jpgs(book_id: str) -> list[dict]:
    book_dir = ORT_PUBLIC / book_id
    jpgs = sorted(book_dir.glob("p*.jpg"), key=lambda p: int(p.stem[1:]))
    pages: list[dict] = []
    for jpg in jpgs:
        raw_lines = ocr_story_lines(jpg.read_bytes())
        lines = [clean_line(ln) for ln in raw_lines]
        lines = [ln for ln in lines if ln]
        pages.append(
            {
                "lines": lines,
                "image": f"{book_id}/{jpg.name}",
            }
        )
    return pages


def flatten_pages(pages: list[dict]) -> list[str]:
    out: list[str] = []
    for p in pages:
        for ln in p.get("lines") or []:
            s = str(ln).strip()
            if s:
                out.append(s)
    return out


def needs_fix(book: dict) -> bool:
    pages = book.get("pages") or []
    if not pages:
        return True
    empty = sum(1 for p in pages if not (p.get("lines") or []))
    no_img = sum(1 for p in pages if not p.get("image"))
    odd_empty = [i + 1 for i, p in enumerate(pages) if not (p.get("lines") or []) and i % 2 == 1]
    if no_img:
        return True
    if len(odd_empty) >= 3:
        return True
    if empty >= 3 and len(flatten_pages(pages)) < 12:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--book", help="Single book id")
    args = parser.parse_args()

    targets = [args.book] if args.book else AFTER_WOBBLY
    raw = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
    by_id = {b["id"]: b for b in raw.get("books") or []}
    updated: list[str] = []

    for bid in targets:
        if bid in SKIP:
            print(f"SKIP {bid} (already aligned)")
            continue
        book = by_id.get(bid)
        if not book:
            print(f"MISSING {bid}")
            continue
        if not needs_fix(book):
            print(f"OK    {bid}")
            continue
        book_dir = ORT_PUBLIC / bid
        if not book_dir.is_dir():
            print(f"NOIMG {bid}")
            continue
        print(f"OCR  {bid} …", flush=True)
        pages = ocr_book_from_jpgs(bid)
        lines = flatten_pages(pages)
        text_n = sum(1 for p in pages if p.get("lines"))
        print(f"     {len(pages)} pages, {text_n} with text, {len(lines)} lines")
        if args.dry_run:
            for i, p in enumerate(pages, start=1):
                ln = " | ".join(p.get("lines") or []) or "(illus)"
                print(f"    p{i:02d}: {ln}")
            continue
        book["pages"] = pages
        book["lines"] = lines
        updated.append(bid)

    if args.dry_run:
        return 0

    if updated:
        BOOKS_JSON.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"\nupdated {len(updated)} books")
    for bid in updated:
        print(f"  {bid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
