"""Playback memory: current item, progress, history, next-episode hints."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from server.config import settings
from server.quark_client import QuarkClient, QuarkFile, QuarkStreamSource

log = logging.getLogger(__name__)

_STATE_DIR = Path(__file__).resolve().parent.parent / "data" / "playback_state"

_SXXEXX_RE = re.compile(r"[Ss](\d+)[Ee](\d+)", re.I)
_EXX_RE = re.compile(r"[Ee](\d+)", re.I)
_EPISODE_CN_RE = re.compile(r"第\s*([0-9一二三四五六七八九十百]+)\s*集")
# Quark story packs often use 0001-Title… (4 digits); allow 1–4.
_LEADING_NUM_RE = re.compile(r"^(\d{1,4})[\._\-【\[]")

_CN_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _cn_number(text: str) -> int | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if raw == "十":
        return 10
    if "十" in raw:
        parts = raw.split("十", 1)
        tens = _CN_DIGITS.get(parts[0], 1) if parts[0] else 1
        ones = _CN_DIGITS.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    if len(raw) == 1 and raw in _CN_DIGITS:
        return _CN_DIGITS[raw]
    return None


@dataclass
class PlaybackRecord:
    fid: str
    filename: str
    query: str
    media_hint: str = "story_audio"
    catalog_key: str | None = None
    position_ms: int = 0
    completed: bool = False
    updated_at: float = field(default_factory=time.time)

    def position_s(self) -> float:
        return max(0.0, self.position_ms / 1000.0)

    def short_title(self) -> str:
        name = self.filename.rsplit(".", 1)[0]
        return name if len(name) <= 40 else name[:37] + "..."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlaybackRecord:
        return cls(
            fid=str(data.get("fid") or ""),
            filename=str(data.get("filename") or ""),
            query=str(data.get("query") or ""),
            media_hint=str(data.get("media_hint") or "story_audio"),
            catalog_key=data.get("catalog_key"),
            position_ms=int(data.get("position_ms") or 0),
            completed=bool(data.get("completed")),
            updated_at=float(data.get("updated_at") or time.time()),
        )


def episode_sort_key(filename: str) -> tuple:
    name = filename or ""
    m = _SXXEXX_RE.search(name)
    if m:
        return (0, int(m.group(1)), int(m.group(2)), name.lower())
    m = _EPISODE_CN_RE.search(name)
    if m:
        num = _cn_number(m.group(1))
        if num is not None:
            return (1, num, 0, name.lower())
    m = _EXX_RE.search(name)
    if m:
        return (2, int(m.group(1)), 0, name.lower())
    m = _LEADING_NUM_RE.match(name)
    if m:
        return (3, int(m.group(1)), 0, name.lower())
    return (9, 0, 0, name.lower())


def series_prefix(filename: str) -> str:
    name = filename.rsplit(".", 1)[0]
    m = _SXXEXX_RE.search(name)
    if m:
        return name[: m.start()] + f"S{m.group(1)}E"
    m = _EPISODE_CN_RE.search(name)
    if m:
        return name[: m.start()]
    m = _LEADING_NUM_RE.match(name)
    if m:
        return re.sub(r"^\d{1,4}[\._\-【\[]?", "", name).strip(" _-.")
    return re.split(r"[\._\-]", name, maxsplit=1)[0]


def next_episode_query(record: PlaybackRecord) -> str | None:
    name = record.filename
    m = _SXXEXX_RE.search(name)
    if m:
        season, ep = int(m.group(1)), int(m.group(2))
        prefix = name[: m.start()]
        return f"{prefix}S{season:02d}E{ep + 1:02d}"
    m = _EPISODE_CN_RE.search(name)
    if m:
        num = _cn_number(m.group(1))
        if num is not None:
            base = record.query or series_prefix(name)
            return f"{base} 第{num + 1}集"
    m = _EXX_RE.search(name)
    if m:
        ep = int(m.group(1))
        prefix = name[: m.start()]
        return f"{prefix}E{ep + 1}"
    m = _LEADING_NUM_RE.match(name)
    if m:
        num = int(m.group(1))
        width = len(m.group(1))
        rest = name[m.start() + len(m.group(1)) :]
        return f"{num + 1:0{width}d}{rest}"
    if record.catalog_key:
        return record.query or record.catalog_key
    return None


class PlaybackStore:
    """Per-device playback state (persisted to disk)."""

    def __init__(self, device_key: str) -> None:
        self.device_key = device_key or "default"
        self.current: PlaybackRecord | None = None
        self.recent: list[PlaybackRecord] = []
        self._load()

    def _path(self) -> Path:
        safe = re.sub(r"[^\w.\-]+", "_", self.device_key)[:80]
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        return _STATE_DIR / f"{safe}.json"

    def _load(self) -> None:
        path = self._path()
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        cur = data.get("current")
        if isinstance(cur, dict) and cur.get("fid"):
            self.current = PlaybackRecord.from_dict(cur)
        self.recent = [
            PlaybackRecord.from_dict(row)
            for row in (data.get("recent") or [])
            if isinstance(row, dict) and row.get("fid")
        ][: settings.playback_history_limit]

    def save(self) -> None:
        payload = {
            "device_key": self.device_key,
            "current": self.current.to_dict() if self.current else None,
            "recent": [row.to_dict() for row in self.recent[: settings.playback_history_limit]],
        }
        try:
            self._path().write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            log.warning("Failed to save playback state for %s", self.device_key)

    def begin(self, source: QuarkStreamSource, *, query: str, media_hint: str, catalog_key: str | None = None, start_offset_ms: int = 0) -> PlaybackRecord:
        rec = PlaybackRecord(
            fid=source.fid,
            filename=source.filename,
            query=query,
            media_hint=media_hint,
            catalog_key=catalog_key,
            position_ms=max(0, start_offset_ms),
            completed=False,
        )
        self.current = rec
        self.save()
        return rec

    def update_progress(self, position_ms: int, *, force_save: bool = False) -> None:
        if self.current is None:
            return
        prev = self.current.position_ms
        self.current.position_ms = max(0, position_ms)
        self.current.updated_at = time.time()
        # Persist about every 5s of playback (HTTP proxy + Mode A).
        if force_save or (position_ms // 5000) != (prev // 5000):
            self.save()

    def finish(self, *, interrupted: bool, final_position_ms: int) -> None:
        if self.current is None:
            return
        rec = self.current
        rec.updated_at = time.time()
        if interrupted:
            rec.position_ms = max(rec.position_ms, final_position_ms)
            rec.completed = False
        else:
            rec.position_ms = 0
            rec.completed = True
        self._push_recent(rec)
        if interrupted:
            self.current = rec
        else:
            self.current = rec
        self.save()

    def _push_recent(self, rec: PlaybackRecord) -> None:
        self.recent = [r for r in self.recent if r.fid != rec.fid]
        self.recent.insert(0, PlaybackRecord.from_dict(rec.to_dict()))
        self.recent = self.recent[: settings.playback_history_limit]

    def resume_target(self) -> PlaybackRecord | None:
        min_ms = settings.playback_resume_min_ms
        if self.current and not self.current.completed and self.current.position_ms >= min_ms:
            return self.current
        for rec in self.recent:
            if not rec.completed and rec.position_ms >= min_ms:
                self.current = rec
                return rec
        return None

    def incomplete_for_catalog(self, catalog_key: str | None) -> PlaybackRecord | None:
        """Unfinished episode in this series (for bare「西游记」→ resume)."""
        if not catalog_key:
            return None
        min_ms = settings.playback_resume_min_ms
        if (
            self.current
            and self.current.catalog_key == catalog_key
            and not self.current.completed
            and self.current.position_ms >= min_ms
            and self.current.fid
        ):
            return self.current
        for rec in self.recent:
            if (
                rec.catalog_key == catalog_key
                and not rec.completed
                and rec.position_ms >= min_ms
                and rec.fid
            ):
                return rec
        return None

    def last_played(self) -> PlaybackRecord | None:
        if self.current:
            return self.current
        return self.recent[0] if self.recent else None

    def context_for_llm(self) -> str:
        lines: list[str] = []
        if self.current:
            pos = self.current.position_ms // 1000
            status = "已播完" if self.current.completed else f"播到约{pos}秒，可续播"
            lines.append(f"- 当前/上次：{self.current.short_title()}（{status}）")
            nxt = next_episode_query(self.current)
            if nxt:
                lines.append(f"- 下一集搜索词建议：{nxt}")
        if self.recent:
            titles = "、".join(r.short_title() for r in self.recent[:3])
            lines.append(f"- 最近听过：{titles}")
        return "\n".join(lines) if lines else "（暂无播放记录）"


def find_next_episode_source(
    client: QuarkClient,
    record: PlaybackRecord,
) -> QuarkStreamSource | None:
    from server.content_catalog import resolve_play_request
    from server.media_index import (
        find_next_file,
        index_available,
        resolve_catalog_key_for_record,
    )

    catalog_key = resolve_catalog_key_for_record(
        catalog_key=record.catalog_key,
        filename=record.filename,
        query=record.query,
    )
    if index_available() and catalog_key:
        nxt = find_next_file(
            catalog_key,
            record.fid,
            current_filename=record.filename,
        )
        if nxt is not None:
            try:
                source = client.resolve_stream_source(
                    nxt.fid,
                    filename_hint=nxt.filename,
                    size_hint=nxt.size,
                )
                log.info("Media index next: %s -> %s", catalog_key, nxt.filename)
                return source
            except Exception as exc:
                log.warning("Media index next resolve failed: %s", exc)

    query_hint = next_episode_query(record)
    search_key = query_hint or record.query
    if not search_key:
        return None

    _, hint, catalog_entry = resolve_play_request(
        search_key,
        user_text=search_key,
        media_hint=record.media_hint,
    )
    if catalog_entry and catalog_entry.search_queries:
        search_keys = list(catalog_entry.search_queries)
    else:
        prefix = series_prefix(record.filename)
        search_keys = [query_hint, f"{prefix} mp3", record.query, search_key]
    search_keys = [q for q in dict.fromkeys(q.strip() for q in search_keys if q and q.strip())]

    candidates: list[QuarkFile] = []
    seen: set[str] = set()
    for q in search_keys[:4]:
        try:
            files = client.search_media(q, limit=max(30, settings.quark_pick_top))
        except Exception as exc:
            log.warning("Next-episode search failed for %r: %s", q, exc)
            continue
        for item in files:
            if item.fid in seen:
                continue
            seen.add(item.fid)
            candidates.append(item)

    if not candidates:
        if query_hint:
            return client.find_stream_source(
                query_hint,
                user_text=query_hint,
                media_hint=record.media_hint,
            )
        return None

    current_key = episode_sort_key(record.filename)
    prefix = series_prefix(record.filename).lower()
    same_series = [
        f
        for f in candidates
        if f.fid != record.fid
        and (
            series_prefix(f.filename).lower() == prefix
            or prefix[:4] in f.filename.lower()
            or (record.catalog_key and record.catalog_key.lower() in f.filename.lower())
        )
    ]
    pool = same_series or [f for f in candidates if f.fid != record.fid]
    if not pool:
        return None

    pool.sort(key=lambda f: episode_sort_key(f.filename))
    for item in pool:
        if episode_sort_key(item.filename) > current_key:
            try:
                return client.resolve_stream_source(
                    item.fid,
                    filename_hint=item.filename,
                    size_hint=item.size,
                )
            except Exception:
                log.exception("Resolve next episode failed: %s", item.filename)
    return None


def resolve_source_for_record(
    client: QuarkClient,
    record: PlaybackRecord,
    http_app,
) -> QuarkStreamSource | None:
    from server.http_stream import cache_stream_source

    cache = http_app.get("quark_stream_cache") or {}
    cached = cache.get(record.fid)
    if cached is not None:
        return cached
    try:
        files = client.search_media(record.filename, limit=5)
    except Exception:
        files = []
    for item in files:
        if item.fid == record.fid or item.filename == record.filename:
            source = client.resolve_stream_source(
                item.fid,
                filename_hint=item.filename,
                size_hint=item.size,
            )
            cache_stream_source(http_app, source)
            return source
    return client.find_stream_source(
        record.query or record.filename,
        user_text=record.filename,
        media_hint=record.media_hint,
    )
