#!/usr/bin/env bash
# 内网 split DNS：让本机 hub.yoloworld.site 指向局域网 IP（避免 DNS→公网 IP 无法回流）
set -euo pipefail

SIDESTORE_HOME="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${HUB_SUBDOMAIN:-hub}.${DOMAIN:-yoloworld.site}"
HOSTS_FILE="/etc/hosts"
MARKER="# sidestore-infra hub local dns"

lan_ip() {
  ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true
}

LAN_IP="${LAN_IP:-$(lan_ip)}"
if [[ -z "${LAN_IP}" ]]; then
  echo "无法检测局域网 IP（en0/en1）" >&2
  exit 1
fi

LINE="${LAN_IP} ${DOMAIN} ${MARKER}"

if grep -qF "${MARKER}" "${HOSTS_FILE}" 2>/dev/null; then
  sudo sed -i '' "/${MARKER//\//\\/}/d" "${HOSTS_FILE}"
fi

echo "写入 ${HOSTS_FILE}: ${LINE}"
echo "${LINE}" | sudo tee -a "${HOSTS_FILE}" >/dev/null
sudo dscacheutil -flushcache 2>/dev/null || true
sudo killall -HUP mDNSResponder 2>/dev/null || true

echo "OK 本机 ${DOMAIN} → ${LAN_IP}"
echo "内网其它设备请在路由器添加「本地 DNS / hosts」：${DOMAIN} → ${LAN_IP}"
