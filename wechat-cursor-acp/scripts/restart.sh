#!/usr/bin/env bash
# Stop + start daemon (background). Exits immediately after daemon is up.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

"${SCRIPT_DIR}/stop.sh"
"${SCRIPT_DIR}/start.sh"
