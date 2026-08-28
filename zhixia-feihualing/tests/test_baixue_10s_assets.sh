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
from zhixia_tts_manifest import load_episode_manifest, load_voice_config


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
assert all("start_ms" not in line for line in raw["lines"])
assert all("gap_before_ms" not in line for line in raw["lines"])

audio_dir = project_dir / "assets" / "audio" / "baixue"
assert not audio_dir.exists()

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
assert "预计产生豆包 TTS 调用：4 次" in preview
assert "待生成：4 句" in preview
assert "阿砚：1 句" in preview
assert "栀夏：3 句" in preview
assert "当前为预览模式，未调用语音接口。" in preview
assert not audio_dir.exists()

print("PASS: Baixue 10s manifest and offline preview are consistent")
PY
