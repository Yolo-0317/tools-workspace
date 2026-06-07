#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CH="${1:?usage: pipeline.sh <chapter_num>}"
CH_PAD="$(printf '%02d' "$CH")"

cd "$ROOT"
mkdir -p output samples

if [[ ! -f "samples/book.epub" || ! -f "samples/chapter${CH_PAD}.mp3" ]]; then
  echo "Missing samples/book.epub or samples/chapter${CH_PAD}.mp3" >&2
  exit 1
fi

if [[ -d "$ROOT/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
elif [[ -d "$ROOT/../english-buddy/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/../english-buddy/.venv/bin/activate"
fi

python3 scripts/extract_sentences.py --chapter "$CH" -o "output/ch${CH_PAD}_sentences.json"
python3 scripts/extract_chinese.py --chapter "$CH" -o "output/ch${CH_PAD}_zh.json"
python3 scripts/align_words.py --chapter "$CH"
python3 scripts/attach_translation.py --chapter "$CH"
echo "Done. Preview: python3 -m http.server 8791  →  http://127.0.0.1:8791/web/"
