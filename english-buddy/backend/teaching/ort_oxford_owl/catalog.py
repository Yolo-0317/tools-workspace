"""Build ORT topic catalog (per-page lines + image paths) from books.json."""

from __future__ import annotations

import json
from pathlib import Path

BOOKS_JSON = Path(__file__).resolve().parent / "books.json"
CATALOG_JSON = Path(__file__).resolve().parent / "catalog.json"
ROOT = Path(__file__).resolve().parents[3]
ORT_DIST = ROOT / "frontend" / "dist" / "ort"
ORT_PUBLIC = ROOT / "frontend" / "public" / "ort"


def ort_images_root() -> Path:
    """Prefer built dist; fall back to public/ort during dev."""
    if ORT_DIST.is_dir():
        return ORT_DIST
    return ORT_PUBLIC


def page_image_exists(image_rel: str) -> bool:
    rel = (image_rel or "").strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        return False
    path = ort_images_root() / rel
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def book_images_ready(pages: list[dict]) -> bool:
    if not pages:
        return False
    return all(page_image_exists(str(p.get("image") or "")) for p in pages)


def _pages_for_book(book: dict) -> list[dict]:
    explicit = book.get("pages")
    if explicit:
        out: list[dict] = []
        for i, page in enumerate(explicit, start=1):
            lines = [str(ln).strip() for ln in page.get("lines") or [] if str(ln).strip()]
            if not lines:
                continue
            img = page.get("image") or f"{book['id']}/p{i:02d}.jpg"
            out.append({"index": i, "lines": lines, "image": img})
        return out

    lines = [str(ln).strip() for ln in book.get("lines") or [] if str(ln).strip()]
    pages: list[dict] = []
    for i, line in enumerate(lines, start=1):
        pages.append(
            {
                "index": i,
                "lines": [line],
                "image": f"{book['id']}/p{i:02d}.jpg",
            }
        )
    return pages


def build_catalog(version: int | str) -> dict:
    raw = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
    books_out: list[dict] = []
    for book in raw.get("books") or []:
        bid = book.get("id") or ""
        if not bid:
            continue
        pages = _pages_for_book(book)
        if not pages:
            continue
        books_out.append(
            {
                "id": bid,
                "lesson_id": bid,
                "title": book.get("title") or bid,
                "ort_level": book.get("ort_level") or "",
                "book_band": book.get("book_band") or "",
                "series": book.get("series") or "",
                "oxford_owl_free": bool(book.get("oxford_owl_free")),
                "page_count": len(pages),
                "pages": pages,
            }
        )
    return {
        "version": version,
        "source": raw.get("source") or "Oxford Reading Tree",
        "source_url": raw.get("source_url") or "",
        "note": raw.get("note") or "",
        "image_base": "ort",
        "books": books_out,
    }


def write_catalog(version: int | str) -> Path:
    data = build_catalog(version)
    CATALOG_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return CATALOG_JSON


def enrich_catalog_images(data: dict) -> dict:
    books: list[dict] = []
    illustrated = 0
    for book in data.get("books") or []:
        pages = book.get("pages") or []
        ready = book_images_ready(pages)
        if ready:
            illustrated += 1
        books.append({**book, "images_ready": ready})
    out = dict(data)
    out["books"] = books
    out["illustrated_count"] = illustrated
    out["total_books"] = len(books)
    return out


def load_catalog() -> dict:
    if CATALOG_JSON.is_file():
        data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    else:
        data = build_catalog(0)
    return enrich_catalog_images(data)
