#!/usr/bin/env bash
# launchd 常驻 SillyTavern — Caddy hub /silly/* 反代
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

mkdir -p "$ROOT/logs"

if [[ ! -d "$ROOT/vendor/SillyTavern" ]]; then
  echo "[$(date '+%F %T')] ERROR: 未安装，先运行 bash scripts/install.sh" >&2
  exit 1
fi

bash "$ROOT/scripts/patch-hub-subpath.sh" >/dev/null 2>&1 || true
bash "$ROOT/scripts/patch-hub-proxy.sh" >/dev/null 2>&1 || true
bash "$ROOT/scripts/configure-hub-external.sh" >/dev/null 2>&1 || true

echo "[$(date '+%F %T')] sillytavern 启动 ${ST_LISTEN:-127.0.0.1}:${ST_PORT:-8792}" >&2
exec bash "$ROOT/scripts/start.sh"
