"""Chapter catalog and samples path helpers (按「部」hp01…hp07)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "book01_chapters.json"


def load_book(book_id: str = "hp01") -> dict:
    if book_id != "hp01":
        raise ValueError(f"Unknown book_id: {book_id}")
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def get_chapter(book_id: str, chapter_id: int) -> dict:
    book = load_book(book_id)
    for ch in book["chapters"]:
        if ch["id"] == chapter_id:
            return ch
    raise KeyError(f"Chapter {chapter_id} not in {book_id}")


def chapter_pad(chapter_id: int) -> str:
    return f"{chapter_id:02d}"


def book_samples_dir(book_id: str = "hp01") -> Path:
    return ROOT / "samples" / book_id


def en_epub_path(book_id: str = "hp01") -> Path:
    return ROOT / "samples" / "epub" / "en" / f"{book_id}.epub"


def zh_epub_path(book_id: str = "hp01") -> Path:
    # 中文珍藏版七册合一；部内章节映射见 book01_chapters.json zh_file
    return ROOT / "samples" / "epub" / "zh" / "collection.epub"


def audio_path(book_id: str, chapter_id: int) -> Path:
    return book_samples_dir(book_id) / f"chapter{chapter_pad(chapter_id)}.mp3"


def audio_rel(book_id: str, chapter_id: int) -> str:
    return f"samples/{book_id}/chapter{chapter_pad(chapter_id)}.mp3"
