#!/usr/bin/env bash
# Hub 反代后须关闭 forwarded IP 白名单（否则外网 X-Forwarded-For 触发 403）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$ROOT/vendor/SillyTavern/config.yaml"
[[ -f "$CFG" ]] || exit 0
sed -i '' 's/^enableForwardedWhitelist: true/enableForwardedWhitelist: false/' "$CFG"
grep -q '^enableForwardedWhitelist:' "$CFG" || echo 'enableForwardedWhitelist: false' >> "$CFG"
echo "config.yaml: enableForwardedWhitelist=false"
