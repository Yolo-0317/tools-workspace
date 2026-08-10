#!/usr/bin/env bash
# Regenerate PWA icons from picture/harryputter.jpeg
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/picture/harryputter.jpeg"
WEB="$ROOT/web"
if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC — copy your icon to picture/harryputter.jpeg" >&2
  exit 1
fi
sips -z 192 192 "$SRC" --out "$WEB/pwa-192.png" >/dev/null
sips -z 512 512 "$SRC" --out "$WEB/pwa-512.png" >/dev/null
sips -z 180 180 "$SRC" --out "$WEB/apple-touch-icon.png" >/dev/null
echo "Wrote web/pwa-{192,512}.png and apple-touch-icon.png"
