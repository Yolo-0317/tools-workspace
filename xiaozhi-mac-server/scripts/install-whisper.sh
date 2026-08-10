#!/usr/bin/env bash
# Download faster-whisper-tiny for xiaozhi-mac-server (hf-mirror, standalone cache).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL="${WHISPER_HUB_NAME:-base}"
CACHE_DIR="${WHISPER_CACHE:-$HOME/.cache/xiaozhi-whisper-${MODEL}}"
BASE="https://hf-mirror.com/Systran/faster-whisper-${MODEL}/resolve/main"

mkdir -p "$CACHE_DIR"
echo ">>> Target: $CACHE_DIR"
echo ">>> Source: $BASE (hf-mirror direct, no proxy)"

download() {
  local f="$1"
  local out="$CACHE_DIR/$f"
  if [[ -f "$out" ]] && [[ "$f" != "model.bin" ]]; then
    echo ">>> skip $f (exists)"
    return 0
  fi
  echo ">>> $f"
  curl -fL --retry 5 --retry-delay 3 -C - -o "$out" "$BASE/$f"
}

download config.json
download tokenizer.json
download vocabulary.txt
download model.bin

echo ">>> Files:"
ls -lh "$CACHE_DIR"

if [[ ! -d .venv ]]; then
  echo "Run bash scripts/install.sh first" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo ">>> Verify load..."
WHISPER_MODEL="$CACHE_DIR" python - <<PY
from faster_whisper import WhisperModel
import os
p = os.path.expanduser("$CACHE_DIR")
WhisperModel(p, device="cpu", compute_type="int8")
print("Whisper OK:", p)
PY

echo ">>> Set in .env: WHISPER_MODEL=$CACHE_DIR"
