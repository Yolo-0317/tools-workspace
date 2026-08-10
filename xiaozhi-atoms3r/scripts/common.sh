#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "$ROOT/.env"
  set +a
fi

: "${IDF_PATH:=$ROOT/.espressif/esp-idf-v6.0.2}"
: "${XIAOZHI_FIRMWARE_DIR:=$ROOT/firmware}"
: "${XIAOZHI_BOARD:=atoms3r-cam-m12-echo-base}"
: "${ESPPORT:=}"

export IDF_PATH
export XIAOZHI_FIRMWARE_DIR
export XIAOZHI_BOARD
export ESPPORT

require_idf() {
  if [[ ! -f "$IDF_PATH/export.sh" ]]; then
    echo "ESP-IDF not found at: $IDF_PATH" >&2
    echo "Run: bash scripts/install-idf.sh" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  source "$IDF_PATH/export.sh"
}

require_firmware() {
  if [[ ! -d "$XIAOZHI_FIRMWARE_DIR/.git" ]]; then
    echo "xiaozhi-esp32 firmware not found at: $XIAOZHI_FIRMWARE_DIR" >&2
    echo "Run: bash scripts/setup.sh" >&2
    exit 1
  fi
}
