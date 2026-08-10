#!/usr/bin/env python3
"""Shared helpers: one bilingual clip per paragraph pair (no sentence splitting)."""

from __future__ import annotations

import re

from chapters import get_chapter  # noqa: E402

_WATERMARK_RE = re.compile(
    r"(?:更多资料分享[^。]*?LearnWi\s*thMe\d*"
    r"|，?\s*微博[：:][^。]*?遇见更好的你"
    r"|LearnWithMe\d*[^。]*?微博[^。]*)",
    re.I,
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def clean_zh(text: str) -> str:
    out = _WATERMARK_RE.sub("", text or "")
    out = re.sub(r"^[，,\s]+", "", out)
    return normalize_text(out)


def fix_en_pdf_artifacts(text: str) -> str:
    out = normalize_text(text)
    if re.search(r'There\'s an owl\s*$', out, re.I):
        out = re.sub(r'There\'s an owl\s*$', "There's an owl—", out, flags=re.I)
    out = re.sub(r"\bpate boy\b", "pale boy", out, flags=re.I)
    out = re.sub(r"\bline 0' Muggles\b", "line o' Muggles", out, flags=re.I)
    out = re.sub(
        r"You saw what everyone in the Leaky Cauldron was like when they saw yeh",
        "You saw him in the Leaky Cauldron",
        out,
        flags=re.I,
    )
    out = re.sub(r"give it a wave", "give it away", out, flags=re.I)
    return out


def _coalesce_orphan_en_pairs(
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Merge EN-only runs (PDF watermark between EN and ZH) with the next ZH."""
    out: list[tuple[str, str]] = []
    buf: list[str] = []
    for en, zh in pairs:
        en = fix_en_pdf_artifacts(en)
        zh = clean_zh(zh)
        if en and not zh:
            buf.append(en)
            continue
        if zh:
            chunk = buf + ([en] if en else [])
            if chunk:
                out.append((normalize_text(" ".join(chunk)), zh))
                buf = []
            elif en:
                out.append((en, zh))
            else:
                out.append(("", zh))
            continue
        if en:
            out.append((en, zh))
    for en in buf:
        out.append((normalize_text(en), ""))
    return out


def _merge_split_paragraph_pairs(
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Merge EN lines split across PDF page breaks (ZH only on the tail)."""
    merged: list[tuple[str, str]] = []
    i = 0
    while i < len(pairs):
        en, zh = pairs[i]
        en = fix_en_pdf_artifacts(en)
        zh = clean_zh(zh)
        if not zh and i + 1 < len(pairs):
            en2, zh2 = pairs[i + 1]
            en2 = fix_en_pdf_artifacts(en2)
            zh2 = clean_zh(zh2)
            if zh2:
                merged.append((normalize_text(f"{en} {en2}"), zh2))
                i += 2
                continue
        merged.append((en, zh))
        i += 1
    return merged


def build_chapter_from_pairs(
    pairs: list[tuple[str, str]],
    *,
    book_id: str,
    chapter: int,
    source: str,
    zh_variant: str = "zh-cn",
) -> dict:
    meta = get_chapter(book_id, chapter)
    title_en = meta["title_en"]
    title_zh = meta["title_zh"]

    heading_en = f"Chapter {chapter} · {title_en}"
    heading_zh = f"第{chapter}章 · {title_zh}"

    body_pairs: list[tuple[str, str]] = []
    for en, zh in _merge_split_paragraph_pairs(_coalesce_orphan_en_pairs(pairs)):
        if not en and not zh:
            continue
        if en.upper() == title_en.upper():
            heading_zh = zh or heading_zh
            continue
        if re.match(r"^CHAPTER\b", en, re.I):
            continue
        if re.match(r"^第\s*\d+\s*章", zh) and len(zh) < 32:
            heading_zh = zh
            continue
        body_pairs.append((en, zh))

    bilingual_clips: list[dict] = [{"en": heading_en, "zh": heading_zh, "kind": "heading"}]
    body_en: list[str] = []
    body_zh: list[str] = []

    for en, zh in body_pairs:
        if not en:
            continue
        bilingual_clips.append({"en": en, "zh": zh})
        body_en.append(en)
        body_zh.append(zh)

    sentences = [heading_en, *body_en]
    zh_sentences = [heading_zh, *body_zh]
    kinds = ["heading", *(["body"] * len(body_en))]

    return {
        "chapter": chapter,
        "title": title_en,
        "title_zh": title_zh,
        "heading_en": heading_en,
        "heading_zh": heading_zh,
        "source": source,
        "zh_variant": zh_variant,
        "granularity": "paragraph",
        "paragraph_pairs": len(body_pairs),
        "sentence_count": len(sentences),
        "body_sentence_count": len(body_en),
        "sentences": sentences,
        "zh_sentences": zh_sentences,
        "kinds": kinds,
        "bilingual_clips": bilingual_clips,
    }
