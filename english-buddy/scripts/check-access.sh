#!/usr/bin/env bash
# 诊断 English Buddy 内网 / 外网 / hairpin 访问
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SIDESTORE="$(cd "$ROOT/../sidestore-infra" && pwd)"

set -a
# shellcheck disable=SC1091
source "$SIDESTORE/.env" 2>/dev/null || true
set +a

INTERNAL_PORT="${INTERNAL_HTTPS_PORT:-8443}"
EXTERNAL_PORT="${EXTERNAL_HTTPS_PORT:-8883}"
HUB="${HUB_SUBDOMAIN:-hub}.${DOMAIN:-yoloworld.site}"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
PUBLIC_IP="${DDNS_PUBLIC_IP:-$(curl -4 -sf --max-time 6 http://ifconfig.me/ip 2>/dev/null || true)}"
HEALTH_PATH="/english/api/health"
TMP="/tmp/eb-health-$$.json"

ok() { echo "OK   $*"; }
warn() { echo "WARN $*"; }
fail() { echo "FAIL $*"; }

probe() {
  local label="$1"
  local url="$2"
  shift 2
  local code
  code=$(curl -sk --max-time 8 -o "$TMP" -w "%{http_code}" "$@" "$url" 2>/dev/null || echo 000)
  if [[ "$code" == "200" ]] && grep -q '"ok"' "$TMP" 2>/dev/null; then
    ok "$label"
    return 0
  fi
  fail "$label (http=${code})"
  return 1
}

echo "== English Buddy 访问诊断 =="
echo "hub=${HUB}  LAN=${LAN_IP:-?}  公网IP=${PUBLIC_IP:-?}"
echo "内网 :${INTERNAL_PORT}  外网 :${EXTERNAL_PORT}"
echo

FAIL=0
probe "launchd 直连" "http://127.0.0.1:18787${HEALTH_PATH}" || FAIL=1

if [[ -n "${LAN_IP}" ]]; then
  probe "局域网 :${INTERNAL_PORT}" "https://${LAN_IP}:${INTERNAL_PORT}${HEALTH_PATH}" || FAIL=1
  probe "局域网 :${EXTERNAL_PORT}" "https://${LAN_IP}:${EXTERNAL_PORT}${HEALTH_PATH}" || FAIL=1
fi

probe "Caddy 本机" "https://${HUB}:${EXTERNAL_PORT}${HEALTH_PATH}" \
  --resolve "${HUB}:${EXTERNAL_PORT}:127.0.0.1" || FAIL=1

if grep -qF "sidestore-infra local dns" /etc/hosts 2>/dev/null || grep -qF "sidestore-infra hub local dns" /etc/hosts 2>/dev/null; then
  probe "域名 split DNS" "https://${HUB}:${EXTERNAL_PORT}${HEALTH_PATH}" || FAIL=1
else
  code=$(curl -sk --max-time 8 -o /dev/null -w "%{http_code}" \
    "https://${HUB}:${EXTERNAL_PORT}${HEALTH_PATH}" 2>/dev/null || echo 000)
  if [[ "$code" == "200" ]]; then
    ok "域名直连"
  else
    warn "域名直连失败 (http=${code}) — 在家 WiFi 多为 hairpin：DNS 指向公网 IP，内网回连失败"
    echo "      修复：bash ${SIDESTORE}/scripts/setup-local-dns.sh"
    echo "      临时：https://${LAN_IP:-<LAN_IP>}:${INTERNAL_PORT}/english/"
  fi
fi

if [[ -n "${PUBLIC_IP}" ]]; then
  code=$(curl -sk --max-time 8 -o /dev/null -w "%{http_code}" \
    "https://${PUBLIC_IP}:${EXTERNAL_PORT}${HEALTH_PATH}" 2>/dev/null || echo 000)
  if [[ "$code" == "200" ]]; then
    ok "公网 IP hairpin"
  else
    warn "公网 IP hairpin 不通 (http=${code}) — 不代表真外网不通"
  fi
  ext=$(curl -sf --max-time 12 \
    "https://api.networktools.dev/v1/port-test?port=${EXTERNAL_PORT}&ip=${PUBLIC_IP}" 2>/dev/null || true)
  if echo "$ext" | grep -q '"status":"OPEN"'; then
    ok "公网 TCP :${EXTERNAL_PORT} 第三方检测 = OPEN"
  elif echo "$ext" | grep -q '"status"'; then
    status=$(echo "$ext" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
    fail "公网 TCP :${EXTERNAL_PORT} = ${status}"
    echo "      修复：路由器 外网 ${EXTERNAL_PORT} → ${LAN_IP:-Mac}:${EXTERNAL_PORT}"
    FAIL=1
  else
    warn "公网端口检测跳过"
  fi
fi

rm -f "$TMP"
echo
echo "地址：内网 https://${LAN_IP:-192.168.x.x}:${INTERNAL_PORT}/english/"
echo "      外网 https://${HUB}:${EXTERNAL_PORT}/english/"
exit "$FAIL"
