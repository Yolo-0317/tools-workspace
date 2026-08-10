#!/usr/bin/env python3
"""Align L2 books.json pages[] with standard 16-page 橙果 PDF layout.

Landscape 9 句本（如 New Trainers）：前 2 页各 1 句，之后每句前插 1 纯插图页 → 16 页。
竖版 16 句本（如 Poor Floppy）：一句一页，共 16 页。
已有 pages[] 的书不覆盖。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "books.json"
sys.path.insert(0, str(ROOT / "backend"))

from teaching.ort_oxford_owl.chengguo_maps import CHENGGUO_LEVEL2  # noqa: E402


def distribute_nine_lines(lines: list[str], total: int = 16) -> list[dict]:
    """ORT L2 九句本标准排版：2 句 + (插图, 句)×7。"""
    pages: list[dict] = []
    if len(lines) >= 1:
        pages.append({"lines": [lines[0]]})
    if len(lines) >= 2:
        pages.append({"lines": [lines[1]]})
    for i in range(2, len(lines)):
        pages.append({"lines": []})
        pages.append({"lines": [lines[i]]})
    while len(pages) < total:
        pages.append({"lines": []})
    return pages[:total]


def is_portrait_pdf(pdf_path: Path) -> bool:
    try:
        import fitz
        from PIL import Image
        import io
    except ImportError:
        return False
    doc = fitz.open(pdf_path)
    imgs = doc[0].get_images(full=True)
    if not imgs:
        return False
    info = doc.extract_image(imgs[0][0])
    w, h = Image.open(io.BytesIO(info["image"])).size
    return h > w


def pdf_story_page_count(pdf_path: Path) -> int:
    import fitz

    doc = fitz.open(pdf_path)
    if doc.page_count >= 20:
        return 16
    if doc.page_count >= 18:
        return doc.page_count - 2
    return max(0, doc.page_count - 2)


def main() -> int:
    batch = Path(
        __import__("os").environ.get(
            "ENGLISH_BUDDY_CHENGGUO_L2_DIR",
            "~/Documents/Oxfordreadingtree/级别 (2)【橙果玩英语】",
        )
    ).expanduser()

    raw = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
    books = raw.get("books") or []
    by_id = {b["id"]: b for b in books}
    updated: list[str] = []

    for pdf_name, bid, _title in CHENGGUO_LEVEL2:
        book = by_id.get(bid)
        if not book or book.get("ort_level") != "2":
            continue
        if book.get("pages"):
            continue
        lines = [str(ln).strip() for ln in book.get("lines") or [] if str(ln).strip()]
        pdf_path = batch / pdf_name
        if not pdf_path.is_file():
            continue
        story_n = pdf_story_page_count(pdf_path)
        portrait = is_portrait_pdf(pdf_path)

        if portrait and story_n >= 16 and len(lines) >= 16:
            book["pages"] = [{"lines": [ln]} for ln in lines[:16]]
            updated.append(f"{bid}: portrait 16×1 line")
        elif not portrait and len(lines) == 9 and story_n == 16:
            book["pages"] = distribute_nine_lines(lines, total=16)
            updated.append(f"{bid}: landscape 9 lines → 16 pages")
        elif portrait and story_n >= len(lines):
            book["pages"] = [{"lines": [ln]} for ln in lines]
            while len(book["pages"]) < story_n:
                book["pages"].append({"lines": []})
            book["pages"] = book["pages"][:story_n]
            updated.append(f"{bid}: portrait {len(lines)} lines → {len(book['pages'])} pages")

    if updated:
        BOOKS_JSON.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"updated {len(updated)} books")
    for line in updated:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
