#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
LABEL="com.user.home-hub"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${AGENTS_DIR}/${LABEL}.plist"

chmod +x "${ROOT}/scripts/home-hub-autostart.sh" "${ROOT}/scripts/launchd-run.sh" "${ROOT}/scripts/start.sh" "${ROOT}/scripts/restart.sh"
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
echo "验证: launchctl list | grep home-hub && curl -s http://127.0.0.1:8780/api/health"
echo ""
echo "公网: 先在 sidestore-infra 执行 ./scripts/setup-home-hub-auth.sh 并重签证书含 hub 子域"
echo "卸载: launchctl bootout gui/$(id -u) ${DST} && rm ${DST}"
