#!/usr/bin/env bash
# Smoke test: Quark search -> resolve CDN URL -> HTTP Range proxy -> ffmpeg decode
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

KEYWORD="${1:-故事}"
echo "== search & resolve: $KEYWORD =="
python3 - <<PY
import asyncio
import json
from server.quark_client import QuarkClient
from server.http_stream import ffmpeg_available, iter_opus_from_http_source

client = QuarkClient.from_env()
if not client:
    raise SystemExit("QuarkClient unavailable (check QUARK_* paths and login)")

source = client.find_stream_source("$KEYWORD")
if not source:
    raise SystemExit("no audio match")

print(json.dumps({
    "filename": source.filename,
    "size": source.size,
    "url_len": len(source.download_url),
    "ffmpeg": ffmpeg_available(),
}, ensure_ascii=False, indent=2))

async def sniff():
    if not ffmpeg_available():
        print("WARN: ffmpeg missing; skip opus decode sniff")
        return
    count = 0
    async for packet in iter_opus_from_http_source(source):
        count += 1
        if count >= 5:
            break
    print(f"opus_packets={count} (first 5 frames OK)")

asyncio.run(sniff())
PY

echo "OK"
