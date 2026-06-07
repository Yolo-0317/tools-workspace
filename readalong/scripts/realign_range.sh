#!/usr/bin/env bash
# Re-run align + zh attach for a chapter range (Whisper cache reused).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOOK="${BOOK:-hp01}"
FROM="${1:?usage: realign_range.sh <from> [to]}"
TO="${2:-$FROM}"

cd "$ROOT"
if [[ -d "$ROOT/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
elif [[ -d "$ROOT/../english-buddy/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/../english-buddy/.venv/bin/activate"
fi

for ch in $(seq "$FROM" "$TO"); do
  pad="$(printf '%02d' "$ch")"
  echo "=== ${BOOK} ch${pad} align ==="
  BOOK="$BOOK" python3 scripts/align_words.py --chapter "$ch"
  python3 scripts/attach_translation.py --book "$BOOK" --chapter "$ch"
done
python3 scripts/build_catalog.py
echo "Done realign ${BOOK} ch$(printf '%02d' "$FROM")-$(printf '%02d' "$TO")"
