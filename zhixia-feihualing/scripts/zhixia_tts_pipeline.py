#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol

from zhixia_tts_client import AudioProbe, TTSRequest, TTSResult, probe_audio
from zhixia_tts_manifest import (
    EpisodeManifest,
    VoiceConfig,
    VoiceLine,
    audio_filename,
    build_subtitles,
)


class VersionConflict(RuntimeError):
    """An existing artifact cannot be overwritten safely."""


class TTSClient(Protocol):
    def synthesize(self, request: TTSRequest) -> TTSResult: ...


Probe = Callable[[Path], AudioProbe]


@dataclass(frozen=True)
class LineState:
    line: VoiceLine
    voice: VoiceConfig
    audio_path: Path
    status: str
    duration_ms: int | None = None


@dataclass(frozen=True)
class GenerationPlan:
    project_root: Path
    manifest: EpisodeManifest
    audio_dir: Path
    metadata_path: Path
    subtitle_path: Path
    ready: tuple[LineState, ...]
    pending: tuple[LineState, ...]
    conflicts: tuple[str, ...]
    total_characters: int

    @property
    def expected_api_calls(self) -> int:
        return len(self.pending)


def _read_metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"lines": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取配音元数据: {path}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
        raise ValueError(f"配音元数据格式无效: {path}")
    if not all(isinstance(item, dict) for item in data["lines"]):
        raise ValueError(f"配音元数据行格式无效: {path}")
    return data


def _records_by_id(metadata: Mapping[str, object]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    raw_lines = metadata.get("lines", [])
    if not isinstance(raw_lines, list):
        return records
    for item in raw_lines:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            records[item["id"]] = item
    return records


def _identity_matches(
    record: Mapping[str, object],
    line: VoiceLine,
    voice: VoiceConfig,
    filename: str,
) -> bool:
    return all(
        (
            record.get("id") == line.id,
            record.get("role") == line.role,
            record.get("text") == line.text,
            record.get("speaker") == voice.speaker,
            record.get("resource_id") == voice.resource_id,
            record.get("revision") == line.revision,
            record.get("filename") == filename,
        )
    )


def build_generation_plan(
    project_root: str | Path,
    manifest: EpisodeManifest,
    *,
    probe: Probe = probe_audio,
) -> GenerationPlan:
    root = Path(project_root)
    audio_dir = root / "assets" / "audio" / manifest.audio_slug
    metadata_path = audio_dir / "audio-metadata.json"
    subtitle_path = (
        root
        / "episodes"
        / manifest.episode
        / f"subtitles-{manifest.theme_slug}.json"
    )
    metadata = _read_metadata(metadata_path)
    records = _records_by_id(metadata)
    ready: list[LineState] = []
    pending: list[LineState] = []
    conflicts: list[str] = []

    for line in manifest.lines:
        voice = manifest.voices[line.role]
        filename = audio_filename(line)
        target = audio_dir / filename
        record = records.get(line.id)
        state = LineState(line, voice, target, "pending")

        if record is None:
            if target.exists():
                conflicts.append(
                    f"{line.id}: unmanaged target exists at {target}; "
                    "increase revision or move the file"
                )
            else:
                pending.append(state)
            continue

        if _identity_matches(record, line, voice, filename):
            if record.get("status") == "ready" and target.is_file():
                try:
                    info = probe(target)
                except (OSError, ValueError):
                    pending.append(state)
                else:
                    ready.append(
                        LineState(
                            line,
                            voice,
                            target,
                            "ready",
                            duration_ms=info.duration_ms,
                        )
                    )
            else:
                pending.append(state)
            continue

        old_revision = record.get("revision")
        if (
            isinstance(old_revision, int)
            and not isinstance(old_revision, bool)
            and line.revision > old_revision
            and not target.exists()
        ):
            pending.append(state)
            continue

        conflicts.append(
            f"{line.id}: content or voice changed without a safe revision bump; "
            "increase revision"
        )

    if conflicts:
        raise VersionConflict("; ".join(conflicts))

    return GenerationPlan(
        project_root=root,
        manifest=manifest,
        audio_dir=audio_dir,
        metadata_path=metadata_path,
        subtitle_path=subtitle_path,
        ready=tuple(ready),
        pending=tuple(pending),
        conflicts=(),
        total_characters=sum(len(state.line.text) for state in pending),
    )


def _atomic_write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(serialized)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_metadata_atomic(
    path: Path,
    manifest: EpisodeManifest,
    records: Mapping[str, Mapping[str, object]],
) -> None:
    ordered = [dict(records[line.id]) for line in manifest.lines if line.id in records]
    _atomic_write_json(
        path,
        {
            "episode": manifest.episode,
            "theme": manifest.theme,
            "audio_slug": manifest.audio_slug,
            "lines": ordered,
        },
    )


def write_subtitles_atomic(
    path: Path,
    manifest: EpisodeManifest,
    durations_ms: Mapping[str, int],
) -> None:
    subtitles = build_subtitles(manifest, durations_ms)
    desired = json.dumps(subtitles, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == desired:
                return
        except OSError as exc:
            raise ValueError(f"无法读取字幕文件: {path}") from exc
    _atomic_write_json(path, subtitles)


def _record_for(
    state: LineState,
    *,
    status: str,
    duration_ms: int | None = None,
    request_id: str | None = None,
    error: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "id": state.line.id,
        "role": state.line.role,
        "text": state.line.text,
        "speaker": state.voice.speaker,
        "resource_id": state.voice.resource_id,
        "revision": state.line.revision,
        "filename": state.audio_path.name,
        "status": status,
    }
    if duration_ms is not None:
        record["duration_ms"] = duration_ms
    if request_id:
        record["request_id"] = request_id
    if error:
        record["error"] = error
    return record


def generate_pending_lines(
    plan: GenerationPlan,
    client: TTSClient,
    *,
    probe: Probe = probe_audio,
) -> GenerationPlan:
    plan.audio_dir.mkdir(parents=True, exist_ok=True)
    records = _records_by_id(_read_metadata(plan.metadata_path))

    for state in plan.pending:
        temporary_path: Path | None = None
        try:
            result = client.synthesize(
                TTSRequest(
                    text=state.line.text,
                    speaker=state.voice.speaker,
                    resource_id=state.voice.resource_id,
                    uid=f"{plan.manifest.episode}-{state.line.id}",
                )
            )
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=plan.audio_dir,
                prefix=f".{state.audio_path.name}.",
                suffix=".tmp.mp3",
                delete=False,
            ) as temporary:
                temporary.write(result.audio)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            info = probe(temporary_path)
            os.replace(temporary_path, state.audio_path)
            temporary_path = None
            records[state.line.id] = _record_for(
                state,
                status="ready",
                duration_ms=info.duration_ms,
                request_id=result.request_id,
            )
            write_metadata_atomic(plan.metadata_path, plan.manifest, records)
        except Exception as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            records[state.line.id] = _record_for(
                state,
                status="failed",
                error=type(exc).__name__,
            )
            write_metadata_atomic(plan.metadata_path, plan.manifest, records)
            raise

    completed = build_generation_plan(
        plan.project_root,
        plan.manifest,
        probe=probe,
    )
    if not completed.pending:
        durations = {
            state.line.id: state.duration_ms
            for state in completed.ready
            if state.duration_ms is not None
        }
        write_subtitles_atomic(
            completed.subtitle_path,
            completed.manifest,
            durations,
        )
    return completed


__all__ = [
    "GenerationPlan",
    "LineState",
    "VersionConflict",
    "build_generation_plan",
    "generate_pending_lines",
    "write_metadata_atomic",
    "write_subtitles_atomic",
]
