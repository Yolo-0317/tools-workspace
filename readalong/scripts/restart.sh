#!/usr/bin/env bash
# Restart readalong launchd service (reload serve.py / dict API).
set -euo pipefail
LABEL="com.user.readalong"
LAUNCHD_UID="$(id -u)"
launchctl kickstart -k "gui/${LAUNCHD_UID}/${LABEL}" 2>/dev/null || {
  echo "launchd job not loaded; starting manually…" >&2
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  exec python3 "$ROOT/scripts/serve.py"
}
