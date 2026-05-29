#!/usr/bin/env bash
set -euo pipefail

SIDESTORE_HOME="${SIDESTORE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$SIDESTORE_HOME"

echo "== SideStore Infra Setup =="

if ! docker info >/dev/null 2>&1; then
  echo "请先启动 Docker Desktop，然后重新运行: $0"
  exit 1
fi

# shellcheck disable=SC1091
source "$SIDESTORE_HOME/scripts/lib/env.sh"
load_aliyun_env

set -a
# shellcheck disable=SC1091
source "$SIDESTORE_HOME/.env"
set +a

echo "[1/5] 同步阿里云 DDNS (ani, config)..."
if [[ -x "$SIDESTORE_HOME/.venv/bin/python" ]] && "$SIDESTORE_HOME/.venv/bin/python" -c "import aliyunsdkalidns" 2>/dev/null; then
  DDNS_PYTHON="$SIDESTORE_HOME/.venv/bin/python"
elif /opt/anaconda3/bin/python -c "import aliyunsdkalidns" 2>/dev/null; then
  DDNS_PYTHON=/opt/anaconda3/bin/python
else
  echo "安装 DDNS 依赖..."
  if command -v uv >/dev/null 2>&1; then
    uv venv "$SIDESTORE_HOME/.venv" 2>/dev/null || true
    uv pip install -p "$SIDESTORE_HOME/.venv/bin/python" -r "$SIDESTORE_HOME/scripts/requirements-ddns.txt"
  else
    python3 -m venv "$SIDESTORE_HOME/.venv"
    "$SIDESTORE_HOME/.venv/bin/pip" install -r "$SIDESTORE_HOME/scripts/requirements-ddns.txt"
  fi
  DDNS_PYTHON="$SIDESTORE_HOME/.venv/bin/python"
fi
"$DDNS_PYTHON" "$SIDESTORE_HOME/scripts/aliyun_ddns.py"

echo "[2/5] 签发 HTTPS 证书 (DNS-01，无需 80/443 端口映射)..."
if [[ ! -f "$SIDESTORE_HOME/certs/fullchain.cer" ]]; then
  bash "$SIDESTORE_HOME/scripts/issue-certs.sh"
else
  echo "证书已存在，跳过签发（强制重签: bash scripts/issue-certs.sh）"
fi

echo "[3/5] 启动 Docker 栈..."
docker compose --env-file .env up -d

echo "[4/5] 等待 anisette 就绪..."
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:6969/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[5/5] 健康检查..."
"$SIDESTORE_HOME/scripts/healthcheck.sh" || true

INTERNAL_PORT="${INTERNAL_HTTPS_PORT:-8443}"
EXTERNAL_PORT="${EXTERNAL_HTTPS_PORT:-8883}"
echo
echo "完成。SideStore 配置："
echo "  Anisette List URL: https://config.yoloworld.site:${EXTERNAL_PORT}/servers.json"
echo "  选择服务器: Yolo Home Anisette"
echo
echo "路由器只需映射一条："
echo "  外网 TCP ${EXTERNAL_PORT} -> 本机 Mac:${INTERNAL_PORT}"
echo
echo "请确认："
echo "  1) .env 中 ACME_EMAIL 为真实邮箱"
echo "  2) iPhone SideStore 启用 LocalDevVPN"
