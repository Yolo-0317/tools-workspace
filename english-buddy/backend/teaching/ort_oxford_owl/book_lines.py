"""ORT books.json：扁平 lines 与按页 pages[] 互转。"""

from __future__ import annotations


def flatten_lines(book: dict) -> list[str]:
    """带读课文真源：优先 pages[].lines，否则 lines[]。"""
    pages = book.get("pages")
    if pages:
        out: list[str] = []
        for page in pages:
            for ln in page.get("lines") or []:
                s = str(ln).strip()
                if s:
                    out.append(s)
        return out
    return [str(ln).strip() for ln in book.get("lines") or [] if str(ln).strip()]


def image_page_count(book: dict) -> int:
    pages = book.get("pages")
    if pages:
        return len(pages)
    return len(flatten_lines(book))


def distribute_lines_evenly(lines: list[str], page_count: int) -> list[list[str]]:
    """把 M 句均匀分到 N 个插图页（同页多句共享一张图）。"""
    if page_count <= 0 or not lines:
        return []
    if page_count >= len(lines):
        return [[ln] for ln in lines] + [[] for _ in range(page_count - len(lines))]
    groups: list[list[str]] = [[] for _ in range(page_count)]
    for i, ln in enumerate(lines):
        groups[i % page_count].append(ln)
    # 按阅读顺序重排：轮询分配会导致 1,4,7 / 2,5,8，改为连续块
    groups = []
    n = len(lines)
    base, rem = divmod(n, page_count)
    idx = 0
    for pi in range(page_count):
        take = base + (1 if pi < rem else 0)
        groups.append(lines[idx : idx + take])
        idx += take
    return groups


def distribute_lines_pairs(lines: list[str], lines_per_page: int = 2) -> list[list[str]]:
    if lines_per_page < 1:
        raise ValueError("lines_per_page must be >= 1")
    groups: list[list[str]] = []
    for i in range(0, len(lines), lines_per_page):
        groups.append(lines[i : i + lines_per_page])
    return groups


def build_pages_field(
    lines: list[str],
    book_id: str,
    *,
    groups: list[list[str]],
) -> list[dict]:
    pages: list[dict] = []
    for i, chunk in enumerate(groups, start=1):
        chunk = [ln for ln in chunk if ln]
        if not chunk:
            continue
        pages.append(
            {
                "lines": chunk,
                "image": f"{book_id}/p{i:02d}.jpg",
            }
        )
    return pages


def apply_page_groups_to_book(
    book: dict,
    groups: list[list[str]],
) -> dict:
    """写入 pages[]，保留 lines[] 为扁平副本供兼容。"""
    lines = [ln for g in groups for ln in g if ln]
    bid = book["id"]
    book = dict(book)
    book["lines"] = lines
    book["pages"] = build_pages_field(lines, bid, groups=groups)
    return book
