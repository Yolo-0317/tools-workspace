#!/usr/bin/env bash
# 用 acme.sh + 阿里云 DNS 签发证书（无需路由器映射 80/443）
set -euo pipefail

SIDESTORE_HOME="${SIDESTORE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$SIDESTORE_HOME"

# shellcheck disable=SC1091
source "$SIDESTORE_HOME/scripts/lib/env.sh"
load_aliyun_env

set -a
# shellcheck disable=SC1091
source "$SIDESTORE_HOME/.env"
set +a

: "${ALIBABA_CLOUD_ACCESS_KEY_ID:?请设置 ALIBABA_CLOUD_ACCESS_KEY_ID}"
: "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:?请设置 ALIBABA_CLOUD_ACCESS_KEY_SECRET}"
: "${ACME_EMAIL:?请在 .env 设置 ACME_EMAIL}"

mkdir -p "$SIDESTORE_HOME/certs"

ANI_DOMAIN="${ANI_SUBDOMAIN}.${DOMAIN}"
CONFIG_DOMAIN="${CONFIG_SUBDOMAIN}.${DOMAIN}"
ALIST_DOMAIN="${ALIST_SUBDOMAIN:-alist}.${DOMAIN}"
WWW_DOMAIN="${WWW_SUBDOMAIN:-www}.${DOMAIN}"
SUB_DOMAIN="${SUB_SUBDOMAIN:-sub}.${DOMAIN}"
HUB_DOMAIN="${HUB_SUBDOMAIN:-hub}.${DOMAIN}"
PHOTOS_DOMAIN="${PHOTOS_SUBDOMAIN:-photos}.${DOMAIN}"

export Ali_Key="$ALIBABA_CLOUD_ACCESS_KEY_ID"
export Ali_Secret="$ALIBABA_CLOUD_ACCESS_KEY_SECRET"

ACME_BIN="${ACME_BIN:-$HOME/.acme.sh/acme.sh}"
if [[ ! -x "$ACME_BIN" ]]; then
  echo "安装 acme.sh..."
  curl -fsSL https://get.acme.sh | sh -s "email=$ACME_EMAIL"
  ACME_BIN="$HOME/.acme.sh/acme.sh"
fi

echo "签发证书: ${ANI_DOMAIN}, ${CONFIG_DOMAIN}, ${ALIST_DOMAIN}, ${WWW_DOMAIN}, ${SUB_DOMAIN}, ${HUB_DOMAIN}, ${PHOTOS_DOMAIN} (DNS-01 / 阿里云)"

"$ACME_BIN" --register-account -m "$ACME_EMAIL" --force 2>/dev/null || true
"$ACME_BIN" --set-default-ca --server letsencrypt 2>/dev/null || true
"$ACME_BIN" --issue --dns dns_ali --server letsencrypt \
  -d "$ANI_DOMAIN" \
  -d "$CONFIG_DOMAIN" \
  -d "$ALIST_DOMAIN" \
  -d "$WWW_DOMAIN" \
  -d "$SUB_DOMAIN" \
  -d "$HUB_DOMAIN" \
  -d "$PHOTOS_DOMAIN" \
  --keylength ec-256 \
  --force

CERT_DIR="$HOME/.acme.sh/${ANI_DOMAIN}_ecc"
install -m 644 "$CERT_DIR/fullchain.cer" "$SIDESTORE_HOME/certs/fullchain.cer"
install -m 600 "$CERT_DIR/${ANI_DOMAIN}.key" "$SIDESTORE_HOME/certs/key.key"

echo "证书已安装到 $SIDESTORE_HOME/certs/"
openssl x509 -in "$SIDESTORE_HOME/certs/fullchain.cer" -noout -subject -dates
