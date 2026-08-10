#!/usr/bin/env bash
# 周二/周五 19:25：提醒群发 + 转群（增长模型）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

mkdir -p logs
exec uv run python -m scripts.tools.wechat_mp_growth_remind "$@"
