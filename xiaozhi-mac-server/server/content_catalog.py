"""Voice/content aliases -> Quark search hints (curated paths in cloud drive)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "quark_content_aliases.json"


@dataclass(frozen=True)
class ContentEntry:
    key: str
    title: str
    path_hint: str
    search_queries: tuple[str, ...]
    filename_boost: tuple[str, ...]
    media_hint: str
    episode: str | None = None


def _norm_alias(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", (text or "").strip().lower())


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, dict]:
    if not _CATALOG_PATH.is_file():
        return {}
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def _alias_index() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, item in _load_raw().items():
        aliases = [key, *(item.get("aliases") or [])]
        for alias in aliases:
            norm = _norm_alias(str(alias))
            if norm:
                rows.append((norm, key))
    rows.sort(key=lambda row: len(row[0]), reverse=True)
    return rows


_EPISODE_RE = re.compile(
    r"(?:第\s*([0-9一二三四五六七八九十百]+)\s*[集季]|"
    r"season\s*([0-9]+)|"
    r"s([0-9]+)|"
    r"ep(?:isode)?\s*([0-9]+))",
    re.I,
)


def _extract_episode(text: str) -> str | None:
    m = _EPISODE_RE.search(text or "")
    if not m:
        return None
    for group in m.groups():
        if group:
            return str(group).strip()
    return None


def match_content(text: str) -> ContentEntry | None:
    raw = (text or "").strip()
    if not raw:
        return None
    norm_text = _norm_alias(raw)
    for alias_norm, key in _alias_index():
        # Alias must appear in the utterance. Do NOT allow short queries to
        # match longer aliases (e.g. 「冰雪奇缘」 must not hit 「冰雪奇缘英文版」).
        if alias_norm not in norm_text:
            continue
        item = _load_raw().get(key) or {}
        queries = item.get("search_queries") or [item.get("title") or key]
        boost = item.get("filename_boost") or []
        episode = _extract_episode(raw)
        search_queries = list(dict.fromkeys(str(q).strip() for q in queries if str(q).strip()))
        if episode:
            episode_queries = []
            for q in search_queries:
                episode_queries.extend([f"{q} 第{episode}集", f"{q} {episode}"])
            search_queries = list(dict.fromkeys([*episode_queries, *search_queries]))
        return ContentEntry(
            key=key,
            title=str(item.get("title") or key),
            path_hint=str(item.get("path_hint") or ""),
            search_queries=tuple(search_queries),
            filename_boost=tuple(str(x) for x in boost if str(x).strip()),
            media_hint=str(item.get("media_hint") or "story_audio"),
            episode=episode,
        )
    return None


def resolve_play_request(keyword: str, *, user_text: str = "", media_hint: str = "any") -> tuple[str, str, ContentEntry | None]:
    """Return (search_keyword, media_hint, catalog_entry)."""
    combined = " ".join(part for part in (keyword, user_text) if part).strip()
    entry = match_content(combined) or match_content(keyword)
    if entry is None:
        return keyword.strip(), media_hint, None
    hint = entry.media_hint if media_hint in {"", "any"} else media_hint
    search_key = entry.search_queries[0] if entry.search_queries else entry.title
    return search_key, hint, entry


def catalog_search_keys(keyword: str, *, user_text: str = "", media_hint: str = "any") -> list[str]:
    _, _, entry = resolve_play_request(keyword, user_text=user_text, media_hint=media_hint)
    if entry is None:
        return []
    return list(entry.search_queries)


def catalog_filename_bonus(entry: ContentEntry | None, filename: str) -> int:
    if entry is None:
        return 0
    name = filename.lower()
    score = 0
    for token in entry.filename_boost:
        if token.lower() in name:
            score += 25
    if entry.path_hint:
        for part in re.split(r"[/\\]", entry.path_hint):
            part = part.strip()
            if len(part) >= 4 and part.lower() in name:
                score += 15
    if entry.episode:
        ep = entry.episode.lower()
        # Prefer explicit 第N集 / leading index; avoid bare 「一」 matching 「第一部」
        if f"第{ep}集" in name or f"s{ep}" in name:
            score += 30
        elif len(ep) >= 2 and ep in name:
            score += 30
        else:
            from server.playback_memory import _cn_number

            n = int(ep) if ep.isdigit() else _cn_number(ep)
            if n is not None and re.match(rf"^0*{n}[\._\-【\[]", name):
                score += 30
    return score


# Child-friendly order when suggesting alternatives after a miss.
_SUGGEST_PREFERRED_KEYS = (
    "journey_west",
    "frozen",
    "frozen_movie",
    "barbapapa",
    "popo_detective",
    "peppa",
    "harry_potter",
    "steve_maggie",
    "bluey",
    "penelope",
    "tong_laoshi",
)

# Spoken suggestion overrides (avoid Chinese nicknames kids shouldn't hear).
_SUGGEST_NAME_OVERRIDE = {
    "steve_maggie": "wow english",
}


def _short_suggestion_name(item: dict, key: str) -> str:
    """Prefer a short Chinese alias for TTS; fall back to title snippet."""
    override = _SUGGEST_NAME_OVERRIDE.get(key)
    if override:
        return override
    for alias in item.get("aliases") or []:
        alias_s = str(alias).strip()
        if re.search(r"[\u4e00-\u9fff]", alias_s) and 2 <= len(alias_s) <= 10:
            return alias_s
    title = str(item.get("title") or key).strip()
    if " / " in title:
        title = title.split(" / ", 1)[0].strip()
    zh = re.search(r"[\u4e00-\u9fffA-Za-z0-9]{2,16}", title)
    return (zh.group(0) if zh else title)[:16]


def catalog_play_suggestions(limit: int = 3) -> list[str]:
    """Short names from configured catalog (prefer series that exist in local index)."""
    from server.media_index import get_series_files, index_available

    raw = _load_raw()
    if not raw:
        return []

    names: list[str] = []
    seen: set[str] = set()

    def _add(catalog_key: str) -> None:
        item = raw.get(catalog_key)
        if not isinstance(item, dict):
            return
        if index_available() and not get_series_files(catalog_key):
            return
        name = _short_suggestion_name(item, catalog_key)
        if not name or name in seen:
            return
        seen.add(name)
        names.append(name)

    for key in _SUGGEST_PREFERRED_KEYS:
        _add(key)
        if len(names) >= limit:
            return names
    for key in raw:
        _add(key)
        if len(names) >= limit:
            break
    return names


def speak_hint_not_in_catalog() -> str:
    suggestions = catalog_play_suggestions(3)
    if suggestions:
        return f"这个故事我这边还没有，换{'、'.join(suggestions)}好不好？"
    return "这个故事我这边还没有，换一个已有的故事名字试试好不好？"
