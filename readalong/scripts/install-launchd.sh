#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
LABEL="com.user.readalong"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${AGENTS_DIR}/${LABEL}.plist"

chmod +x "${ROOT}/scripts/launchd-run.sh" "${ROOT}/scripts/serve.py" "${ROOT}/scripts/pipeline.sh"
mkdir -p "${ROOT}/logs" "${AGENTS_DIR}"

cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"
echo "已加载 launchd: ${DST}"
echo "本机: http://127.0.0.1:8791/web/"
echo "公网: https://hub.yoloworld.site:8883/readalong/web/"
echo ""
echo "Caddy 改后须: cd sidestore-infra && docker compose restart caddy"
