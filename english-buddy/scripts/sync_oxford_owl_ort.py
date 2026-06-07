#!/usr/bin/env python3
"""校验 / 维护 Oxford Reading Tree 课文真源 books.json。

Oxford Owl 免费电子书需注册登录，阅读器为翻页 UI，暂无稳定公开 API。
批量抓取请用浏览器登录后人工核对，再编辑：

  backend/teaching/ort_oxford_owl/books.json

然后：

  cd english-buddy/backend && python3 teaching/build_lessons_v5.py
  cd english-buddy && ./scripts/restart.sh --build
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "backend" / "teaching" / "ort_oxford_owl" / "books.json"
OWL_LIBRARY = (
    "https://www.oxfordowl.co.uk/for-home/find-a-book/library-page/"
    "?series=Oxford+Reading+Tree"
)


def validate(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    books = data.get("books") or []
    if not books:
        print("error: books[] 为空", file=sys.stderr)
        return 1
    ids: set[str] = set()
    for i, book in enumerate(books, start=1):
        bid = book.get("id") or ""
        title = book.get("title") or ""
        lines = book.get("lines") or []
        if not bid or not title:
            print(f"error: 第 {i} 本缺少 id/title", file=sys.stderr)
            return 1
        if bid in ids:
            print(f"error: 重复 id {bid}", file=sys.stderr)
            return 1
        ids.add(bid)
        if not lines:
            print(f"error: {bid} 无 lines", file=sys.stderr)
            return 1
        for ln in lines:
            if len(ln.split()) > 12:
                print(f"warn: {bid} 行较长({len(ln.split())}词): {ln[:60]}...")
    print(f"ok: {len(books)} 本 ORT · 库 {OWL_LIBRARY}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--books",
        type=Path,
        default=BOOKS,
        help="books.json 路径",
    )
    args = parser.parse_args()
    if not args.books.is_file():
        print(f"error: 找不到 {args.books}", file=sys.stderr)
        return 1
    return validate(args.books)


if __name__ == "__main__":
    raise SystemExit(main())
