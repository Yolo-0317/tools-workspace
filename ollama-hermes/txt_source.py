"""Load and slice plain-text novel files for Hermes prompts."""

from __future__ import annotations

import re
from pathlib import Path


def read_text_file(path: str | Path, *, encoding: str = "utf-8") -> str:
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Text file not found: {p}")
    return p.read_text(encoding=encoding)


def extract_by_markers(
    text: str,
    *,
    start: str,
    end: str | None = None,
) -> str:
    """Extract substring from *start* marker up to (but not including) *end* marker."""
    i = text.find(start)
    if i < 0:
        raise ValueError(f"Start marker not found: {start!r}")
    if end:
        j = text.find(end, i + len(start))
        if j < 0:
            fragment = text[i:]
        else:
            fragment = text[i:j]
    else:
        fragment = text[i:]
    return fragment.strip()


def extract_chapter(
    text: str,
    chapter_label: str,
    *,
    prefix: str = "正文第",
    suffix: str = "章",
) -> str:
    """Extract one chapter body, e.g. chapter_label='七十' -> 正文第七十章 ..."""
    start = f"{prefix}{chapter_label}{suffix}"
    pattern = re.compile(rf"{re.escape(prefix)}[^章]+{re.escape(suffix)}")
    matches = list(pattern.finditer(text))
    starts = [m.start() for m in matches if m.group(0).startswith(start)]
    if not starts:
        raise ValueError(f"Chapter not found: {start}")
    begin = starts[0]
    after = begin + len(start)
    nxt = pattern.search(text, after)
    end = nxt.start() if nxt else len(text)
    return text[begin:end].strip()


def extract_chapter_range(
    text: str,
    start_chapter: str,
    end_chapter: str | None = None,
    **kwargs: str,
) -> str:
    start = extract_chapter(text, start_chapter, **kwargs)
    if not end_chapter:
        return start
    end_marker = f"{kwargs.get('prefix', '正文第')}{end_chapter}{kwargs.get('suffix', '章')}"
    i = text.find(start)
    j = text.find(end_marker, i + len(start))
    if j < 0:
        return text[i:].strip()
    return text[i:j].strip()


def trim_fragment(fragment: str, *, max_chars: int | None = None) -> str:
    if max_chars is None or len(fragment) <= max_chars:
        return fragment
    head = max_chars // 2
    tail = max_chars - head
    return fragment[:head] + "\n\n……（中段已省略）……\n\n" + fragment[-tail:]
