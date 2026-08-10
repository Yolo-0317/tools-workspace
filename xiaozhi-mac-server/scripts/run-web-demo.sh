#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
echo "Open in browser: http://127.0.0.1:${HTTP_PORT:-8766}/demo/"
exec python server/main.py
