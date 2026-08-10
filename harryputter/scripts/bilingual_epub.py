#!/usr/bin/env python3
"""Immersive-Translate bilingual EPUB: one clip per <p> EN/ZH pair (繁→简)."""

from __future__ import annotations

import re
import zipfile
from html import unescape
from pathlib import Path

from bilingual_common import build_chapter_from_pairs  # noqa: E402
from chapters import bilingual_epub_path, get_chapter  # noqa: E402

_ZH_WRAPPER_RE = re.compile(
    r'<span class="notranslate immersive-translate-target-wrapper.*',
    re.S,
)
_ZH_INNER_RE = re.compile(
    r'immersive-translate-target-inner[^>]*>(.*?)</span>',
    re.S,
)
_ABBREV_FIX_RE = re.compile(r"\b([A-Z])\s+([a-z]{1,2}\.)")


def to_simplified(text: str) -> str:
    if not text:
        return text
    try:
        from zhconv import convert

        return convert(text, "zh-cn")
    except ImportError:
        try:
            from opencc import OpenCC

            return OpenCC("t2s").convert(text)
        except ImportError as exc:
            raise ImportError(
                "Install zhconv for Traditional→Simplified: pip install zhconv"
            ) from exc


def chapter_xhtml_files(chapter: int) -> list[str]:
    part = chapter + 1
    return [f"OEBPS/part{part}_split_001.xhtml"]


def _clean_en_html(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return _ABBREV_FIX_RE.sub(r"\1\2", text)


def _clean_zh_html(raw: str) -> str:
    inner = _ZH_INNER_RE.search(raw)
    chunk = inner.group(1) if inner else raw
    text = re.sub(r"<br\s*/?>", " ", chunk, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).replace("\xa0", " ").strip()


def extract_en_zh_pairs(html: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.S):
        wrapper = _ZH_WRAPPER_RE.search(raw)
        if wrapper:
            en_raw = raw[: wrapper.start()]
            zh_raw = raw[wrapper.start() :]
        else:
            en_raw, zh_raw = raw, ""
        en = _clean_en_html(en_raw)
        zh = to_simplified(_clean_zh_html(zh_raw)) if zh_raw else ""
        if en:
            pairs.append((en, zh))
    return pairs


def extract_chapter(epub_path: Path, book_id: str, chapter: int) -> dict:
    pairs: list[tuple[str, str]] = []
    with zipfile.ZipFile(epub_path) as zf:
        for rel in chapter_xhtml_files(chapter):
            if rel not in zf.namelist():
                raise FileNotFoundError(f"{rel} not in {epub_path}")
            html = zf.read(rel).decode("utf-8", errors="replace")
            pairs.extend(extract_en_zh_pairs(html))

    if not pairs:
        raise ValueError(f"No bilingual pairs in chapter {chapter}")

    return build_chapter_from_pairs(
        pairs,
        book_id=book_id,
        chapter=chapter,
        source="bilingual_epub",
        zh_variant="zh-cn",
    )


def default_epub(book_id: str) -> Path:
    return bilingual_epub_path(book_id)
