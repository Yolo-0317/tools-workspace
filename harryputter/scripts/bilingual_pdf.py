#!/usr/bin/env python3
"""Bilingual PDF (hp01): extract EN/ZH paragraph pairs — one clip per pair."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from bilingual_common import (  # noqa: E402
    _coalesce_orphan_en_pairs,
    build_chapter_from_pairs,
    normalize_text,
)
from chapters import bilingual_pdf_path, get_chapter, load_book  # noqa: E402

# 1-indexed PDF page where each chapter banner appears (中英对照版)
BOOK_PDF_CHAPTER_START_PAGES: dict[str, list[int]] = {
    "hp01": [
        2, 16, 27, 41, 55, 80, 104, 121, 131, 150, 165, 178, 197, 209, 222, 240, 266,
    ],
    "hp02": [
        2, 11, 22, 38, 58, 77, 92, 109, 126, 145, 164, 185, 205, 226, 240, 257, 278, 298,
    ],
}

_CHAPTER_START_RE = re.compile(r"^CHAPTER\s", re.I)
_CHAPTER_ZH_RE = re.compile(r"^第\s*\d+\s*章")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_EN_CHAPTER_ORDINALS: dict[int, str] = {
    1: "ONE",
    2: "TWO",
    3: "THREE",
    4: "FOUR",
    5: "FIVE",
    6: "SIX",
    7: "SEVEN",
    8: "EIGHT",
    9: "NINE",
    10: "TEN",
    11: "ELEVEN",
    12: "TWELVE",
    13: "THIRTEEN",
    14: "FOURTEEN",
    15: "FIFTEEN",
    16: "SIXTEEN",
    17: "SEVENTEEN",
    18: "EIGHTEEN",
}


def _cjk_count(text: str) -> int:
    return len(_CJK_RE.findall(text))


def _latin_count(text: str) -> int:
    return sum(1 for c in text if c.isascii() and c.isalpha())


def _line_lang(line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    cjk, latin = _cjk_count(line), _latin_count(line)
    if cjk > 0 and latin > 6:
        return "mixed"
    if cjk >= max(latin, 1):
        return "zh"
    if latin > 0:
        return "en"
    return None


def _split_mixed_line(line: str) -> tuple[str, str]:
    for i, c in enumerate(line):
        if "\u4e00" <= c <= "\u9fff":
            j = i
            while j > 0 and line[j - 1] in " \t\"'「":
                j -= 1
            return normalize_text(line[:j]), normalize_text(line[j:])
    return normalize_text(line), ""


def _is_chapter_banner(line: str, chapter: int) -> bool:
    s = line.strip()
    ordinal = _EN_CHAPTER_ORDINALS.get(chapter, "").upper()
    if ordinal and re.match(rf"^CHAPTER\s+{ordinal}\b", s, re.I):
        return True
    if re.match(rf"^第\s*{chapter}\s*章", s):
        return True
    return False


def _norm_title_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _is_chapter_title_line(s: str, *, book_id: str | None, chapter: int | None) -> bool:
    if not chapter or not book_id:
        return False
    try:
        title_en = get_chapter(book_id, chapter).get("title_en", "")
    except KeyError:
        return False
    if not title_en:
        return False
    return _norm_title_key(s) == _norm_title_key(title_en)


def _is_skip_line(
    line: str, *, book_id: str | None = None, chapter: int | None = None
) -> bool:
    s = line.strip()
    if not s:
        return True
    if _CHAPTER_START_RE.match(s):
        return True
    if _CHAPTER_ZH_RE.match(s) and len(s) < 40:
        return True
    if _is_chapter_title_line(s, book_id=book_id, chapter=chapter):
        return True
    if re.match(r"^Harry Potter and the", s, re.I):
        return True
    if re.match(r"^HARRY POTTER", s, re.I):
        return True
    if re.match(r"^AND THE ", s, re.I) and _cjk_count(s) == 0 and len(s) < 48:
        return True
    if book_id:
        title_zh = load_book(book_id).get("book_title_zh", "")
        if title_zh and s.replace(" ", "") == title_zh.replace(" ", ""):
            return True
        if title_zh and s in title_zh and len(s) <= len(title_zh) + 4:
            return True
    if re.match(r"^哈利·波特", s) and len(s) < 24:
        return True
    if re.search(r"更多资料分享|LearnWi\s*thMe|微博[：:].*遇见更好的你", s, re.I):
        return True
    if (
        s.isupper()
        and _cjk_count(s) == 0
        and len(s) < 96
        and not re.search(r"[.!?]", s)
    ):
        return True
    return False


def chapter_start_pages(book_id: str) -> list[int]:
    pages = BOOK_PDF_CHAPTER_START_PAGES.get(book_id)
    if not pages:
        raise ValueError(f"bilingual PDF not mapped for {book_id}")
    return pages


def _chapter_page_range(book_id: str, chapter: int, page_count: int) -> tuple[int, int]:
    starts = chapter_start_pages(book_id)
    if chapter < 1 or chapter > len(starts):
        raise ValueError(f"chapter {chapter} out of range for {book_id}")
    start = starts[chapter - 1] - 1
    if chapter < len(starts):
        end = starts[chapter] - 2
    else:
        end = page_count - 1
    return start, end


def _lines_to_segments(lines: list[tuple[str, str]]) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    for lang, text in lines:
        if segments and segments[-1][0] == lang:
            segments[-1] = (lang, f"{segments[-1][1]} {text}")
        else:
            segments.append((lang, text))
    return segments


def _segments_to_pairs(segments: list[tuple[str, str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(segments):
        lang, text = segments[i]
        if lang == "en" and i + 1 < len(segments) and segments[i + 1][0] == "zh":
            pairs.append((text, segments[i + 1][1]))
            i += 2
        elif lang == "zh" and i + 1 < len(segments) and segments[i + 1][0] == "en":
            pairs.append((segments[i + 1][1], text))
            i += 2
        elif lang == "en":
            pairs.append((text, ""))
            i += 1
        else:
            pairs.append(("", text))
            i += 1
    return [(en, zh) for en, zh in pairs if en]


def _collect_lines(
    page_text: str,
    *,
    book_id: str | None,
    chapter: int | None = None,
    mode: str = "full",
) -> tuple[list[tuple[str, str]], bool]:
    """mode: full | until_next_chapter | from_chapter_banner"""
    lines: list[tuple[str, str]] = []
    started = mode != "from_chapter_banner"
    for raw in page_text.split("\n"):
        raw = raw.strip()
        if mode == "until_next_chapter" and chapter and _is_chapter_banner(raw, chapter + 1):
            return lines, True
        if mode == "from_chapter_banner" and chapter:
            if _is_chapter_banner(raw, chapter):
                started = True
                continue
            if not started:
                continue
        if _is_skip_line(raw, book_id=book_id, chapter=chapter):
            continue
        lang = _line_lang(raw)
        if lang == "mixed":
            en, zh = _split_mixed_line(raw)
            if en:
                lines.append(("en", en))
            if zh:
                lines.append(("zh", zh))
        elif lang:
            lines.append((lang, normalize_text(raw)))
    return lines, False


def extract_en_zh_pairs_from_pages(
    page_texts: list[str],
    *,
    book_id: str | None = None,
    chapter: int | None = None,
    page_modes: list[str] | None = None,
) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for i, page_text in enumerate(page_texts):
        mode = (page_modes[i] if page_modes and i < len(page_modes) else "full")
        chunk, stop = _collect_lines(
            page_text, book_id=book_id, chapter=chapter, mode=mode
        )
        lines.extend(chunk)
        if stop:
            break
    return _coalesce_orphan_en_pairs(
        _segments_to_pairs(_lines_to_segments(lines))
    )


def extract_chapter(pdf_path: Path, book_id: str, chapter: int) -> dict:
    import fitz

    doc = fitz.open(pdf_path)
    start, end = _chapter_page_range(book_id, chapter, doc.page_count)
    starts = chapter_start_pages(book_id)
    start_pi = starts[chapter - 1] - 1
    page_texts = [doc[i].get_text() for i in range(start_pi, end + 1)]
    page_modes = ["from_chapter_banner"] + ["full"] * max(0, len(page_texts) - 1)
    if chapter < len(starts):
        next_pi = starts[chapter] - 1
        if next_pi > end:
            page_texts.append(doc[next_pi].get_text())
            page_modes.append("until_next_chapter")
        else:
            page_modes[-1] = "until_next_chapter"

    pairs = extract_en_zh_pairs_from_pages(
        page_texts, book_id=book_id, chapter=chapter, page_modes=page_modes
    )
    if not pairs:
        raise ValueError(f"No bilingual paragraph pairs in {pdf_path} ch{chapter}")
    return build_chapter_from_pairs(
        pairs,
        book_id=book_id,
        chapter=chapter,
        source="bilingual_pdf",
        zh_variant="zh-cn",
    )


def default_pdf(book_id: str) -> Path:
    return bilingual_pdf_path(book_id)
