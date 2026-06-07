#!/usr/bin/env bash
# Download faster-whisper-small via hf-mirror (直连镜像；勿对 hf-mirror 走代理，易 SSL 失败).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE_DIR="${WHISPER_CACHE:-$HOME/.cache/faster-whisper-small}"
BASE="https://hf-mirror.com/Systran/faster-whisper-small/resolve/main"

mkdir -p "$CACHE_DIR"
echo ">>> Target: $CACHE_DIR"
echo ">>> Source: $BASE (no proxy — hf-mirror 直连)"

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

echo ">>> Verify load..."
cd "$ROOT"
WHISPER_MODEL="$CACHE_DIR" PYTHONPATH=backend .venv/bin/python -c "
import os
from faster_whisper import WhisperModel
p = os.path.expanduser('$CACHE_DIR')
m = WhisperModel(p, device='cpu', compute_type='int8')
print('Whisper OK:', p)
"
