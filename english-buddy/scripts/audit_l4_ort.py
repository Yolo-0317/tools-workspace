#!/usr/bin/env python3
"""Audit ORT Level 4: image rotation, empty pages, multi-line pages, padding.

  cd english-buddy && .venv/bin/python3 scripts/audit_l4_ort.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "books.json"
ORT_PUBLIC = ROOT / "frontend" / "public" / "ort"
sys.path.insert(0, str(ROOT / "backend"))

from teaching.ort_oxford_owl.book_lines import flatten_lines  # noqa: E402
from teaching.ort_oxford_owl.chengguo_maps import CHENGGUO_LEVEL4, chengguo_batch_dir  # noqa: E402


from teaching.ort_oxford_owl.pdf_extract import pdf_story_page_count as pdf_story_pages  # noqa: E402


def jpg_orientation(path: Path) -> str:
    from PIL import Image

    w, h = Image.open(path).size
    if h > w * 1.05:
        return "portrait"
    if w > h * 1.05:
        return "landscape"
    return "square"


def padded_tail_pages(book_dir: Path) -> list[int]:
    jpgs = sorted(book_dir.glob("p*.jpg"))
    if len(jpgs) < 2:
        return []
    sizes = [p.stat().st_size for p in jpgs]
    last = sizes[-1]
    run = [len(jpgs)]
    for i in range(len(sizes) - 2, -1, -1):
        if sizes[i] == last:
            run.insert(0, i + 1)
        else:
            break
    return run if len(run) >= 2 else []


def main() -> int:
    try:
        import fitz  # noqa: F401
    except ImportError:
        print("pip install pymupdf pillow", file=sys.stderr)
        return 1

    batch = chengguo_batch_dir("4")
    books = {b["id"]: b for b in json.loads(BOOKS_JSON.read_text())["books"]}

    rot_bad: list[str] = []
    rows: list[dict] = []

    for pdf_name, bid, title in CHENGGUO_LEVEL4:
        book = books[bid]
        pdf_path = batch / pdf_name
        pdf_n = fitz.open(pdf_path).page_count if pdf_path.is_file() else 0
        story_n = pdf_story_pages(pdf_path) if pdf_path.is_file() else 0
        flat = flatten_lines(book)
        pages = book.get("pages")
        json_pages = len(pages) if pages else len(flat)
        empty = sum(1 for p in (pages or []) if not (p.get("lines") or []))
        multi = sum(1 for p in (pages or []) if len(p.get("lines") or []) > 1)
        book_dir = ORT_PUBLIC / bid
        jpg_n = len(list(book_dir.glob("p*.jpg"))) if book_dir.is_dir() else 0
        pad = padded_tail_pages(book_dir) if book_dir.is_dir() else []

        for n in (1, 2):
            p = book_dir / f"p{n:02d}.jpg"
            if p.is_file() and jpg_orientation(p) == "landscape":
                rot_bad.append(f"{bid} {p.name} landscape")

        flags: list[str] = []
        if not pages:
            flags.append("no_pages[]")
        if json_pages != story_n:
            flags.append(f"pages={json_pages}≠pdf{story_n}")
        if jpg_n > story_n:
            flags.append(f"jpg_pad+{jpg_n - story_n}")
        if empty:
            flags.append(f"empty={empty}")
        if multi:
            flags.append(f"multi={multi}")

        rows.append(
            {
                "bid": bid,
                "title": title,
                "pdf": pdf_n,
                "story": story_n,
                "lines": len(flat),
                "json_pages": json_pages,
                "jpg": jpg_n,
                "empty": empty,
                "multi": multi,
                "pad_from": pad[0] if pad else None,
                "flags": flags,
            }
        )

    print("=== L4 ORT audit ===\n")
    print(
        f"{'book':<28} {'story':>5} {'lines':>5} {'pages':>5} {'jpg':>4} "
        f"{'empty':>5} {'multi':>5}  flags"
    )
    print("-" * 88)
    for r in rows:
        fl = " ".join(r["flags"]) or "ok"
        print(
            f"{r['bid']:<28} {r['story']:>5} {r['lines']:>5} {r['json_pages']:>5} "
            f"{r['jpg']:>4} {r['empty']:>5} {r['multi']:>5}  {fl}"
        )

    print(f"\nRotation issues: {len(rot_bad)}")
    for x in rot_bad:
        print(f"  {x}")

    no_pages = [r for r in rows if "no_pages[]" in r["flags"]]
    padded = [r for r in rows if "jpg_pad" in " ".join(r["flags"])]
    with_empty = [r for r in rows if r["empty"] > 0]
    with_multi = [r for r in rows if r["multi"] > 0]

    print(f"\nSummary: {len(rows)} books")
    print(f"  missing pages[]: {len(no_pages)}")
    print(f"  padded JPEG tail: {len(padded)}")
    print(f"  has empty illustration pages: {len(with_empty)}")
    print(f"  has multi-line pages: {len(with_multi)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
