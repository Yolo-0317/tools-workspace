#!/usr/bin/env python3
"""把 ORT 扁平 lines[] 合并为 pages[]（同页多句共用一张插图）。

带读仍按「句」推进；翻页图仅在进入下一插图页时切换（catalog + 前端已支持）。

示例：
  # 每 2 句合并为一页（常见：一书页两句）
  .venv/bin/python scripts/sync_ort_page_groups.py --book ort_the_go_kart --lines-per-page 2

  # 12 句合并为 8 张插图页（均匀分块）
  .venv/bin/python scripts/sync_ort_page_groups.py --book ort_the_toys_party --image-pages 8

  # 整级 Level 2 默认每页 2 句（可先 --dry-run）
  .venv/bin/python scripts/sync_ort_page_groups.py --ort-level 2 --lines-per-page 2 --dry-run

之后：
  cd backend && python3 teaching/build_lessons_v5.py
  .venv/bin/python scripts/extract_ort_pdf_pages.py --batch-level 2 --batch-dir \"...\"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "books.json"
sys.path.insert(0, str(ROOT / "backend" / "teaching" / "ort_oxford_owl"))

from book_lines import (  # noqa: E402
    apply_page_groups_to_book,
    distribute_lines_evenly,
    distribute_lines_pairs,
    flatten_lines,
    image_page_count,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", action="append", help="book id，可重复")
    parser.add_argument("--ort-level", help="如 2、3")
    parser.add_argument(
        "--lines-per-page",
        type=int,
        metavar="N",
        help="连续 N 句合并为一插图页",
    )
    parser.add_argument(
        "--image-pages",
        type=int,
        metavar="N",
        help="目标插图页数（均匀分句）",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.lines_per_page and not args.image_pages:
        raise SystemExit("specify --lines-per-page N or --image-pages N")
    if args.lines_per_page and args.image_pages:
        raise SystemExit("use only one of --lines-per-page / --image-pages")

    raw = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
    books = raw.get("books") or []
    targets = {b["id"]: b for b in books}

    ids: list[str] = []
    if args.book:
        ids.extend(args.book)
    if args.ort_level:
        for b in books:
            if str(b.get("ort_level")) == args.ort_level:
                ids.append(b["id"])
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise SystemExit("no books matched")

    changed = 0
    for bid in ids:
        book = targets.get(bid)
        if not book:
            print(f"SKIP unknown {bid}")
            continue
        lines = flatten_lines(book)
        if not lines:
            print(f"SKIP {bid}: no lines")
            continue
        old_pages = image_page_count(book)
        if args.lines_per_page:
            groups = distribute_lines_pairs(lines, args.lines_per_page)
        else:
            groups = distribute_lines_evenly(lines, args.image_pages)
        new_pages = len(groups)
        sizes = [len(g) for g in groups]
        print(f"{bid}: {len(lines)} lines, pages {old_pages} -> {new_pages} groups {sizes}")
        if args.dry_run:
            continue
        targets[bid] = apply_page_groups_to_book(book, groups)
        changed += 1

    if args.dry_run:
        print("dry-run: no files written")
        return 0

    raw["books"] = list(targets.values())
    BOOKS_JSON.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {BOOKS_JSON} ({changed} books updated)")
    print("next: cd backend && python3 teaching/build_lessons_v5.py")
    print("then re-extract images for affected books (page_count changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
