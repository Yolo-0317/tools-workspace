"""Chapter catalog and samples path helpers (按「部」hp01…hp07)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LIBRARY_PATH = ROOT / "output" / "library.json"
KNOWN_BOOKS = ("hp01", "hp02")


def book_data_path(book_id: str) -> Path:
    if book_id not in KNOWN_BOOKS:
        raise ValueError(f"Unknown book_id: {book_id}")
    return DATA_DIR / f"book{book_id[2:]}_chapters.json"


def load_book(book_id: str = "hp01") -> dict:
    path = book_data_path(book_id)
    if not path.is_file():
        raise ValueError(f"Unknown book_id: {book_id}")
    return json.loads(path.read_text(encoding="utf-8"))


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


def book_output_dir(book_id: str) -> Path:
    return ROOT / "output" / book_id


def en_epub_path(book_id: str = "hp01") -> Path:
    return ROOT / "samples" / "epub" / "en" / f"{book_id}.epub"


def zh_epub_path(book_id: str = "hp01") -> Path:
    return ROOT / "samples" / "epub" / "zh" / "collection.epub"


def bilingual_epub_path(book_id: str = "hp01") -> Path:
    return ROOT / "samples" / "epub" / "bilingual" / f"{book_id}.epub"


def bilingual_pdf_path(book_id: str = "hp01") -> Path:
    return ROOT / "samples" / "pdf" / "bilingual" / f"{book_id}.pdf"


def audio_path(book_id: str, chapter_id: int) -> Path:
    return book_samples_dir(book_id) / f"chapter{chapter_pad(chapter_id)}.mp3"


def audio_rel(book_id: str, chapter_id: int) -> str:
    return f"samples/{book_id}/chapter{chapter_pad(chapter_id)}.mp3"


def sentences_path(book_id: str, chapter_id: int) -> Path:
    pad = chapter_pad(chapter_id)
    return book_output_dir(book_id) / f"ch{pad}_sentences.json"


def zh_extract_path(book_id: str, chapter_id: int) -> Path:
    pad = chapter_pad(chapter_id)
    return book_output_dir(book_id) / f"ch{pad}_zh.json"


def words_cache_path(book_id: str, chapter_id: int) -> Path:
    pad = chapter_pad(chapter_id)
    return book_output_dir(book_id) / f"ch{pad}_words.json"


def manifest_path(book_id: str, chapter_id: int) -> Path:
    pad = chapter_pad(chapter_id)
    return book_output_dir(book_id) / f"ch{pad}.json"


def manifest_rel(book_id: str, chapter_id: int) -> str:
    pad = chapter_pad(chapter_id)
    return f"output/{book_id}/ch{pad}.json"


def catalog_path(book_id: str) -> Path:
    return book_output_dir(book_id) / "catalog.json"


def catalog_rel(book_id: str) -> str:
    return f"output/{book_id}/catalog.json"
