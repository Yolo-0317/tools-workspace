#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/common.sh"

require_firmware

FW_DIR="$XIAOZHI_FIRMWARE_DIR"
if [[ "$FW_DIR" != /* ]]; then
  FW_DIR="$ROOT/$FW_DIR"
fi

cd "$FW_DIR"
# Must precede require_idf / export.sh (python_env under tools/).
export IDF_TOOLS_PATH="${IDF_TOOLS_PATH:-$ROOT/.espressif/tools}"
require_idf

echo "Building board: $XIAOZHI_BOARD"
python3 scripts/release.py "$XIAOZHI_BOARD"

echo
echo "Build complete. Firmware artifacts under:"
echo "  $FW_DIR/build/"
