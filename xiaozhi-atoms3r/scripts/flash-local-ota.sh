#!/usr/bin/env bash
# Rebuild AtomS3R(+Pyramid) firmware with OTA pointing at local xiaozhi-mac-server, then flash.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAC_SERVER="$(cd "$ROOT/../xiaozhi-mac-server" && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
[[ -f .env ]] && source .env

BOARD="${XIAOZHI_BOARD:-atoms3r-echo-pyramid}"
HTTP_PORT="${HTTP_PORT:-8766}"

if [[ -d "$MAC_SERVER/.venv" ]]; then
  LAN_IP="$("$MAC_SERVER/.venv/bin/python" -c 'from server.config import settings; print(settings.lan_ip)' 2>/dev/null || true)"
fi
if [[ -z "${LAN_IP:-}" ]]; then
  LAN_IP="$(python3 - <<'PY'
import socket
s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("8.8.8.8", 80))
    print(s.getsockname()[0])
finally:
    s.close()
PY
)"
fi

OTA_URL="${XIAOZHI_OTA_URL:-http://${LAN_IP}:${HTTP_PORT}/xiaozhi/ota/}"
echo "Board : $BOARD"
echo "OTA   : $OTA_URL"

CFG_JSON="$ROOT/firmware/main/boards/${BOARD}/config.json"
if [[ ! -f "$CFG_JSON" ]]; then
  echo "Missing board config: $CFG_JSON" >&2
  exit 1
fi

python3 - <<PY
import json
from pathlib import Path
path = Path("$CFG_JSON")
data = json.loads(path.read_text())
ota = 'CONFIG_OTA_URL="$OTA_URL"'
for build in data.get("builds", []):
    append = list(build.get("sdkconfig_append") or [])
    append = [x for x in append if not str(x).startswith("CONFIG_OTA_URL=")]
    append.append(ota)
    build["sdkconfig_append"] = append
path.write_text(json.dumps(data, indent=4) + "\n")
print("Updated", path)
PY

rm -f firmware/releases/v*_atoms3r-echo-pyramid.zip firmware/releases/v*_${BOARD}.zip 2>/dev/null || true
bash scripts/build.sh
bash scripts/flash.sh

echo
echo "Done. Ensure mac-server is running:"
echo "  cd $MAC_SERVER && bash scripts/run-quark-voice-stack.sh"
echo "Then reboot device (Pyramid bottom USB power). It should pull WS from:"
echo "  $OTA_URL"
