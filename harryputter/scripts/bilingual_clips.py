#!/usr/bin/env python3
"""Load Agent-curated bilingual clips from translation_fixes JSON."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fixes_path(book: str, chapter: int) -> Path:
    return ROOT / "data" / "translation_fixes" / f"{book}_ch{chapter:02d}.json"


def load_fixes(book: str, chapter: int) -> dict | None:
    path = fixes_path(book, chapter)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_bilingual_clips(book: str, chapter: int) -> list[dict] | None:
    fixes = load_fixes(book, chapter)
    if not fixes:
        return None
    clips = fixes.get("bilingual_clips")
    if not clips or not isinstance(clips, list):
        return None
    out: list[dict] = []
    for item in clips:
        en = (item.get("en") or item.get("text") or "").strip()
        if not en:
            continue
        clip: dict = {"en": en, "zh": (item.get("zh") or "").strip()}
        if item.get("kind"):
            clip["kind"] = item["kind"]
        if item.get("comment"):
            clip["comment"] = item["comment"]
        out.append(clip)
    return out if out else None


def clips_for_align(clips: list[dict]) -> tuple[list[str], list[str]]:
    sentences = [c["en"] for c in clips]
    kinds = [c.get("kind") or "body" for c in clips]
    return sentences, kinds


def load_granularity(book: str, chapter: int) -> str:
    fixes = load_fixes(book, chapter)
    if not fixes:
        return "sentence"
    return fixes.get("granularity") or "sentence"
