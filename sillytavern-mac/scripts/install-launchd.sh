#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
LABEL="com.user.sillytavern"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${AGENTS_DIR}/${LABEL}.plist"

chmod +x "${ROOT}/scripts/launchd-run.sh" "${ROOT}/scripts/start.sh" "${ROOT}/scripts/patch-hub-subpath.sh"
mkdir -p "${ROOT}/logs" "${AGENTS_DIR}"

cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"
echo "已加载 launchd: ${DST}"
echo "本机: http://127.0.0.1:${ST_PORT:-8792}/"
echo "Hub:  https://hub.yoloworld.site:8883/silly/"
echo ""
echo "Caddy 改后须: cd sidestore-infra && docker compose restart caddy"
