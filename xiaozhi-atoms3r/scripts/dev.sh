#!/usr/bin/env bash
# 开发迭代：menuconfig + build + flash + monitor
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

FLASH_ARGS=()
if [[ -n "$ESPPORT" ]]; then
  FLASH_ARGS+=(-p "$ESPPORT")
fi

echo "Opening menuconfig (Board: Xiaozhi Assistant -> Board Type -> AtomS3R CAM/M12 + Echo Base)"
idf.py menuconfig

idf.py build
echo "Enter download mode: hold RESET ~2s until green LED."
idf.py "${FLASH_ARGS[@]}" flash monitor
