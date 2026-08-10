#!/usr/bin/env python3
"""从橙果 PDF 页图 OCR 提取 ORT 官方课文（macOS Vision / ocrmac）。

替代爱贝 i-bei 指导页文本；与 extract_ort_pdf_pages.py 页数对齐。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "books.json"
sys.path.insert(0, str(ROOT / "backend"))

from teaching.ort_oxford_owl.chengguo_maps import CHENGGUO_BY_LEVEL, chengguo_batch_dir  # noqa: E402
from teaching.ort_oxford_owl.pdf_extract import (  # noqa: E402
    extract_pdf_page_jpeg,
    pdf_story_page_count,
)


def _is_story_fragment(text: str) -> bool:
    t = text.strip()
    if not t or re.fullmatch(r"\d{1,2}", t):
        return False
    if len(t) <= 5 and t.isupper():
        return False
    if not re.search(r"[a-zA-Z]", t):
        return False
    words = re.findall(r"[a-zA-Z']+", t)
    if not words:
        return False
    if len(words) == 1 and len(words[0]) <= 2 and words[0] not in ("I", "Oh"):
        return False
    if any(ch in t for ch in '."\'?!,'):
        return True
    return len(words) >= 2


def _ocr_region(im, y0_frac: float, y1_frac: float) -> str:
    from ocrmac import ocrmac

    w, h = im.size
    crop = im.crop((int(w * 0.05), int(h * y0_frac), int(w * 0.95), int(h * y1_frac)))
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    crop.save(tmp.name, quality=92)
    tmp.close()
    try:
        anns = ocrmac.OCR(tmp.name).recognize()
    finally:
        os.unlink(tmp.name)
    parts = [a[0].strip() for a in anns if a[1] >= 0.4 and _is_story_fragment(a[0])]
    return " ".join(parts).strip()


def ocr_story_sentence(jpeg_bytes: bytes) -> str:
    try:
        from ocrmac import ocrmac  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "ocrmac required (macOS Vision OCR): .venv/bin/pip install ocrmac"
        ) from e
    from PIL import Image
    import io

    im = Image.open(io.BytesIO(jpeg_bytes))
    for y0, y1 in ((0.72, 1.0), (0.0, 0.24), (0.40, 0.58)):
        text = _ocr_region(im, y0, y1)
        if text:
            return text
    return ""


def ocr_story_lines(jpeg_bytes: bytes) -> list[str]:
    """每页 0–2 句：页底 / 页顶 / 上下双格。"""
    from PIL import Image
    import io

    im = Image.open(io.BytesIO(jpeg_bytes))
    regions = (
        (0.0, 0.24),
        (0.40, 0.58),
        (0.72, 1.0),
    )
    found: list[str] = []
    seen: set[str] = set()
    for y0, y1 in regions:
        text = _ocr_region(im, y0, y1)
        if not text or text in seen:
            continue
        seen.add(text)
        found.append(text)
    if len(found) <= 1:
        return found
    # 双格页：按区域顺序（上→中→下）保留
    ordered: list[str] = []
    for y0, y1 in regions:
        text = _ocr_region(im, y0, y1)
        if text and text not in ordered:
            ordered.append(text)
    return ordered[:2]


def extract_book_pages(pdf_path: Path, *, story_start: int = 3) -> list[dict]:
    n = pdf_story_page_count(pdf_path)
    pages: list[dict] = []
    for i in range(n):
        pdf_page = story_start + i
        jpeg = extract_pdf_page_jpeg(pdf_path, pdf_page)
        lines = ocr_story_lines(jpeg)
        pages.append({"lines": lines} if lines else {"lines": []})
    return pages


def flatten_pages(pages: list[dict]) -> list[str]:
    out: list[str] = []
    for page in pages:
        for ln in page.get("lines") or []:
            s = str(ln).strip()
            if s:
                out.append(s)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=["2", "3", "4"], default="2")
    parser.add_argument("--book", help="Single book id, e.g. ort_poor_floppy")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--batch-dir",
        type=Path,
        help="橙果 PDF 目录（默认 ENGLISH_BUDDY_CHENGGUO_L{n}_DIR）",
    )
    args = parser.parse_args()

    batch = (args.batch_dir or chengguo_batch_dir(args.level)).expanduser()
    if not batch.is_dir():
        raise SystemExit(f"batch dir not found: {batch}")

    pdf_map = {bid: (pdf, title) for pdf, bid, title in CHENGGUO_BY_LEVEL.get(args.level, [])}
    targets = [args.book] if args.book else list(pdf_map)
    if args.book and args.book not in pdf_map:
        raise SystemExit(f"unknown book: {args.book}")

    raw = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
    by_id = {b["id"]: b for b in raw.get("books") or []}

    for bid in targets:
        pdf_name, title = pdf_map[bid]
        pdf_path = batch / pdf_name
        if not pdf_path.is_file():
            print(f"SKIP {bid}: missing PDF")
            continue
        print(f"OCR {pdf_name} → {bid} …")
        pages = extract_book_pages(pdf_path)
        lines = flatten_pages(pages)
        text_n = sum(1 for p in pages if p.get("lines"))
        print(f"  {len(pages)} pages, {text_n} with text, {len(lines)} lines")
        if args.dry_run:
            for i, p in enumerate(pages, start=1):
                ln = (p.get("lines") or [""])[0]
                print(f"    p{i:02d}: {ln or '(illus)'}")
            continue
        book = by_id.get(bid) or {
            "id": bid,
            "title": title,
            "ort_level": args.level,
            "book_band": {"2": "Red", "3": "Yellow", "4": "Blue"}.get(args.level, "Blue"),
            "series": (
                "Oxford Reading Tree · Stories"
                if args.level == "4"
                else f"Oxford Reading Tree · Stage {args.level}"
            ),
        }
        book["title"] = title
        book["lines"] = lines
        book["pages"] = pages
        by_id[bid] = book

    if args.dry_run:
        return 0

    raw["books"] = [by_id.get(b["id"], b) for b in raw.get("books") or []]
    note = (
        "ORT 课文真源：橙果 PDF 官方页底 OCR（extract_ort_pdf_lines.py）；"
        "页图 extract_ort_pdf_pages.py。Level 2 勿用爱贝 i-bei。"
    )
    raw["note"] = note
    BOOKS_JSON.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {BOOKS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
