#!/usr/bin/env bash
set -euo pipefail

SIDESTORE_HOME="${SIDESTORE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$SIDESTORE_HOME"

set -a
# shellcheck disable=SC1091
source "$SIDESTORE_HOME/.env" 2>/dev/null || true
set +a

INTERNAL_PORT="${INTERNAL_HTTPS_PORT:-8443}"
EXTERNAL_PORT="${EXTERNAL_HTTPS_PORT:-8883}"
ANI_URL="https://ani.yoloworld.site:${EXTERNAL_PORT}/"
CONFIG_URL="https://config.yoloworld.site:${EXTERNAL_PORT}/servers.json"

FAIL=0

check() {
  local name="$1"
  shift
  if "$@"; then
    echo "OK  $name"
  else
    echo "FAIL $name"
    FAIL=1
  fi
}

echo "== SideStore Health Check (内网 :${INTERNAL_PORT} / 公网 :${EXTERNAL_PORT}) =="
echo

check "Docker anisette container" bash -c "docker ps --format '{{.Names}}' | grep -q '^sidestore-anisette$'"
check "Docker caddy container" bash -c "docker ps --format '{{.Names}}' | grep -q '^sidestore-caddy$'"
check "TLS cert files" test -f "$SIDESTORE_HOME/certs/fullchain.cer"

if curl -sf "http://127.0.0.1:6969/" | grep -q 'X-Apple-I-MD'; then
  echo "OK  anisette localhost"
else
  echo "FAIL anisette localhost"
  FAIL=1
fi

if curl -sf --max-time 5 --resolve "ani.yoloworld.site:${INTERNAL_PORT}:127.0.0.1" "https://ani.yoloworld.site:${INTERNAL_PORT}/" | grep -q 'X-Apple-I-MD'; then
  echo "OK  anisette HTTPS 内网 :${INTERNAL_PORT}"
else
  echo "FAIL anisette HTTPS 内网 :${INTERNAL_PORT}"
  FAIL=1
fi

if curl -sf --max-time 5 --resolve "config.yoloworld.site:${INTERNAL_PORT}:127.0.0.1" "https://config.yoloworld.site:${INTERNAL_PORT}/servers.json" | grep -q 'Yolo Home Anisette'; then
  echo "OK  servers.json HTTPS 内网 :${INTERNAL_PORT}"
else
  echo "FAIL servers.json HTTPS 内网 :${INTERNAL_PORT}"
  FAIL=1
fi

SUB_DOMAIN="${SUB_SUBDOMAIN:-sub}.${DOMAIN:-yoloworld.site}"
if curl -sf --max-time 15 --resolve "${SUB_DOMAIN}:${INTERNAL_PORT}:127.0.0.1" "https://${SUB_DOMAIN}:${INTERNAL_PORT}/clash.yaml" | grep -q 'mixed-port:'; then
  echo "OK  clash.yaml HTTPS 内网 :${INTERNAL_PORT}"
else
  echo "FAIL clash.yaml HTTPS 内网 :${INTERNAL_PORT} (检查证书 SAN 是否含 ${SUB_DOMAIN})"
  FAIL=1
fi

if curl -sfk --max-time 8 "$ANI_URL" 2>/dev/null | grep -q 'X-Apple-I-MD'; then
  echo "OK  anisette HTTPS 公网 :${EXTERNAL_PORT}"
else
  echo "WARN anisette HTTPS 公网 :${EXTERNAL_PORT} (路由器 ${EXTERNAL_PORT}->${INTERNAL_PORT} 可能未配置)"
fi

if curl -sfk --max-time 8 "$CONFIG_URL" 2>/dev/null | grep -q 'Yolo Home Anisette'; then
  echo "OK  servers.json HTTPS 公网 :${EXTERNAL_PORT}"
else
  echo "WARN servers.json HTTPS 公网 :${EXTERNAL_PORT} (路由器 ${EXTERNAL_PORT}->${INTERNAL_PORT} 可能未配置)"
fi

ANI_IP=$(dig +short ani.yoloworld.site 2>/dev/null | tail -1)
CONFIG_IP=$(dig +short config.yoloworld.site 2>/dev/null | tail -1)
PUBLIC_IP=$(curl -4 -sf --max-time 8 http://ifconfig.me/ip 2>/dev/null || true)
echo
echo "DNS ani.yoloworld.site     -> ${ANI_IP:-未知}"
echo "DNS config.yoloworld.site  -> ${CONFIG_IP:-未知}"
echo "当前公网 IP                -> ${PUBLIC_IP:-未知}"
echo "路由器应映射               -> 外网 ${EXTERNAL_PORT} -> Mac ${INTERNAL_PORT}"

JELLYFIN_STACK="${JELLYFIN_STACK:-$HOME/docker/jellyfin-stack}"
if [[ -x "$JELLYFIN_STACK/scripts/verify-playback.sh" ]]; then
  echo
  if bash "$JELLYFIN_STACK/scripts/verify-playback.sh"; then
    :
  else
    FAIL=1
  fi
fi

exit "$FAIL"
