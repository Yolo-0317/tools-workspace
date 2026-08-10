#!/usr/bin/env bash
# Voice demo: same WebSocket + Opus path as AtomS3R / Echo Base hardware.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  bash scripts/install.sh
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! curl -sf "http://127.0.0.1:${HTTP_PORT:-8766}/health" >/dev/null 2>&1; then
  echo "Starting gateway (WS + HTTP OTA + Quark stream)..."
  python server/main.py &
  SERVER_PID=$!
  trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
  for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${HTTP_PORT:-8766}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
else
  echo "Gateway already running on :${HTTP_PORT:-8766}"
  SERVER_PID=""
fi

LAN_IP="$(python - <<'PY'
from server.config import settings
print(settings.lan_ip)
PY
)"

echo ""
echo "=== 小智语音 Demo（Mac 模拟物理设备）==="
echo "WebSocket : ws://127.0.0.1:${WS_PORT:-8765}"
echo "真机 OTA   : http://${LAN_IP}:${HTTP_PORT:-8766}/xiaozhi/ota/"
echo "协议       : hello / listen / Opus 16k 上行 / 24k 下行"
echo ""
echo "试试说：想听儿童故事 / 想听冰雪奇缘 / 你好小智"
echo "文字调试：t + 回车"
echo ""

exec python client/sim_device.py --url "ws://127.0.0.1:${WS_PORT:-8765}" "$@"
