#!/usr/bin/env bash
set -eo pipefail

SIDESTORE_HOME="${SIDESTORE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# shellcheck disable=SC1091
source "$SIDESTORE_HOME/scripts/lib/env.sh"
load_aliyun_env || {
  echo "错误: 无法加载阿里云凭证（检查 .env.secrets 或 ~/.zshrc）"
  exit 1
}

set -a
# shellcheck disable=SC1091
source "$SIDESTORE_HOME/.env"
set +a

export DDNS_DOMAIN="${DOMAIN:-yoloworld.site}"
export DDNS_SUBDOMAINS="${DDNS_SUBDOMAINS:-ani,config}"

PYTHON="$SIDESTORE_HOME/.venv/bin/python"
if [[ -x "$PYTHON" ]] && "$PYTHON" -c "import aliyunsdkalidns" 2>/dev/null; then
  :
elif /opt/anaconda3/bin/python -c "import aliyunsdkalidns" 2>/dev/null; then
  PYTHON=/opt/anaconda3/bin/python
else
  PYTHON=python3
fi

exec "$PYTHON" "$SIDESTORE_HOME/scripts/aliyun_ddns.py"
