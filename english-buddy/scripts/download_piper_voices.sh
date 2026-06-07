#!/usr/bin/env bash
# Download Piper ONNX voices into voices/piper/ (one-time, offline TTS).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r backend/requirements.txt

export PYTHONPATH="$ROOT/backend"
python3 << 'PY'
from pathlib import Path
import shutil
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parent if False else Path.cwd()
PIPER = ROOT / "voices" / "piper"

VOICES = {
    # Elsa：Amy medium — 年轻女声；synthesis.json 提速 + 提音高（轻快明亮）
    "elsa": ("en/en_US/amy/medium", "en_US-amy-medium"),
    # Ultra teacher: Ryan — US male hero narrator
    "ultra": ("en/en_US/ryan/medium", "en_US-ryan-medium"),
}

for slot, (hf_dir, name) in VOICES.items():
    out = PIPER / slot
    out.mkdir(parents=True, exist_ok=True)
    onnx_src = hf_hub_download(
        repo_id="rhasspy/piper-voices",
        filename=f"{hf_dir}/{name}.onnx",
    )
    json_src = hf_hub_download(
        repo_id="rhasspy/piper-voices",
        filename=f"{hf_dir}/{name}.onnx.json",
    )
    shutil.copy2(onnx_src, out / f"{name}.onnx")
    shutil.copy2(json_src, out / f"{name}.onnx.json")
    print(f"OK {slot} -> {out / name}")

print("Done. Set TTS_ENGINE=piper in .env and restart backend.")
PY
