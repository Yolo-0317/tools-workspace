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
export IDF_TOOLS_PATH="${IDF_TOOLS_PATH:-$ROOT/.espressif/tools}"
require_idf

FLASH_ARGS=()
if [[ -n "$ESPPORT" ]]; then
  FLASH_ARGS+=(-p "$ESPPORT")
fi

echo "Enter download mode: hold RESET ~2s until green LED, then release."
echo "Flashing..."
idf.py "${FLASH_ARGS[@]}" flash

echo "Done. Press RESET once to reboot."
