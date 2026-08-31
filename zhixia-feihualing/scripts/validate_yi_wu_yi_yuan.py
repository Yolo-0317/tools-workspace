#!/usr/bin/env python3
"""Validate the fixed content and subtitle timing for 一舞一愿."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


HANZI = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ATTRIBUTION = re.compile(r"^[^·《》]+·[^·《》]+《[^《》]+》$")
SPOKEN_FIELDS = ("recipient", "blessing", "poem")
EPISODE_FIELDS = (
    "episode",
    "recipient",
    "blessing",
    "poem",
    "attribution",
    "share_scene",
    "dance_event",
)
SUBTITLE_IDS = ["01-recipient", "02-blessing", "03-poem"]


def count_hanzi(text: str) -> int:
    """Count CJK unified ideographs while ignoring punctuation and spaces."""
    return len(HANZI.findall(text))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {path}") from exc


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def validate_season(path: Path) -> None:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError("season must be an object")

    if data.get("series") != "yi-wu-yi-yuan":
        raise ValueError("series must be yi-wu-yi-yuan")
    season = _require_nonempty_string(data.get("season"), "season")
    if not SLUG.fullmatch(season):
        raise ValueError("season must be a lowercase hyphenated slug")

    for field, expected in (
        ("duration_ms", 15000),
        ("voice_end_max_ms", 11500),
        ("tail_min_ms", 3000),
    ):
        if data.get(field) != expected:
            raise ValueError(f"{field} must be {expected}")

    limits = data.get("max_hanzi")
    if not isinstance(limits, dict):
        raise ValueError("max_hanzi must be an object")
    expected_limits = {"recipient": 10, "blessing": 12, "poem": 14, "total": 34}
    if limits != expected_limits:
        raise ValueError(f"max_hanzi must be {expected_limits}")

    banned = data.get("banned_phrases")
    if not isinstance(banned, list) or not banned or not all(
        isinstance(phrase, str) and phrase for phrase in banned
    ):
        raise ValueError("banned_phrases must be a non-empty string list")

    episodes = data.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != 3:
        raise ValueError("episodes must contain exactly 3 entries")

    unique_fields = ("episode", "recipient", "poem", "dance_event")
    seen: dict[str, set[str]] = {field: set() for field in unique_fields}
    for index, episode in enumerate(episodes, start=1):
        if not isinstance(episode, dict):
            raise ValueError(f"episodes[{index}] must be an object")
        values = {
            field: _require_nonempty_string(episode.get(field), f"episodes[{index}].{field}")
            for field in EPISODE_FIELDS
        }
        if not SLUG.fullmatch(values["episode"]):
            raise ValueError(f"episodes[{index}].episode must be a lowercase hyphenated slug")
        if not ATTRIBUTION.fullmatch(values["attribution"]):
            raise ValueError(
                f"episodes[{index}].attribution must include dynasty, author and title"
            )

        total = 0
        for field in SPOKEN_FIELDS:
            length = count_hanzi(values[field])
            limit = limits[field]
            if length > limit:
                raise ValueError(
                    f"episodes[{index}].{field} has {length} Hanzi; maximum is {limit}"
                )
            total += length
            for phrase in banned:
                if phrase in values[field]:
                    raise ValueError(
                        f"episodes[{index}].{field} contains banned phrase: {phrase}"
                    )
        if total > limits["total"]:
            raise ValueError(
                f"episodes[{index}] has {total} spoken Hanzi; maximum is {limits['total']}"
            )

        for field in unique_fields:
            value = values[field]
            if value in seen[field]:
                raise ValueError(f"episodes[{index}].{field} must be unique")
            seen[field].add(value)


def validate_subtitle_plan(
    path: Path,
    duration_ms: int,
    voice_end_max_ms: int,
    tail_min_ms: int,
) -> None:
    items = _read_json(path)
    if not isinstance(items, list) or len(items) != 3:
        raise ValueError("subtitle plan must contain exactly 3 items")
    if [item.get("id") if isinstance(item, dict) else None for item in items] != SUBTITLE_IDS:
        raise ValueError("subtitle ids must be recipient, blessing, poem")

    for index, item in enumerate(items):
        start = item.get("start")
        end = item.get("end")
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            raise ValueError(f"subtitle {index + 1} start must be numeric")
        if isinstance(end, bool) or not isinstance(end, (int, float)):
            raise ValueError(f"subtitle {index + 1} end must be numeric")
        if start < 0 or end <= start:
            raise ValueError(f"subtitle {index + 1} must have a positive interval")

    if any(items[index]["end"] > items[index + 1]["start"] for index in range(2)):
        raise ValueError("subtitle timeline overlaps")

    voice_end_ms = round(float(items[-1]["end"]) * 1000)
    if voice_end_ms > voice_end_max_ms:
        raise ValueError(f"voice end {voice_end_ms} exceeds {voice_end_max_ms}")
    if duration_ms - voice_end_ms < tail_min_ms:
        raise ValueError("tail is shorter than required")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--season", type=Path)
    group.add_argument("--subtitle-plan", type=Path)
    args = parser.parse_args()

    if args.season:
        validate_season(args.season)
        data = _read_json(args.season)
        for episode in data["episodes"]:
            total = sum(count_hanzi(episode[field]) for field in SPOKEN_FIELDS)
            print(f"{episode['episode']}: {total} Hanzi")
    else:
        validate_subtitle_plan(args.subtitle_plan, 15000, 11500, 3000)
        print(f"subtitle plan valid: {args.subtitle_plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
