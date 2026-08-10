#!/usr/bin/env bash
# Smoke test: WS text turn -> Quark story playback (no microphone).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

TEXT="${1:-想听儿童故事}"
URL="${WS_URL:-ws://127.0.0.1:8765}"
TOKEN="${TOKEN:-demo-token}"

python - <<PY
import asyncio
import json
import uuid
import websockets

URL = "$URL"
TOKEN = "$TOKEN"
TEXT = """$TEXT"""

async def main():
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Protocol-Version": "1",
        "Device-Id": "smoke:mac:test",
        "Client-Id": str(uuid.uuid4()),
    }
    opus = 0
    async with websockets.connect(URL, additional_headers=headers, max_size=8*1024*1024) as ws:
        await ws.send(json.dumps({
            "type": "hello", "version": 1, "features": {"mcp": True},
            "transport": "websocket",
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
        }))
        hello = json.loads(await ws.recv())
        sid = hello["session_id"]
        await ws.send(json.dumps({"session_id": sid, "type": "listen", "state": "start", "mode": "manual"}))
        await ws.send(json.dumps({"session_id": sid, "type": "listen", "state": "stop", "text": TEXT}))
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=180)
            if isinstance(msg, bytes):
                opus += 1
                if opus >= 30:
                    print(f"OK: received {opus}+ opus packets for {TEXT!r}")
                    return
            else:
                data = json.loads(msg)
                if data.get("type") == "tts" and data.get("state") == "sentence_start":
                    print("TTS:", data.get("text", ""))
                if data.get("type") == "tts" and data.get("state") == "stop" and opus == 0:
                    raise SystemExit("FAIL: tts stopped without opus downlink")

asyncio.run(main())
PY
