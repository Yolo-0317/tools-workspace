#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PY:-/opt/homebrew/bin/python3.12}"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3.12 || command -v python3)"
fi

echo "[1/5] System deps (opus for opuslib, ffmpeg libs for PyAV)..."
if command -v brew &>/dev/null; then
  # Cursor Agent 沙箱会改写 HOMEBREW_CACHE，导致 formula.jws.json 损坏；本机终端安装须用用户缓存。
  export HOMEBREW_CACHE="${HOMEBREW_CACHE:-$HOME/Library/Caches/Homebrew}"
  brew list opus &>/dev/null || brew install opus
  if ! brew list ffmpeg &>/dev/null; then
    bash "$ROOT/scripts/install-ffmpeg.sh" || echo "  ffmpeg install failed; run: bash scripts/install-ffmpeg.sh"
  fi
else
  echo "  Homebrew not found; ensure libopus is installed for opuslib"
fi

echo "[2/5] Python venv -> $ROOT/.venv"
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip wheel
pip install -r requirements.txt

echo "[3/5] Config"
cp -n .env.example .env 2>/dev/null || true

echo "[4/5] Whisper ASR (optional, for voice)"
if [[ -x "$ROOT/scripts/install-whisper.sh" ]]; then
  if [[ ! -f "${WHISPER_CACHE:-$HOME/.cache/xiaozhi-whisper-tiny}/model.bin" ]]; then
    bash "$ROOT/scripts/install-whisper.sh" || echo "  whisper download failed; run: bash scripts/install-whisper.sh"
  else
    echo "  whisper cache OK"
  fi
fi

echo "[5/5] Ollama model (optional, for LLM replies)"
if command -v ollama &>/dev/null; then
  if ! ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL:-qwen2.5:0.5b}"; then
    ollama pull "${OLLAMA_MODEL:-qwen2.5:0.5b}" || echo "  ollama pull failed; text replies will use fallback"
  fi
else
  echo "  ollama not found; install from https://ollama.com"
fi

echo "[6/6] Done"
echo "  Start server:  bash scripts/run-server.sh"
echo "  Sim device:    bash scripts/run-sim.sh"
echo "  One-shot demo: bash scripts/demo.sh"
