"""Oxford Reading Tree topic catalog (per-page read-along)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from teaching.ort_oxford_owl.catalog import load_catalog

router = APIRouter(prefix="/api/ort", tags=["ort"])


@router.get("/catalog")
async def ort_catalog() -> dict:
    return load_catalog()


@router.get("/books/{book_id}")
async def ort_book(book_id: str) -> dict:
    data = load_catalog()
    for book in data.get("books") or []:
        if book.get("id") == book_id:
            return book
    raise HTTPException(status_code=404, detail="读本未找到")
