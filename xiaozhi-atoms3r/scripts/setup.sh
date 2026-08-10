#!/usr/bin/env bash
# 拉取 78/xiaozhi-esp32 固件源码
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/common.sh"

FW_DIR="$XIAOZHI_FIRMWARE_DIR"
if [[ "$FW_DIR" != /* ]]; then
  FW_DIR="$ROOT/$FW_DIR"
fi

if [[ -d "$FW_DIR/.git" ]]; then
  echo "Firmware already cloned: $FW_DIR"
  git -C "$FW_DIR" fetch --depth 1 origin main
  git -C "$FW_DIR" checkout main
  git -C "$FW_DIR" pull --ff-only origin main || true
  exit 0
fi

echo "Cloning xiaozhi-esp32 -> $FW_DIR"
git clone --depth 1 https://github.com/78/xiaozhi-esp32.git "$FW_DIR"

echo
echo "Firmware ready. Board: $XIAOZHI_BOARD"
echo "Next: bash scripts/install-idf.sh   # if ESP-IDF not installed"
echo "      bash scripts/build.sh"
