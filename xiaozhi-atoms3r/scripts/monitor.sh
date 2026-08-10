#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/common.sh"

require_firmware
require_idf

FW_DIR="$XIAOZHI_FIRMWARE_DIR"
if [[ "$FW_DIR" != /* ]]; then
  FW_DIR="$ROOT/$FW_DIR"
fi

cd "$FW_DIR"
export IDF_TOOLS_PATH="${IDF_TOOLS_PATH:-$ROOT/.espressif/tools}"

MON_ARGS=()
if [[ -n "$ESPPORT" ]]; then
  MON_ARGS+=(-p "$ESPPORT")
fi

idf.py "${MON_ARGS[@]}" monitor
