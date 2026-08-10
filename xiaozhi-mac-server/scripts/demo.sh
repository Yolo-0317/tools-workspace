#!/usr/bin/env bash
# Start server in background, run sim client in foreground, then cleanup.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  bash scripts/install.sh
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python server/main.py &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

sleep 2
echo "Server PID=$SERVER_PID — opening sim device (q to quit)"
python client/sim_device.py "$@"
