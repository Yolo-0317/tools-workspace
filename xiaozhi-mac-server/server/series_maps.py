"""Curated per-series episode maps (canonical first episode, seasons).

Prefer these over heuristic keyword ranking when a map file exists under
``data/quark_series_maps/<catalog_key>.json``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from server.playback_memory import _cn_number

log = logging.getLogger(__name__)

_MAPS_DIR = Path(__file__).resolve().parent.parent / "data" / "quark_series_maps"

_SEASON2_RE = re.compile(
    r"(第二部|二部|续集|冰雪奇缘二|frozen\s*2|season\s*2)",
    re.I,
)
_SEASON1_RE = re.compile(r"(第一部|一部|frozen\s*1|season\s*1)", re.I)


@dataclass(frozen=True)
class MappedEpisode:
    catalog_key: str
    global_n: int
    season: int
    season_ep: int | None
    filename: str
    title: str
    fid: str
    fids: tuple[str, ...]
    audio_map: str | None = None

@lru_cache(maxsize=32)
def _load_map(catalog_key: str) -> dict[str, Any] | None:
    path = _MAPS_DIR / f"{catalog_key}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("series map load failed %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def clear_series_map_cache() -> None:
    _load_map.cache_clear()


def has_series_map(catalog_key: str) -> bool:
    return _load_map(catalog_key) is not None


def _episode_int(episode: str | None) -> int | None:
    if not episode:
        return None
    ep = str(episode).strip()
    if ep.isdigit():
        return int(ep)
    return _cn_number(ep)


def _infer_season(text: str, *, episode: str | None = None) -> int | None:
    blob = " ".join(part for part in (text, episode or "") if part)
    if _SEASON2_RE.search(blob):
        return 2
    if _SEASON1_RE.search(blob):
        return 1
    return None


def _row_to_mapped(catalog_key: str, row: dict[str, Any]) -> MappedEpisode | None:
    fid = str(row.get("fid") or (row.get("fids") or [None])[0] or "")
    filename = str(row.get("filename") or "")
    if not fid or not filename:
        return None
    fids = tuple(str(x) for x in (row.get("fids") or [fid]) if x)
    audio_map = row.get("audio_map")
    return MappedEpisode(
        catalog_key=catalog_key,
        global_n=int(row.get("global_n") or 0),
        season=int(row.get("season") or 1),
        season_ep=int(row["season_ep"]) if row.get("season_ep") is not None else None,
        filename=filename,
        title=str(row.get("title") or filename),
        fid=fid,
        fids=fids or (fid,),
        audio_map=str(audio_map) if audio_map else None,
    )


def resolve_mapped_episode(
    catalog_key: str,
    *,
    keyword: str = "",
    user_text: str = "",
    episode: str | None = None,
) -> MappedEpisode | None:
    """Resolve a curated episode. No map / no match → None (caller falls back)."""
    data = _load_map(catalog_key)
    if not data:
        return None

    combined = " ".join(part for part in (keyword, user_text) if part).strip()
    season = _infer_season(combined, episode=episode)
    ep_n = _episode_int(episode)
    episodes = [e for e in (data.get("episodes") or []) if isinstance(e, dict)]

    # Bare title / 中文版 with no episode → canonical first file
    if ep_n is None and season is None:
        start = data.get("default_start")
        if isinstance(start, dict):
            mapped = _row_to_mapped(catalog_key, start)
            if mapped:
                log.info(
                    "Series map default: %s -> %s",
                    catalog_key,
                    mapped.filename,
                )
                return mapped
        return None

    season = season or 1
    target_ep = ep_n if ep_n is not None else 1

    for row in episodes:
        if int(row.get("season") or 0) != season:
            continue
        if row.get("season_ep") is not None and int(row["season_ep"]) == target_ep:
            mapped = _row_to_mapped(catalog_key, row)
            if mapped:
                log.info(
                    "Series map hit: %s S%sE%s -> %s",
                    catalog_key,
                    season,
                    target_ep,
                    mapped.filename,
                )
                return mapped

    # Fallback: treat N as global leading index (0001 → 1)
    if ep_n is not None:
        for row in episodes:
            if int(row.get("global_n") or 0) == ep_n:
                mapped = _row_to_mapped(catalog_key, row)
                if mapped:
                    log.info(
                        "Series map global_n=%s -> %s",
                        ep_n,
                        mapped.filename,
                    )
                    return mapped

    return None
