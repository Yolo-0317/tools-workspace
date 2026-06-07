#!/usr/bin/env bash
# 内网 split DNS：本机 /etc/hosts 让 ani / config / hub 指向局域网 IP（避免公网 IP hairpin 失败）
set -euo pipefail

SIDESTORE_HOME="$(cd "$(dirname "$0")/.." && pwd)"
HOSTS_FILE="/etc/hosts"
MARKER="# sidestore-infra local dns"

set -a
# shellcheck disable=SC1091
source "$SIDESTORE_HOME/.env" 2>/dev/null || true
set +a

DOMAIN="${DOMAIN:-yoloworld.site}"
SUBDOMAINS=(
  "${ANI_SUBDOMAIN:-ani}"
  "${CONFIG_SUBDOMAIN:-config}"
  "${HUB_SUBDOMAIN:-hub}"
)

lan_ip() {
  ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true
}

LAN_IP="${LAN_IP:-$(lan_ip)}"
if [[ -z "${LAN_IP}" ]]; then
  echo "无法检测局域网 IP（en0/en1）；可 export LAN_IP=192.168.x.x 后重试" >&2
  exit 1
fi

if grep -qF "${MARKER}" "${HOSTS_FILE}" 2>/dev/null; then
  sudo sed -i '' "/${MARKER}/d" "${HOSTS_FILE}"
fi

# 兼容旧版仅 hub 的 marker
OLD_MARKER="# sidestore-infra hub local dns"
if grep -qF "${OLD_MARKER}" "${HOSTS_FILE}" 2>/dev/null; then
  sudo sed -i '' "/${OLD_MARKER}/d" "${HOSTS_FILE}"
fi

echo "写入 ${HOSTS_FILE}（${LAN_IP}）："
for sub in "${SUBDOMAINS[@]}"; do
  fqdn="${sub}.${DOMAIN}"
  line="${LAN_IP} ${fqdn} ${MARKER}"
  echo "  ${line}"
  echo "${line}" | sudo tee -a "${HOSTS_FILE}" >/dev/null
done

sudo dscacheutil -flushcache 2>/dev/null || true
sudo killall -HUP mDNSResponder 2>/dev/null || true

echo
echo "OK 本机以下域名 → ${LAN_IP}："
for sub in "${SUBDOMAINS[@]}"; do
  echo "  - ${sub}.${DOMAIN}"
done
echo
echo "iPhone / 其它内网设备（二选一）："
echo "  A) 路由器「本地 DNS / 静态 hosts」添加上述域名 → ${LAN_IP}"
echo "  B) 运行 bash scripts/setup-lan-dnsmasq.sh，iPhone WiFi DNS 手动设为 ${LAN_IP}"
