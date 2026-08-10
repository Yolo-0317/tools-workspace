"""Quark media inventory index (pre-scanned mp3 list per catalog series)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from server.playback_memory import episode_sort_key

log = logging.getLogger(__name__)

_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "quark_media_index.json"
_DISFAVOR = (
    "预告",
    "片花",
    "铃声",
    "采访",
    "歌单",
    "mv",
    "bgm",
    "试播",
    "片头",
    "trailer",
    "发刊词",
    "奖励音频",
    "经验分享",
)
_EPISODE_RE = re.compile(
    r"(?:第\s*([0-9一二三四五六七八九十百]+)\s*[集季]|"
    r"[Ss](\d+)[Ee](\d+)|"
    r"[Ee](\d+)|"
    r"^(\d{1,3})[\._\-【\[])",
    re.I,
)


@dataclass(frozen=True)
class IndexedFile:
    fid: str
    filename: str
    size: int
    catalog_key: str
    sort_key: tuple
    audio_map: str | None = None

    @classmethod
    def from_row(cls, catalog_key: str, row: dict[str, Any]) -> IndexedFile:
        name = str(row.get("filename") or "")
        # Always derive from filename so stale index sort_key (e.g. all type-9)
        # cannot pick the lexicographically last episode.
        audio_map = row.get("audio_map")
        return cls(
            fid=str(row.get("fid") or ""),
            filename=name,
            size=int(row.get("size") or 0),
            catalog_key=catalog_key,
            sort_key=episode_sort_key(name),
            audio_map=str(audio_map) if audio_map else None,
        )


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    if not _INDEX_PATH.is_file():
        return {}
    try:
        data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def index_available() -> bool:
    raw = _load_raw()
    return bool(raw.get("series"))


def index_built_at() -> str:
    return str(_load_raw().get("built_at") or "")


def series_keys() -> list[str]:
    series = _load_raw().get("series") or {}
    return sorted(series.keys()) if isinstance(series, dict) else []


def get_series_files(catalog_key: str) -> list[IndexedFile]:
    series = (_load_raw().get("series") or {}).get(catalog_key) or {}
    rows = series.get("files") or []
    out: list[IndexedFile] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = IndexedFile.from_row(catalog_key, row)
        if item.fid:
            out.append(item)
    out.sort(key=lambda f: f.sort_key)
    return out


def _disfavored(name: str) -> bool:
    lower = name.lower()
    return any(part in lower for part in _DISFAVOR)


def _keyword_bonus(keyword: str, filename: str) -> int:
    key = (keyword or "").strip().lower()
    name = filename.lower()
    if not key:
        return 0
    score = 0
    if key in name:
        score += 100
    for token in re.split(r"[\s_\-]+", key):
        if len(token) >= 2 and token in name:
            score += 15
    return score


def _episode_hint_bonus(episode: str | None, filename: str) -> int:
    """Score how well filename matches an episode hint (数字 / 中文序号).

    Do not use bare substring of short CN digits (e.g. 「一」 in 「第一部完结」).
    """
    if not episode:
        return 0
    ep = str(episode).strip()
    name = (filename or "").lower()
    from server.playback_memory import _cn_number

    n: int | None
    if ep.isdigit():
        n = int(ep)
    else:
        n = _cn_number(ep)

    if n is not None:
        compact = name.replace(" ", "")
        padded2 = f"{n:02d}"
        padded4 = f"{n:04d}"
        if f"第{n}集" in name or f"第{padded2}集" in name or f"第{ep}集" in name:
            return 50
        if f"s{padded2}e" in compact or f"e{padded2}" in compact:
            return 40
        # 0001-Title… / 01-Title…
        if re.match(rf"^0*{n}[\._\-【\[]", name):
            return 45
        # Title01 / 冰雪奇缘01 / 冰雪奇缘二01 — episode digits after series title
        if re.search(rf"(?:奇缘|缘)(?:[一二三四五六七八九十]+)?{padded2}(?:\D|$)", name):
            return 35
        if re.search(rf"(?:^|[^\d]){padded2}(?:\s|$|[^\d])", name) and name.startswith(
            ("0", padded2)
        ):
            return 30
        return 0

    # Longer non-numeric hints only (avoid single-char false positives)
    if len(ep) >= 2 and ep.lower() in name:
        return 25
    return 0


def pick_best_file(
    catalog_key: str,
    *,
    keyword: str = "",
    episode: str | None = None,
    prefer_audio: bool = True,
    user_text: str = "",
) -> IndexedFile | None:
    files = get_series_files(catalog_key)
    if not files:
        return None

    # Curated series map wins over keyword heuristics (e.g. frozen ep1).
    try:
        from server.series_maps import resolve_mapped_episode

        mapped = resolve_mapped_episode(
            catalog_key,
            keyword=keyword,
            user_text=user_text,
            episode=episode,
        )
    except Exception:
        mapped = None
    if mapped is not None:
        by_fid = {f.fid: f for f in files}
        for fid in mapped.fids:
            hit = by_fid.get(fid)
            if hit is not None:
                if mapped.audio_map and hit.audio_map != mapped.audio_map:
                    return IndexedFile(
                        fid=hit.fid,
                        filename=hit.filename,
                        size=hit.size,
                        catalog_key=hit.catalog_key,
                        sort_key=hit.sort_key,
                        audio_map=mapped.audio_map,
                    )
                return hit
        for f in files:
            if f.filename == mapped.filename:
                if mapped.audio_map and f.audio_map != mapped.audio_map:
                    return IndexedFile(
                        fid=f.fid,
                        filename=f.filename,
                        size=f.size,
                        catalog_key=f.catalog_key,
                        sort_key=f.sort_key,
                        audio_map=mapped.audio_map,
                    )
                return f

    pool = [f for f in files if not _disfavored(f.filename)]
    if not pool:
        pool = files

    # Higher bonus first; on ties prefer earliest episode (ascending sort_key).
    # Never reverse=True on (bonus, sort_key) — that picked the *last* episode
    # when every file shared the same keyword bonus.
    if episode:
        scored = sorted(
            pool,
            key=lambda f: (-_episode_hint_bonus(episode, f.filename), f.sort_key),
        )
        best = scored[0]
        if _episode_hint_bonus(episode, best.filename) > 0:
            return best

    if keyword:
        scored = sorted(
            pool,
            key=lambda f: (-_keyword_bonus(keyword, f.filename), f.sort_key),
        )
        if scored and _keyword_bonus(keyword, scored[0].filename) > 0:
            return scored[0]

    return pool[0]


def find_next_file(
    catalog_key: str,
    current_fid: str,
    current_filename: str | None = None,
) -> IndexedFile | None:
    files = get_series_files(catalog_key)
    if not files:
        return None
    current = next((f for f in files if f.fid == current_fid), None)
    if current is None and current_filename:
        current = next((f for f in files if f.filename == current_filename), None)
    if current is None and current_filename:
        # Synthetic anchor from filename only (resolved fid may not be in index).
        m0 = re.match(r"^(\d{1,4})-", current_filename)
        if m0:
            cur_n = int(m0.group(1))
            best: IndexedFile | None = None
            best_n = None
            for item in files:
                if _disfavored(item.filename):
                    continue
                m2 = re.match(r"^(\d{1,4})-", item.filename)
                if not m2:
                    continue
                n = int(m2.group(1))
                if n <= cur_n:
                    continue
                if best_n is None or n < best_n:
                    best_n = n
                    best = item
            return best
    if current is None:
        return None

    # Prefer next higher leading NNNN- index (handles duplicate fids / sort ties).
    m = re.match(r"^(\d{1,4})-", current.filename)
    if m:
        cur_n = int(m.group(1))
        best: IndexedFile | None = None
        best_n = None
        for item in files:
            if _disfavored(item.filename):
                continue
            m2 = re.match(r"^(\d{1,4})-", item.filename)
            if not m2:
                continue
            n = int(m2.group(1))
            if n <= cur_n:
                continue
            if best_n is None or n < best_n:
                best_n = n
                best = item
        if best is not None:
            return best

    for item in files:
        if item.sort_key > current.sort_key and item.fid != current_fid:
            if not _disfavored(item.filename):
                return item
    return None


def find_file_by_fid(fid: str) -> IndexedFile | None:
    if not fid:
        return None
    for key in series_keys():
        for item in get_series_files(key):
            if item.fid == fid:
                return item
    return None


def resolve_catalog_key_for_record(
    *,
    catalog_key: str | None,
    filename: str,
    query: str,
) -> str | None:
    if catalog_key and get_series_files(catalog_key):
        return catalog_key
    from server.content_catalog import match_content

    entry = match_content(f"{query} {filename}")
    if entry and get_series_files(entry.key):
        return entry.key
    return catalog_key if catalog_key and get_series_files(catalog_key) else None


def list_series_summary(limit: int = 12) -> list[str]:
    raw = _load_raw().get("series") or {}
    lines: list[str] = []
    for key in series_keys()[:limit]:
        item = raw.get(key) or {}
        title = str(item.get("title") or key)
        count = int(item.get("file_count") or 0)
        if count:
            lines.append(f"{title}（{count}个音频）")
        else:
            lines.append(title)
    return lines


def context_for_llm() -> str:
    if not index_available():
        return "（网盘库存索引未生成，运行 scripts/build_quark_media_index.py）"
    raw = _load_raw()
    total = sum(
        int((s or {}).get("file_count") or 0)
        for s in (raw.get("series") or {}).values()
    )
    titles = "、".join(list_series_summary(8))
    return f"库存索引（{raw.get('built_at', '?')}）：共 {total} 个音频。可播系列：{titles}"


def invalidate_cache() -> None:
    _load_raw.cache_clear()
