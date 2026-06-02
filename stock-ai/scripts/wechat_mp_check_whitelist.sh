#!/usr/bin/env bash
# 公众号 API / IP 白名单监控（供 launchd 每小时调用）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export PATH="${HOME}/.local/bin:${PATH}"
exec uv run python -m scripts.tools.wechat_mp_check_whitelist --push-wechat "$@"
