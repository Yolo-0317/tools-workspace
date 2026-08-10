#!/usr/bin/env bash
# 通过本机代理安装 ffmpeg（依赖 bottle 通常已缓存，仅补 ffmpeg 本体）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/proxy-env.sh"

if brew list ffmpeg &>/dev/null; then
  echo "ffmpeg already installed: $(brew --prefix ffmpeg)/bin/ffmpeg"
  exit 0
fi

echo "Proxy: $PROXY_URL"
echo "HOMEBREW_CACHE: $HOMEBREW_CACHE"
echo "Fetching ffmpeg bottle via proxy..."

rm -f "$HOMEBREW_CACHE"/downloads/*ffmpeg*.incomplete 2>/dev/null || true

MAX_TRIES=3
for i in $(seq 1 "$MAX_TRIES"); do
  echo "--- attempt $i/$MAX_TRIES ---"
  if brew install ffmpeg; then
    echo "OK: $(/opt/homebrew/bin/ffmpeg -version | head -1)"
    exit 0
  fi
  echo "brew install failed, retry in 5s..."
  rm -f "$HOMEBREW_CACHE"/downloads/*ffmpeg*.incomplete 2>/dev/null || true
  sleep 5
done

echo "ffmpeg install failed after $MAX_TRIES attempts." >&2
echo "Try in terminal: proxy_on && bash scripts/install-ffmpeg.sh" >&2
exit 1
