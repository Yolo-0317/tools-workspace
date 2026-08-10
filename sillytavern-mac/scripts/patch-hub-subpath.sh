#!/usr/bin/env bash
# 本地直连须 base href="/"；Hub 经 Caddy 从根路径加载 /style.css、/scripts 等（见 sidestore-infra Caddyfile @st_hub_paths）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor/SillyTavern"
BASE="${ST_BASE_HREF:-/}"

if [[ ! -d "$VENDOR/public" ]]; then
  echo "错误: 未安装 SillyTavern（vendor/SillyTavern 不存在）"
  exit 1
fi

for f in index.html login.html; do
  fp="$VENDOR/public/$f"
  if [[ -f "$fp" ]]; then
    sed -i '' "s|<base href=\"[^\"]*\">|<base href=\"${BASE}\">|g" "$fp"
    echo "已 patch: $f -> base href=\"${BASE}\""
  fi
done
