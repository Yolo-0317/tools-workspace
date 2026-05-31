#!/usr/bin/env bash
# 生成 Caddy Basic Auth 片段（home-hub 公网访问）
set -euo pipefail

SIDESTORE_HOME="${SIDESTORE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
AUTH_FILE="${SIDESTORE_HOME}/caddy/home-hub.auth"

if [[ -d "${AUTH_FILE}" ]]; then
  echo "移除误创建的目录 ${AUTH_FILE}（Docker 在文件不存在时会挂载成空目录）" >&2
  rm -rf "${AUTH_FILE}"
fi

if [[ -f "${SIDESTORE_HOME}/.env.secrets" ]]; then
  # shellcheck disable=SC1091
  set -a && source "${SIDESTORE_HOME}/.env.secrets" && set +a
fi

USER_NAME="${HUB_BASIC_AUTH_USER:-hub}"
if [[ -z "${HUB_BASIC_AUTH_PASSWORD:-}" ]]; then
  echo "请设置环境变量 HUB_BASIC_AUTH_PASSWORD（或写入 sidestore-infra/.env.secrets 后 source）" >&2
  exit 1
fi

HASH="$(docker run --rm docker.m.daocloud.io/library/caddy:2.9-alpine \
  caddy hash-password --plaintext "${HUB_BASIC_AUTH_PASSWORD}" | tr -d '\r\n')"

cat > "${AUTH_FILE}" <<EOF
# generated $(date '+%Y-%m-%d %H:%M:%S') — do not commit
basicauth /* {
	${USER_NAME} ${HASH}
}
EOF

chmod 600 "${AUTH_FILE}"
echo "已写入 ${AUTH_FILE}"
echo "用户: ${USER_NAME}"
echo "下一步: docker compose -f ${SIDESTORE_HOME}/docker-compose.yml restart caddy"
