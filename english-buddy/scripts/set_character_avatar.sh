#!/usr/bin/env bash
# Center-crop to square and resize to 512×512 for frontend/public/characters/{stem}.jpg
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PUBLIC="$ROOT/frontend/public/characters"
DIST="$ROOT/frontend/dist/characters"
SIZE="${AVATAR_SIZE:-512}"

usage() {
  echo "Usage: $0 <source-image> [stem]" >&2
  echo "  stem defaults to source basename without extension (e.g. elsa)" >&2
  exit 1
}

[[ $# -ge 1 ]] || usage
SRC="$1"
[[ -f "$SRC" ]] || { echo "Not a file: $SRC" >&2; exit 1; }

STEM="${2:-$(basename "$SRC" | sed 's/\.[^.]*$//')}"
STEM="${STEM%-source}"
WORK="$(mktemp -t avatar.XXXXXX).jpg"
OUT="$PUBLIC/${STEM}.jpg"

W=$(sips -g pixelWidth "$SRC" | awk '/pixelWidth:/ {print $2}')
H=$(sips -g pixelHeight "$SRC" | awk '/pixelHeight:/ {print $2}')
SIDE=$(( W < H ? W : H ))
OFF_X=$(( (W - SIDE) / 2 ))
OFF_Y=$(( (H - SIDE) / 2 ))

cp "$SRC" "$WORK"
sips -s format jpeg "$WORK" --out "$WORK" >/dev/null
sips -c "$SIDE" "$SIDE" --cropOffset "$OFF_Y" "$OFF_X" "$WORK" >/dev/null
sips -z "$SIZE" "$SIZE" "$WORK" --out "$OUT" >/dev/null
rm -f "$WORK"

if [[ -d "$DIST" ]]; then
  cp "$OUT" "$DIST/${STEM}.jpg"
  echo "Updated $OUT and $DIST/${STEM}.jpg (${SIZE}×${SIZE})"
else
  echo "Updated $OUT (${SIZE}×${SIZE}); run ./scripts/restart.sh --build for production dist"
fi
