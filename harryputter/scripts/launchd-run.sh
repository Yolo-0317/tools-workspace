#!/usr/bin/env bash
# launchd 常驻：静态站 :8791（Caddy hub /harryputter/* 反代，不经 Home Hub 登录）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HARRYPUTTER_PORT="${HARRYPUTTER_PORT:-${READALONG_PORT:-8791}}"
export HARRYPUTTER_HOST="${HARRYPUTTER_HOST:-${READALONG_HOST:-127.0.0.1}}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

# 外网试读：非内网 IP 仅开放第 1 章；登录 admin 可听全本
export HARRYPUTTER_MAX_PUBLIC_CHAPTER="${HARRYPUTTER_MAX_PUBLIC_CHAPTER:-${READALONG_MAX_PUBLIC_CHAPTER:-1}}"
export HARRYPUTTER_FULL_ACCESS_CIDRS="${HARRYPUTTER_FULL_ACCESS_CIDRS:-${READALONG_FULL_ACCESS_CIDRS:-127.,10.,192.168.,172.16.,::1}}"
export HARRYPUTTER_ADMIN_USER="${HARRYPUTTER_ADMIN_USER:-${READALONG_ADMIN_USER:-admin}}"
export HARRYPUTTER_COOKIE_PATH="${HARRYPUTTER_COOKIE_PATH:-${READALONG_COOKIE_PATH:-/}}"
export HARRYPUTTER_COOKIE_SECURE="${HARRYPUTTER_COOKIE_SECURE:-${READALONG_COOKIE_SECURE:-1}}"

mkdir -p logs

if [[ ! -f output/hp01/ch01.json ]]; then
  echo "[$(date '+%F %T')] WARN: output/hp01/ch01.json 缺失，先运行 BOOK=hp01 ./scripts/pipeline.sh 1" >&2
fi

echo "[$(date '+%F %T')] harryputter 启动 ${HARRYPUTTER_HOST}:${HARRYPUTTER_PORT}" >&2
exec python3 "$ROOT/scripts/serve.py"
