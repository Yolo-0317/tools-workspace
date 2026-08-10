#!/usr/bin/env python3
"""Build quark_media_index.json by searching playable audio for each catalog series."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
sys.path.insert(0, str(ROOT))

from server.playback_memory import episode_sort_key  # noqa: E402

ALIASES_PATH = ROOT / "data/quark_content_aliases.json"
INDEX_PATH = ROOT / "data/quark_media_index.json"
CLI_PATH = WORKSPACE / ".cursor/skills/quarkclouddrive/scripts/quark-drive.cjs"
HERMES_CONFIG = WORKSPACE / ".cursor/skills/quarkclouddrive/hermes/config.json"

_MEDIA_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg"}
_DISFAVOR = ("预告", "片花", "铃声", "采访", "歌单", "mv", "bgm", "试播", "片头", "trailer")


def _load_catalog() -> dict[str, dict[str, Any]]:
    if not ALIASES_PATH.is_file():
        raise SystemExit(f"Missing catalog: {ALIASES_PATH}")
    data = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _cli_env() -> dict[str, str]:
    import os

    env = os.environ.copy()
    data = json.loads(HERMES_CONFIG.read_text(encoding="utf-8"))
    env["HERMES_SESSION_ID"] = str(data.get("currentUserId") or "index-scan")
    return env


def _parse_ndjson(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _search_files(keyword: str, *, limit: int = 100) -> list[dict[str, Any]]:
    if not CLI_PATH.is_file():
        raise SystemExit(f"Quark CLI not found: {CLI_PATH}")
    cmd = [
        "node",
        str(CLI_PATH),
        "search",
        "--keyword",
        keyword,
        "--size",
        str(limit),
        "--stdout-only",
        "--category",
        "2",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=_cli_env(),
        timeout=120,
    )
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-300:]
        print(f"  warn search {keyword!r}: {tail}", file=sys.stderr)
        return []
    rows = _parse_ndjson(proc.stdout)
    result = next(
        (row for row in rows if row.get("action") == "search" and row.get("type") == "result"),
        None,
    )
    if not result:
        return []
    file_list = list((result.get("data") or {}).get("file_list") or [])
    artifact = next((row for row in rows if row.get("type") == "artifact"), None)
    if artifact:
        path = str((artifact.get("data") or {}).get("file_path") or "")
        if path:
            artifact_path = Path(path)
            if artifact_path.is_file():
                extra: list[dict[str, Any]] = []
                for line in artifact_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        if isinstance(row, dict):
                            extra.append(row)
                    except json.JSONDecodeError:
                        continue
                if extra:
                    file_list = extra
    return file_list


def _is_playable(row: dict[str, Any], *, filename_boost: list[str]) -> bool:
    name = str(row.get("filename") or "")
    if not name:
        return False
    ext = Path(name).suffix.lower()
    if ext not in _MEDIA_EXTENSIONS:
        return False
    lower = name.lower()
    if any(part in lower for part in _DISFAVOR):
        return False
    if filename_boost:
        return any(token.lower() in lower for token in filename_boost)
    return True


def _row_to_entry(row: dict[str, Any]) -> dict[str, Any]:
    name = str(row.get("filename") or "")
    return {
        "fid": str(row.get("fid") or ""),
        "filename": name,
        "size": int(row.get("size") or 0),
        "sort_key": list(episode_sort_key(name)),
    }


def build_index() -> dict[str, Any]:
    catalog = _load_catalog()
    series_out: dict[str, Any] = {}

    for key, item in catalog.items():
        title = str(item.get("title") or key)
        queries = list(item.get("search_queries") or [title])
        boost = [str(x) for x in (item.get("filename_boost") or []) if str(x).strip()]
        seen_fids: set[str] = set()
        collected: list[dict[str, Any]] = []

        print(f"[{key}] {title}")
        for query in queries[:5]:
            print(f"  search: {query}")
            try:
                rows = _search_files(query, limit=100)
            except subprocess.TimeoutExpired:
                print("  timeout", file=sys.stderr)
                continue
            for row in rows:
                fid = str(row.get("fid") or "")
                if not fid or fid in seen_fids:
                    continue
                if not _is_playable(row, filename_boost=boost):
                    continue
                seen_fids.add(fid)
                collected.append(_row_to_entry(row))
            time.sleep(0.2)

        collected.sort(key=lambda r: tuple(r.get("sort_key") or []))
        series_out[key] = {
            "title": title,
            "path_hint": str(item.get("path_hint") or ""),
            "media_hint": str(item.get("media_hint") or "story_audio"),
            "aliases": list(item.get("aliases") or []),
            "file_count": len(collected),
            "files": collected,
        }
        print(f"  -> {len(collected)} files")

    return {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "catalog_source": str(ALIASES_PATH.name),
        "series_count": len(series_out),
        "series": series_out,
    }


def main() -> None:
    if not HERMES_CONFIG.is_file():
        raise SystemExit(f"Quark not configured: {HERMES_CONFIG}")
    index = build_index()
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(s.get("file_count", 0) for s in index["series"].values())
    print(f"\nWrote {index['series_count']} series, {total} files -> {INDEX_PATH}")


if __name__ == "__main__":
    main()
