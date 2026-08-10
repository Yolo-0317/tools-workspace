#!/usr/bin/env bash
# Rebuild + flash with official xiaozhi.me OTA (cloud dialogue + HTTP story play).
# Pair with Mac: com.user.xiaozhi-media + mcp_pipe (see xiaozhi-mac-server/scripts/run-media-stack.sh --with-mcp).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
[[ -f .env ]] && source .env

BOARD="${XIAOZHI_BOARD:-atoms3r-echo-pyramid}"
OTA_URL="${XIAOZHI_OTA_URL:-https://api.tenclass.net/xiaozhi/ota/}"
echo "Board : $BOARD"
echo "OTA   : $OTA_URL (official cloud)"

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

# Keep large-app partition for HTTP MP3 on Pyramid (do not wipe other appends).
rm -f firmware/releases/v*_atoms3r-echo-pyramid.zip firmware/releases/v*_${BOARD}.zip 2>/dev/null || true
bash scripts/build.sh
bash scripts/flash.sh

echo
echo "Done. Device should WS to xiaozhi.me (not local :8765)."
echo "Mac: media launchd + bash scripts/run-media-stack.sh --with-mcp"
echo "Console: bind device + paste role prompt from docs/CLOUD_HTTP_AGENT_PROMPT.md"
