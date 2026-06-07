#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
LABEL="com.user.english-buddy"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${AGENTS_DIR}/${LABEL}.plist"

chmod +x "${ROOT}/scripts/launchd-run.sh" "${ROOT}/scripts/dev-backend.sh" "${ROOT}/scripts/dev-frontend.sh"
mkdir -p "${ROOT}/logs" "${AGENTS_DIR}"

if [[ ! -f "${SRC}" ]]; then
  echo "Error: missing ${SRC}" >&2
  exit 1
fi

cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"
echo "已加载 launchd: ${DST}"
echo "日志: ${ROOT}/logs/launchd.out.log / launchd.err.log"
echo "本机: curl -s http://127.0.0.1:18787/api/health"
echo "公网: https://hub.yoloworld.site:8883/english/"
echo ""
echo "Caddy 改后须: cd sidestore-infra && docker compose restart caddy"
echo "卸载: launchctl bootout gui/$(id -u) ${DST} && rm ${DST}"
