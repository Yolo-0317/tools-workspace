"""Manifest parsing and timeline rules for Zhixia TTS generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINE_ID_PATTERN = re.compile(r"^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class VoiceConfig:
    key: str
    name: str
    speaker: str
    resource_id: str


@dataclass(frozen=True)
class VoiceLine:
    id: str
    role: str
    text: str
    start_ms: int | None = None
    gap_before_ms: int = 0
    revision: int = 1
    context_texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class EpisodeManifest:
    episode: str
    format: str
    theme: str
    theme_slug: str
    audio_slug: str
    lines: tuple[VoiceLine, ...]
    voices: dict[str, VoiceConfig]


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}不能为空")
    return value.strip()


def _nonnegative_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} 必须是非负整数")
    return value


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} 必须是正整数")
    return value


def _context_texts(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field} 必须是字符串列表")
    return tuple(
        _nonempty_string(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def load_voice_config(path: Path) -> dict[str, VoiceConfig]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取角色音色配置: {path}") from exc
    if not isinstance(raw, dict) or not raw:
        raise ValueError("角色音色配置必须是非空对象")

    voices: dict[str, VoiceConfig] = {}
    for key, item in raw.items():
        if not isinstance(key, str) or not SLUG_PATTERN.fullmatch(key):
            raise ValueError(f"角色键无效: {key}")
        if not isinstance(item, dict):
            raise ValueError(f"角色配置必须是对象: {key}")
        voices[key] = VoiceConfig(
            key=key,
            name=_nonempty_string(item.get("name"), f"{key}.name"),
            speaker=_nonempty_string(item.get("speaker"), f"{key}.speaker"),
            resource_id=_nonempty_string(
                item.get("resource_id"), f"{key}.resource_id"
            ),
        )
    return voices


def manifest_from_dict(
    data: Mapping[str, Any], voices: Mapping[str, VoiceConfig]
) -> EpisodeManifest:
    if not isinstance(data, Mapping):
        raise ValueError("配音清单必须是对象")

    episode = _nonempty_string(data.get("episode"), "episode")
    episode_format = data.get("format", "one-character-three-poems")
    episode_format = _nonempty_string(episode_format, "format")
    allowed_line_counts: dict[str, set[int] | None] = {
        "one-character-three-poems": {4, 5},
        "one-character-two-poems": {2, 3},
        "one-poem-story": None,
    }
    if episode_format not in allowed_line_counts:
        raise ValueError(f"未知飞花令格式: {episode_format}")
    theme = _nonempty_string(data.get("theme"), "theme")
    theme_slug = _nonempty_string(data.get("theme_slug"), "theme_slug")
    audio_slug = _nonempty_string(data.get("audio_slug"), "audio_slug")
    if not SLUG_PATTERN.fullmatch(episode):
        raise ValueError("episode 必须是小写英文、数字或连字符")
    if not SLUG_PATTERN.fullmatch(theme_slug):
        raise ValueError("theme_slug 必须是小写英文、数字或连字符")
    if not SLUG_PATTERN.fullmatch(audio_slug):
        raise ValueError("audio_slug 必须是小写英文、数字或连字符")

    raw_lines = data.get("lines")
    expected_counts = allowed_line_counts[episode_format]
    if not isinstance(raw_lines, list):
        raise ValueError(f"{episode_format} 配音清单的 lines 必须是列表")
    if expected_counts is None:
        if not raw_lines:
            raise ValueError(f"{episode_format} 配音清单必须至少包含 1 句")
    elif len(raw_lines) not in expected_counts:
        expected = " 或 ".join(str(count) for count in sorted(expected_counts))
        raise ValueError(f"{episode_format} 配音清单必须包含 {expected} 句")

    parsed: list[VoiceLine] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_lines, start=1):
        if not isinstance(raw, Mapping):
            raise ValueError(f"第 {index} 句必须是对象")
        line_id = _nonempty_string(raw.get("id"), f"第 {index} 句 id")
        if not LINE_ID_PATTERN.fullmatch(line_id):
            raise ValueError(f"台词 ID 无效: {line_id}")
        if line_id in seen_ids:
            raise ValueError(f"重复台词 ID: {line_id}")
        seen_ids.add(line_id)

        role = _nonempty_string(raw.get("role"), f"{line_id}.role")
        if role not in voices:
            raise ValueError(f"未知角色: {role}")
        text = _nonempty_string(raw.get("text"), f"{line_id} 台词")
        if len(text) > 300:
            raise ValueError(f"{line_id} 台词超过 300 个字符")

        has_start = "start_ms" in raw
        has_gap = "gap_before_ms" in raw
        if has_start and has_gap:
            raise ValueError(f"{line_id} 不能同时设置 start_ms 和 gap_before_ms")
        start_ms = (
            _nonnegative_integer(raw["start_ms"], f"{line_id}.start_ms")
            if has_start
            else None
        )
        gap_before_ms = (
            _nonnegative_integer(raw["gap_before_ms"], f"{line_id}.gap_before_ms")
            if has_gap
            else 0
        )
        revision = _positive_integer(raw.get("revision", 1), f"{line_id}.revision")
        context_texts = _context_texts(
            raw.get("context_texts"), f"{line_id}.context_texts"
        )
        parsed.append(
            VoiceLine(
                id=line_id,
                role=role,
                text=text,
                start_ms=start_ms,
                gap_before_ms=gap_before_ms,
                revision=revision,
                context_texts=context_texts,
            )
        )

    return EpisodeManifest(
        episode=episode,
        format=episode_format,
        theme=theme,
        theme_slug=theme_slug,
        audio_slug=audio_slug,
        lines=tuple(parsed),
        voices=dict(voices),
    )


def load_episode_manifest(
    path: Path, voices: Mapping[str, VoiceConfig]
) -> EpisodeManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取配音清单: {path}") from exc
    return manifest_from_dict(data, voices)


def audio_filename(line: VoiceLine) -> str:
    number, semantic = line.id.split("-", 1)
    suffix = "" if line.revision == 1 else f"-v{line.revision:02d}"
    return f"{number}-{line.role}-{semantic}{suffix}.mp3"


def build_subtitles(
    manifest: EpisodeManifest, durations_ms: Mapping[str, int]
) -> list[dict[str, object]]:
    subtitles: list[dict[str, object]] = []
    previous_end_ms = 0
    for line in manifest.lines:
        if line.id not in durations_ms:
            raise ValueError(f"缺少音频时长: {line.id}")
        duration_ms = _positive_integer(durations_ms[line.id], f"{line.id}.duration_ms")
        if line.start_ms is None:
            start_ms = previous_end_ms + line.gap_before_ms
        else:
            start_ms = line.start_ms
        if subtitles and start_ms < previous_end_ms:
            raise ValueError(f"字幕时间重叠或倒序: {line.id}")
        end_ms = start_ms + duration_ms
        subtitles.append(
            {
                "id": line.id,
                "text": line.text,
                "start": round(start_ms / 1000, 3),
                "end": round(end_ms / 1000, 3),
                "highlight": manifest.theme,
            }
        )
        previous_end_ms = end_ms
    return subtitles
