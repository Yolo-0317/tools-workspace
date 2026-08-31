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
VOICE_TRIAL_FIELDS = ("recipient", "situation", "blessing", "poem")
OUTLINE_FIELDS = ("recipient", "blessing", "poem")
EPISODE_FIELDS = (
    "episode",
    "production_status",
    "recipient",
    "blessing",
    "poem",
    "attribution",
    "share_scene",
    "dance_event",
)
SUBTITLE_IDS = ["01-recipient", "02-situation", "03-blessing", "04-poem"]


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

    recitation = data.get("recitation")
    expected_recitation = {
        "target_hanzi_min": 55,
        "target_hanzi_max": 60,
        "voice_start_max_ms": 200,
        "voice_end_min_ms": 14000,
        "voice_end_target_max_ms": 14800,
        "duration_ms": 15000,
        "max_gap_ms": 500,
        "speech_rate": 0,
    }
    if recitation != expected_recitation:
        raise ValueError(f"recitation must be {expected_recitation}")

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
    voice_trials: list[str] = []
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

        status = values["production_status"]
        if status not in {"voice-trial", "theme-outline"}:
            raise ValueError(
                f"episodes[{index}].production_status must be voice-trial or theme-outline"
            )
        spoken_fields = OUTLINE_FIELDS
        if status == "voice-trial":
            voice_trials.append(values["episode"])
            situation = _require_nonempty_string(
                episode.get("situation"), f"episodes[{index}].situation"
            )
            values["situation"] = situation
            spoken_fields = VOICE_TRIAL_FIELDS

        if count_hanzi(values["recipient"]) > 10:
            raise ValueError(f"episodes[{index}].recipient exceeds 10 Hanzi")
        if count_hanzi(values["poem"]) > 14:
            raise ValueError(f"episodes[{index}].poem exceeds 14 Hanzi")

        total = 0
        for field in spoken_fields:
            total += count_hanzi(values[field])
            for phrase in banned:
                if phrase in values[field]:
                    raise ValueError(
                        f"episodes[{index}].{field} contains banned phrase: {phrase}"
                    )
        if status == "voice-trial" and not (
            recitation["target_hanzi_min"] <= total <= recitation["target_hanzi_max"]
        ):
            raise ValueError(
                f"episodes[{index}] voice-trial has {total} Hanzi; "
                f"required {recitation['target_hanzi_min']} to "
                f"{recitation['target_hanzi_max']}"
            )

        for field in unique_fields:
            value = values[field]
            if value in seen[field]:
                raise ValueError(f"episodes[{index}].{field} must be unique")
            seen[field].add(value)

    if voice_trials != ["yiwu-yiyuan-qiancheng-01-restart-15s"]:
        raise ValueError("restart must be the only voice-trial episode")


def validate_subtitle_plan(
    path: Path,
    duration_ms: int,
    voice_start_max_ms: int,
    voice_end_min_ms: int,
    voice_end_target_max_ms: int,
    max_gap_ms: int,
) -> None:
    items = _read_json(path)
    if not isinstance(items, list) or len(items) != 4:
        raise ValueError("subtitle plan must contain exactly 4 items")
    if [item.get("id") if isinstance(item, dict) else None for item in items] != SUBTITLE_IDS:
        raise ValueError("subtitle ids must be recipient, situation, blessing, poem")

    for index, item in enumerate(items):
        start = item.get("start")
        end = item.get("end")
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            raise ValueError(f"subtitle {index + 1} start must be numeric")
        if isinstance(end, bool) or not isinstance(end, (int, float)):
            raise ValueError(f"subtitle {index + 1} end must be numeric")
        if start < 0 or end <= start:
            raise ValueError(f"subtitle {index + 1} must have a positive interval")

    if any(items[index]["end"] > items[index + 1]["start"] for index in range(3)):
        raise ValueError("subtitle timeline overlaps")

    voice_start_ms = round(float(items[0]["start"]) * 1000)
    if voice_start_ms > voice_start_max_ms:
        raise ValueError(f"voice start {voice_start_ms} exceeds {voice_start_max_ms}")

    for index in range(3):
        gap_ms = round(
            (float(items[index + 1]["start"]) - float(items[index]["end"])) * 1000
        )
        if gap_ms > max_gap_ms:
            raise ValueError(f"subtitle gap {gap_ms} exceeds {max_gap_ms}")

    voice_end_ms = round(float(items[-1]["end"]) * 1000)
    if voice_end_ms < voice_end_min_ms:
        raise ValueError(f"voice end {voice_end_ms} is before {voice_end_min_ms}")
    if voice_end_ms > duration_ms:
        raise ValueError(f"voice end {voice_end_ms} exceeds {duration_ms}")

    if voice_end_target_max_ms > duration_ms:
        raise ValueError("voice end target exceeds video duration")


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
            status = episode["production_status"]
            fields = VOICE_TRIAL_FIELDS if status == "voice-trial" else OUTLINE_FIELDS
            total = sum(count_hanzi(episode[field]) for field in fields)
            print(f"{episode['episode']}: {status}: {total} Hanzi")
    else:
        validate_subtitle_plan(args.subtitle_plan, 15000, 200, 14000, 14800, 500)
        items = _read_json(args.subtitle_plan)
        voice_end_ms = round(float(items[-1]["end"]) * 1000)
        if voice_end_ms > 14800:
            print(f"warning: voice end {voice_end_ms} exceeds target 14800")
        print(f"subtitle plan valid: {args.subtitle_plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
