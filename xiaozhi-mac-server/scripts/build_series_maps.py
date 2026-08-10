#!/usr/bin/env python3
"""Rebuild data/quark_series_maps/*.json + catalog overview from media index."""

from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ALIASES = DATA / "quark_content_aliases.json"
INDEX = DATA / "quark_media_index.json"
SCAN = DATA / "quark_yueyue_scan_report.json"
MAPS = DATA / "quark_series_maps"
OVERVIEW = DATA / "quark_yueyue_catalog_overview.json"

_WOW_STORY_RE = re.compile(
    r"^(\d{3})\.(.+)\.mp3$",
    re.I,
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_overview(aliases: dict, series: dict, scan: dict, now: str) -> None:
    overview = {
        "built_at": now,
        "note": "玥玥 catalog keys vs media index; empty unique_filenames → rebuild index / fix search_queries.",
        "yueyue_scan_folder_count": scan.get("discovered_folder_count"),
        "catalog": {},
        "scan_folders": sorted((scan.get("folders") or {}).keys()),
    }
    for key, meta in aliases.items():
        files = (series.get(key) or {}).get("files") or []
        uniq = sorted({f.get("filename") for f in files if f.get("filename")})
        overview["catalog"][key] = {
            "title": meta.get("title"),
            "path_hint": meta.get("path_hint"),
            "media_hint": meta.get("media_hint"),
            "index_file_rows": len(files),
            "unique_filenames": len(uniq),
            "first_file": uniq[0] if uniq else None,
            "has_series_map": (MAPS / f"{key}.json").is_file(),
            "status": "ok" if uniq else "empty_index",
        }
    OVERVIEW.write_text(json.dumps(overview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OVERVIEW.relative_to(ROOT)}")


def build_frozen(series: dict, scan: dict, now: str) -> int:
    files = (series.get("frozen") or {}).get("files") or []
    if not files:
        print("frozen series empty in media index", file=sys.stderr)
        return 1

    by_n: OrderedDict[int, dict] = OrderedDict()
    for row in files:
        name = str(row.get("filename") or "")
        m = re.match(r"^(\d{4})-", name)
        if not m:
            continue
        n = int(m.group(1))
        season = 2 if "冰雪奇缘二" in name else 1
        sep = re.search(r"冰雪奇缘二?(\d{2})", name)
        season_ep = int(sep.group(1)) if sep else None
        title_m = re.match(r"^\d{4}-冰雪奇缘二?\d{2}\s*(.+)\.mp3$", name, re.I)
        short = title_m.group(1).strip() if title_m else name
        entry = by_n.setdefault(
            n,
            {
                "global_n": n,
                "season": season,
                "season_ep": season_ep,
                "filename": name,
                "title": short,
                "fids": [],
            },
        )
        fid = row.get("fid")
        if fid and fid not in entry["fids"]:
            entry["fids"].append(fid)

    eps = list(by_n.values())
    s1 = [e for e in eps if e["season"] == 1]
    s2 = [e for e in eps if e["season"] == 2]
    ep1 = eps[0]
    fmap = {
        "catalog_key": "frozen",
        "title": "冰雪奇缘 Frozen",
        "path_hint": "玥玥/冰雪奇缘",
        "folder_fid": (scan.get("folders") or {}).get("冰雪奇缘", {}).get("fid"),
        "built_at": now,
        "source": "derived from quark_media_index.json; leading NNNN is canonical order",
        "rules": {
            "default_play": "global_n=1 (第一部第1集)",
            "voice_第一集": "season=1 season_ep=1 → 0001-冰雪奇缘01 神奇的冰雪魔法.mp3",
            "voice_第二部第一集": "season=2 season_ep=1 → 0038-冰雪奇缘二01 …",
            "do_not_confuse": "0037 含「第一部完结」不是第一集；0075 是全书最后一集",
            "duplicate_fids": "每集常有 2 个 fid，播放取 fids[0]",
        },
        "default_start": {
            "global_n": 1,
            "season": 1,
            "season_ep": 1,
            "filename": ep1["filename"],
            "title": ep1["title"],
            "fid": ep1["fids"][0],
            "fids": ep1["fids"],
        },
        "seasons": [
            {
                "id": 1,
                "label": "第一部",
                "aliases": ["第一部", "一部", "frozen 1", "冰雪奇缘一"],
                "episode_count": len(s1),
                "global_range": [s1[0]["global_n"], s1[-1]["global_n"]],
                "first_filename": s1[0]["filename"],
                "last_filename": s1[-1]["filename"],
            },
            {
                "id": 2,
                "label": "第二部",
                "aliases": ["第二部", "二部", "续集", "冰雪奇缘二", "frozen 2"],
                "episode_count": len(s2),
                "global_range": [s2[0]["global_n"], s2[-1]["global_n"]],
                "first_filename": s2[0]["filename"],
                "last_filename": s2[-1]["filename"],
            },
        ],
        "episode_count": len(eps),
        "episodes": [{**e, "fid": e["fids"][0]} for e in eps],
    }
    MAPS.mkdir(parents=True, exist_ok=True)
    out = MAPS / "frozen.json"
    out.write_text(json.dumps(fmap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(eps)} episodes)")
    print(f"default_start: {fmap['default_start']['filename']}")
    return 0


def build_steve_maggie(series: dict, aliases: dict, now: str) -> int:
    """Wow English TV stories: leading NNN. + 'Wow English TV' in name.

    Excludes Blue/Gold course packs and Songs-for-kids tracks without Wow English TV.
    Duplicate NNN keep first-seen filename; merge fids.
    """
    files = (series.get("steve_maggie") or {}).get("files") or []
    if not files:
        print("steve_maggie series empty in media index", file=sys.stderr)
        return 1

    meta = aliases.get("steve_maggie") or {}
    by_n: OrderedDict[int, dict] = OrderedDict()
    for row in files:
        name = str(row.get("filename") or "")
        if "Wow English TV" not in name and "Wow English Tv" not in name:
            # Case-insensitive check
            if "wow english tv" not in name.lower():
                continue
        m = _WOW_STORY_RE.match(name)
        if not m:
            continue
        n = int(m.group(1))
        short = m.group(2).strip()
        entry = by_n.setdefault(
            n,
            {
                "global_n": n,
                "season": 1,
                "season_ep": None,  # filled after sort
                "filename": name,
                "title": short,
                "fids": [],
            },
        )
        fid = row.get("fid")
        if fid and fid not in entry["fids"]:
            entry["fids"].append(fid)

    if not by_n:
        print("no Wow English TV NNN. stories found for steve_maggie", file=sys.stderr)
        return 1

    eps = list(by_n.values())
    for i, e in enumerate(eps, start=1):
        e["season_ep"] = i
    ep1 = eps[0]
    path_hint = meta.get("path_hint") or ""
    fmap = {
        "catalog_key": "steve_maggie",
        "title": meta.get("title") or "Wow English / Steve and Maggie",
        "path_hint": path_hint,
        "folder_fid": None,
        "built_at": now,
        "source": "derived from quark_media_index.json; leading NNN. is Wow English TV story order",
        "rules": {
            "default_play": f"global_n={ep1['global_n']} → {ep1['filename']}",
            "voice_第一集": "season_ep=1",
            "scope": "仅收录 NNN. 开头的 Wow English TV 故事；不含 Blue/Gold 课程长音频、不含 Songs for kids 儿歌编号",
            "duplicate_fids": "每集可有多个 fid，播放取 fids[0]",
        },
        "default_start": {
            "global_n": ep1["global_n"],
            "season": 1,
            "season_ep": 1,
            "filename": ep1["filename"],
            "title": ep1["title"],
            "fid": ep1["fids"][0],
            "fids": ep1["fids"],
        },
        "seasons": [
            {
                "id": 1,
                "label": "Wow English TV 故事",
                "aliases": ["wow english", "steve and maggie", "第一部", "哇英语"],
                "episode_count": len(eps),
                "global_range": [eps[0]["global_n"], eps[-1]["global_n"]],
                "first_filename": eps[0]["filename"],
                "last_filename": eps[-1]["filename"],
            }
        ],
        "episode_count": len(eps),
        "episodes": [{**e, "fid": e["fids"][0]} for e in eps],
    }
    MAPS.mkdir(parents=True, exist_ok=True)
    out = MAPS / "steve_maggie.json"
    out.write_text(json.dumps(fmap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(eps)} episodes)")
    print(f"default_start: {fmap['default_start']['filename']}")
    return 0


def build_journey_west(series: dict, aliases: dict, now: str) -> int:
    """儿童广播剧：NNN.第…回 ….mp3；编号从 002=第一回 起，无 001。"""
    files = (series.get("journey_west") or {}).get("files") or []
    if not files:
        print("journey_west series empty in media index", file=sys.stderr)
        return 1

    meta = aliases.get("journey_west") or {}
    by_n: OrderedDict[int, dict] = OrderedDict()
    for row in files:
        name = str(row.get("filename") or "")
        m = re.match(r"^(\d{3})\.(.+)\.mp3$", name, re.I)
        if not m or "回" not in name:
            continue
        n = int(m.group(1))
        short = m.group(2).strip()
        entry = by_n.setdefault(
            n,
            {
                "global_n": n,
                "season": 1,
                "season_ep": None,
                "filename": name,
                "title": short,
                "fids": [],
            },
        )
        fid = row.get("fid")
        if fid and fid not in entry["fids"]:
            entry["fids"].append(fid)

    eps = list(by_n.values())
    if not eps:
        print("journey_west: no NNN.第…回 episodes", file=sys.stderr)
        return 1
    for i, e in enumerate(eps, start=1):
        e["season_ep"] = i

    ep1 = eps[0]
    fmap = {
        "catalog_key": "journey_west",
        "title": meta.get("title") or "西游记儿童广播剧",
        "path_hint": meta.get("path_hint") or "玥玥/04.【完结】西游记儿童广播剧",
        "built_at": now,
        "source": "derived from quark_media_index.json; leading NNN. + 第N回",
        "rules": {
            "default_play": f"global_n={ep1['global_n']} → {ep1['filename']}",
            "voice_第一集": "season_ep=1（文件常为 002.第一回 …）",
            "scope": "仅收录 NNN.第…回 的儿童广播剧 mp3；无 001 文件属正常",
            "duplicate_fids": "每集可有多个 fid，播放取 fids[0]",
        },
        "default_start": {
            "global_n": ep1["global_n"],
            "season": 1,
            "season_ep": 1,
            "filename": ep1["filename"],
            "title": ep1["title"],
            "fid": ep1["fids"][0],
            "fids": ep1["fids"],
        },
        "seasons": [
            {
                "id": 1,
                "label": "西游记儿童广播剧",
                "aliases": ["西游记", "美猴王", "孙悟空", "广播剧"],
                "episode_count": len(eps),
                "global_range": [eps[0]["global_n"], eps[-1]["global_n"]],
                "first_filename": eps[0]["filename"],
                "last_filename": eps[-1]["filename"],
            }
        ],
        "episode_count": len(eps),
        "episodes": [{**e, "fid": e["fids"][0]} for e in eps],
    }
    MAPS.mkdir(parents=True, exist_ok=True)
    out = MAPS / "journey_west.json"
    out.write_text(json.dumps(fmap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(eps)} episodes)")
    print(f"default_start: {fmap['default_start']['filename']}")
    return 0


def main() -> int:
    aliases = json.loads(ALIASES.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    scan = json.loads(SCAN.read_text(encoding="utf-8")) if SCAN.is_file() else {}
    series = index.get("series") or {}
    now = _now()

    MAPS.mkdir(parents=True, exist_ok=True)
    rc = 0
    rc |= build_frozen(series, scan, now)
    rc |= build_steve_maggie(series, aliases, now)
    rc |= build_journey_west(series, aliases, now)
    # Overview after maps exist so has_series_map is accurate
    write_overview(aliases, series, scan, now)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
