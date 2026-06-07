#!/usr/bin/env bash
# 在 Mac 上运行 dnsmasq，为局域网提供 ani/config/hub 的 split DNS（iPhone WiFi 自定义 DNS 指向本机即可）
set -euo pipefail

SIDESTORE_HOME="$(cd "$(dirname "$0")/.." && pwd)"
CONF_DIR="${SIDESTORE_HOME}/config/dnsmasq"
CONF_FILE="${CONF_DIR}/sidestore.conf"
MARKER="# sidestore-infra lan dnsmasq"

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
  echo "无法检测局域网 IP；可 export LAN_IP=192.168.x.x 后重试" >&2
  exit 1
fi

if ! command -v dnsmasq >/dev/null 2>&1; then
  echo "未找到 dnsmasq，正在通过 Homebrew 安装..."
  if ! command -v brew >/dev/null 2>&1; then
    echo "请先安装 Homebrew，或手动: brew install dnsmasq" >&2
    exit 1
  fi
  brew install dnsmasq
fi

DNSMASQ_BIN="$(command -v dnsmasq)"
mkdir -p "${CONF_DIR}"

{
  echo "${MARKER}"
  echo "listen-address=${LAN_IP}"
  echo "bind-dynamic"
  echo "no-resolv"
  echo "server=223.5.5.5"
  echo "server=114.114.114.114"
  echo "local=/mask.icloud.com/"
  echo "local=/mask-h2.icloud.com/"
  for sub in "${SUBDOMAINS[@]}"; do
    echo "address=/${sub}.${DOMAIN}/${LAN_IP}"
  done
  echo "log-queries"
  echo "log-facility=/tmp/dnsmasq-sidestore.log"
} >"${CONF_FILE}"

echo "已写入 ${CONF_FILE}"
if pgrep -f "conf-file=${CONF_FILE}" >/dev/null 2>&1; then
  sudo pkill -f "conf-file=${CONF_FILE}" || true
  sleep 1
fi

sudo "${DNSMASQ_BIN}" --conf-file="${CONF_FILE}"
sleep 1

if ! pgrep -f "conf-file=${CONF_FILE}" >/dev/null 2>&1; then
  echo "dnsmasq 启动失败" >&2
  exit 1
fi

echo
echo "OK dnsmasq 已在 ${LAN_IP}:53 监听"
echo "iPhone：设置 → Wi‑Fi → (i) → 配置 DNS → 手动 → 添加 ${LAN_IP}，删除其它 DNS"
echo
echo "验证（本机）："
for sub in "${SUBDOMAINS[@]}"; do
  fqdn="${sub}.${DOMAIN}"
  resolved="$(dig +short "${fqdn}" @"${LAN_IP}" 2>/dev/null | tail -1 || true)"
  echo "  ${fqdn} @${LAN_IP} → ${resolved:-失败}"
done
