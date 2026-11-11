#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"

python3 - "$project_dir" <<'PY'
from __future__ import annotations

import io
import json
import sys
from pathlib import Path


project_dir = Path(sys.argv[1])
sys.path.insert(0, str(project_dir / "scripts"))

from generate_episode_audio import run_cli
from zhixia_tts_manifest import (
    build_subtitles,
    load_episode_manifest,
    load_voice_config,
)


manifest_path = project_dir / "episodes" / "baixue" / "voice-lines.json"
voices = load_voice_config(project_dir / "config" / "voices.json")
manifest = load_episode_manifest(manifest_path, voices)

expected = [
    ("01-ayan-dialogue", "ayan", "梨花？"),
    ("02-zhixia-dialogue", "zhixia", "是新雪。"),
    ("03-zhixia-poem-one", "zhixia", "忽如一夜春风来。"),
    ("04-zhixia-poem-two", "zhixia", "千树万树梨花开。"),
]

assert manifest.episode == "baixue"
assert manifest.format == "one-poem-story"
assert [(line.id, line.role, line.text) for line in manifest.lines] == expected
assert all(line.revision == 1 for line in manifest.lines)
assert all(line.context_texts for line in manifest.lines)

raw = json.loads(manifest_path.read_text(encoding="utf-8"))
assert [line["start_ms"] for line in raw["lines"]] == [500, 1850, 3600, 6200]
assert all("gap_before_ms" not in line for line in raw["lines"])

audio_dir = project_dir / "assets" / "audio" / "baixue"
metadata = json.loads((audio_dir / "audio-metadata.json").read_text(encoding="utf-8"))
durations_ms = {line["id"]: line["duration_ms"] for line in metadata["lines"]}
assert durations_ms == {
    "01-ayan-dialogue": 1224,
    "02-zhixia-dialogue": 1632,
    "03-zhixia-poem-one": 2448,
    "04-zhixia-poem-two": 2832,
}
expected_subtitles = [
    {
        "id": "01-ayan-dialogue",
        "text": "梨花？",
        "start": 0.5,
        "end": 1.724,
        "highlight": "白雪",
    },
    {
        "id": "02-zhixia-dialogue",
        "text": "是新雪。",
        "start": 1.85,
        "end": 3.482,
        "highlight": "白雪",
    },
    {
        "id": "03-zhixia-poem-one",
        "text": "忽如一夜春风来。",
        "start": 3.6,
        "end": 6.048,
        "highlight": "白雪",
    },
    {
        "id": "04-zhixia-poem-two",
        "text": "千树万树梨花开。",
        "start": 6.2,
        "end": 9.032,
        "highlight": "白雪",
    },
]
assert build_subtitles(manifest, durations_ms) == expected_subtitles
subtitles_path = project_dir / "episodes" / "baixue" / "subtitles-baixue.json"
assert json.loads(subtitles_path.read_text(encoding="utf-8")) == expected_subtitles

stdout = io.StringIO()
stderr = io.StringIO()


def forbidden_client_factory(api_key: str) -> object:
    raise AssertionError("preview must not construct a TTS client")


code = run_cli(
    ["--episode", "baixue"],
    project_root=project_dir,
    client_factory=forbidden_client_factory,
    stdout=stdout,
    stderr=stderr,
    environ={},
)

assert code == 0
assert stderr.getvalue() == ""
preview = stdout.getvalue()
assert "预计产生豆包 TTS 调用：0 次" in preview
assert "待生成：0 句" in preview
assert "已就绪并跳过：4 句" in preview
assert "当前为预览模式，未调用语音接口。" in preview

print("PASS: Baixue 10s audio timeline and offline preview are consistent")
PY
