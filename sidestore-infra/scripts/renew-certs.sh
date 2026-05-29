#!/usr/bin/env bash
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

ANI_DOMAIN="${ANI_SUBDOMAIN}.${DOMAIN}"
export Ali_Key="$ALIBABA_CLOUD_ACCESS_KEY_ID"
export Ali_Secret="$ALIBABA_CLOUD_ACCESS_KEY_SECRET"

ACME_BIN="${ACME_BIN:-$HOME/.acme.sh/acme.sh}"
"$ACME_BIN" --renew -d "$ANI_DOMAIN" --force

CERT_DIR="$HOME/.acme.sh/${ANI_DOMAIN}_ecc"
install -m 644 "$CERT_DIR/fullchain.cer" "$SIDESTORE_HOME/certs/fullchain.cer"
install -m 600 "$CERT_DIR/${ANI_DOMAIN}.key" "$SIDESTORE_HOME/certs/key.key"

if docker ps --format '{{.Names}}' | grep -q '^sidestore-caddy$'; then
  docker compose --env-file .env restart caddy
fi
echo "证书已续期"
