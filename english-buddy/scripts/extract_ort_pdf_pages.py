#!/usr/bin/env python3
"""Extract ORT story page images from 橙果玩英语 PDF scans.

橙果 PDF 结构（以 Level 3 为例）：
  p1  封面
  p2  家长导读
  p3… 故事第 1…N 页（与 catalog.json pages[].image 一一对应）
  …   家长活动页、封底

输出：frontend/public/ort/{book_id}/p01.jpg …

示例：
  python3 scripts/extract_ort_pdf_pages.py \\
    --pdf "$HOME/Documents/级别 (3)【橙果玩英语】/3-01 The Duck Race.pdf" \\
    --book ort_the_duck_race
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "catalog.json"
ORT_PUBLIC = ROOT / "frontend" / "public" / "ort"
ORT_PKG = ROOT / "backend" / "teaching" / "ort_oxford_owl"
sys.path.insert(0, str(ORT_PKG))

from chengguo_maps import pdf_map_for_level  # noqa: E402


def _load_book_page_count(book_id: str) -> int:
    books_json = ORT_PKG / "books.json"
    if books_json.is_file():
        from book_lines import image_page_count  # noqa: E402

        raw = json.loads(books_json.read_text(encoding="utf-8"))
        for book in raw.get("books") or []:
            if book.get("id") == book_id:
                n = image_page_count(book)
                if n > 0:
                    return n
    if CATALOG_JSON.is_file():
        data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
        for book in data.get("books") or []:
            if book.get("id") == book_id:
                return int(book.get("page_count") or len(book.get("pages") or []))
    raise SystemExit(f"book not found in books.json / catalog.json: {book_id}")


def _extract_story_images(
    pdf_path: Path,
    *,
    story_start: int,
    page_count: int,
    rotate: int,
    jpeg_quality: int,
) -> list[tuple[int, bytes]]:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise SystemExit(
            "PyMuPDF required: .venv/bin/pip install pymupdf pillow"
        ) from e
    from PIL import Image
    import io

    doc = fitz.open(pdf_path)
    available = max(0, doc.page_count - story_start + 1)
    if page_count > available:
        print(
            f"warn: PDF has {available} story pages ({story_start}–{doc.page_count}); "
            f"catalog wants {page_count} — extracting {available}",
            file=sys.stderr,
        )
        page_count = available
    if page_count <= 0:
        raise SystemExit(
            f"PDF has {doc.page_count} pages; no story pages from index {story_start}"
        )

    out: list[tuple[int, bytes]] = []
    for i in range(page_count):
        pdf_page = story_start + i
        page = doc[pdf_page - 1]
        imgs = page.get_images(full=True)
        if not imgs:
            raise SystemExit(f"no embedded image on PDF page {pdf_page}")
        info = doc.extract_image(imgs[0][0])
        img = Image.open(io.BytesIO(info["image"]))
        # 橙果扫描：奇数故事页 -90°，偶数故事页 +90°（相对默认 rotate）
        page_rotate = rotate if (i + 1) % 2 == 1 else -rotate
        if page_rotate:
            img = img.rotate(page_rotate, expand=True)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        out.append((i + 1, buf.getvalue()))
    return out


def _extract_cover_image(
    pdf_path: Path,
    *,
    cover_page: int,
    rotate: int,
    jpeg_quality: int,
) -> bytes:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise SystemExit(
            "PyMuPDF required: .venv/bin/pip install pymupdf pillow"
        ) from e
    from PIL import Image
    import io

    doc = fitz.open(pdf_path)
    if cover_page < 1 or cover_page > doc.page_count:
        raise SystemExit(f"cover page {cover_page} out of range (1–{doc.page_count})")
    page = doc[cover_page - 1]
    imgs = page.get_images(full=True)
    if not imgs:
        raise SystemExit(f"no embedded image on PDF cover page {cover_page}")
    info = doc.extract_image(imgs[0][0])
    img = Image.open(io.BytesIO(info["image"]))
    if rotate:
        img = img.rotate(rotate, expand=True)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    return buf.getvalue()


def _write_cover(
    pdf_path: Path,
    book_id: str,
    *,
    cover_page: int,
    rotate: int,
    quality: int,
    dry_run: bool,
) -> None:
    data = _extract_cover_image(
        pdf_path,
        cover_page=cover_page,
        rotate=rotate,
        jpeg_quality=quality,
    )
    dest = ORT_PUBLIC / book_id / "cover.jpg"
    if dry_run:
        print(f"  cover.jpg  {len(data) // 1024} KB (dry-run)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"  wrote {dest.relative_to(ROOT)} ({len(data) // 1024} KB)")


def _extract_one(
    pdf_path: Path,
    book_id: str,
    *,
    story_start: int,
    pages: int,
    rotate: int,
    quality: int,
    dry_run: bool,
    cover_page: int,
    write_cover: bool,
) -> None:
    page_count = pages or _load_book_page_count(book_id)
    dest_dir = ORT_PUBLIC / book_id

    print(f"PDF: {pdf_path.name}")
    print(f"Book: {book_id} ({page_count} story pages)")
    if write_cover:
        print(f"Cover: PDF page {cover_page} → cover.jpg")
    print(f"PDF pages: {story_start}–{story_start + page_count - 1}")
    print(f"Output: {dest_dir}/pNN.jpg")

    if write_cover:
        _write_cover(
            pdf_path,
            book_id,
            cover_page=cover_page,
            rotate=rotate,
            quality=quality,
            dry_run=dry_run,
        )

    images = _extract_story_images(
        pdf_path,
        story_start=story_start,
        page_count=page_count,
        rotate=rotate,
        jpeg_quality=quality,
    )

    if dry_run:
        for idx, data in images:
            print(f"  p{idx:02d}.jpg  {len(data)//1024} KB")
        print("dry-run: no story files written")
        return

    expected = _load_book_page_count(book_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for idx, data in images:
        path = dest_dir / f"p{idx:02d}.jpg"
        path.write_bytes(data)
        print(f"  wrote {path.relative_to(ROOT)} ({len(data)//1024} KB)")

    if len(images) < expected and images:
        last = images[-1][1]
        for idx in range(len(images) + 1, expected + 1):
            path = dest_dir / f"p{idx:02d}.jpg"
            path.write_bytes(last)
            print(f"  padded {path.relative_to(ROOT)} (copy of last page)")

    print(f"done: {len(images)} pages → {dest_dir}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract ORT page images from 橙果 PDF")
    parser.add_argument("--pdf", type=Path, help="Path to 橙果 PDF")
    parser.add_argument("--book", help="ORT book id, e.g. ort_the_duck_race")
    parser.add_argument(
        "--batch-level",
        choices=["2", "3"],
        metavar="N",
        help="Batch level (2 or 3); use with --batch-dir",
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        metavar="DIR",
        help="橙果玩英语文件夹，如 ~/Documents/Oxfordreadingtree/级别 (2)【橙果玩英语】",
    )
    parser.add_argument(
        "--batch-level3",
        type=Path,
        metavar="DIR",
        help="(兼容) 同 --batch-level 3 --batch-dir DIR",
    )
    parser.add_argument(
        "--batch-level3-covers",
        type=Path,
        metavar="DIR",
        help="(兼容) Level 3 仅 cover.jpg",
    )
    parser.add_argument(
        "--batch-level2-covers",
        type=Path,
        metavar="DIR",
        help="Level 2 仅 cover.jpg",
    )
    parser.add_argument(
        "--cover-page",
        type=int,
        default=1,
        help="1-based PDF page for cover.jpg (default: 1)",
    )
    parser.add_argument(
        "--covers-only",
        action="store_true",
        help="With --pdf/--book: only write cover.jpg",
    )
    parser.add_argument(
        "--no-cover",
        action="store_true",
        help="Skip cover.jpg when extracting story pages",
    )
    parser.add_argument(
        "--story-start",
        type=int,
        default=3,
        help="1-based PDF page index of first story page (default: 3)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=0,
        help="Story page count (default: from catalog.json)",
    )
    parser.add_argument(
        "--rotate",
        type=int,
        default=-90,
        help="PIL rotate degrees for upright pages (default: -90)",
    )
    parser.add_argument("--quality", type=int, default=88, help="JPEG quality")
    parser.add_argument("--dry-run", action="store_true", help="Probe only, do not write")
    args = parser.parse_args()

    def _run_batch(batch_dir: Path, level: str, *, covers_only: bool) -> None:
        if not batch_dir.is_dir():
            raise SystemExit(f"batch dir not found: {batch_dir}")
        ok, fail = 0, 0
        for pdf_name, book_id in pdf_map_for_level(level):
            pdf_path = batch_dir / pdf_name
            if not pdf_path.is_file():
                print(f"SKIP missing PDF: {pdf_name}")
                fail += 1
                continue
            try:
                print(f"PDF: {pdf_path.name} → {book_id}")
                if covers_only:
                    _write_cover(
                        pdf_path,
                        book_id,
                        cover_page=args.cover_page,
                        rotate=args.rotate,
                        quality=args.quality,
                        dry_run=args.dry_run,
                    )
                else:
                    _extract_one(
                        pdf_path,
                        book_id,
                        story_start=args.story_start,
                        pages=args.pages,
                        rotate=args.rotate,
                        quality=args.quality,
                        dry_run=args.dry_run,
                        cover_page=args.cover_page,
                        write_cover=not args.no_cover,
                    )
                ok += 1
            except SystemExit as e:
                print(f"FAIL {book_id}: {e}")
                fail += 1
        print(f"batch done: {ok} ok, {fail} skipped/failed")

    if args.batch_level and args.batch_dir:
        _run_batch(args.batch_dir.expanduser().resolve(), args.batch_level, covers_only=False)
        return

    if args.batch_level3:
        _run_batch(args.batch_level3.expanduser().resolve(), "3", covers_only=False)
        return

    if args.batch_level3_covers:
        _run_batch(args.batch_level3_covers.expanduser().resolve(), "3", covers_only=True)
        return

    if args.batch_level2_covers:
        _run_batch(args.batch_level2_covers.expanduser().resolve(), "2", covers_only=True)
        return

    if not args.pdf or not args.book:
        raise SystemExit(
            "use --pdf + --book, --batch-level N --batch-dir DIR, "
            "or --batch-level3/--batch-level2-covers DIR"
        )

    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    if args.covers_only:
        _write_cover(
            pdf_path,
            args.book,
            cover_page=args.cover_page,
            rotate=args.rotate,
            quality=args.quality,
            dry_run=args.dry_run,
        )
        return

    _extract_one(
        pdf_path,
        args.book,
        story_start=args.story_start,
        pages=args.pages,
        rotate=args.rotate,
        quality=args.quality,
        dry_run=args.dry_run,
        cover_page=args.cover_page,
        write_cover=not args.no_cover,
    )


if __name__ == "__main__":
    main()
