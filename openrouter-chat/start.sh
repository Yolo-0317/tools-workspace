#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export CHAT_HOST="${CHAT_HOST:-127.0.0.1}"
export CHAT_PORT="${CHAT_PORT:-8795}"
export PYTHONUNBUFFERED=1
exec python3 "$ROOT/server.py"
