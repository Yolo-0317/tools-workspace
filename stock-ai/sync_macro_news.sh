#!/bin/sh
# 东财 7×24 快讯 → MySQL（launchd 每 15 分钟）
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ -z "${HOME:-}" ]; then
  HOME="$(/usr/bin/dscl . -read "/Users/$(whoami)" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
fi
if [ -z "${HOME:-}" ]; then
  HOME="/Users/$(whoami)"
fi

export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export STOCK_AI_ROOT="${ROOT}"
export PATH="${HOME}/.local/bin:${HOME}/.nvm/versions/node/v24.14.1/bin:${PATH}"
export OPENCLI_BIN="${OPENCLI_BIN:-${HOME}/.nvm/versions/node/v24.14.1/bin/opencli}"
UV_BIN="${UV_BIN:-${HOME}/.local/bin/uv}"
export LLM_BACKEND="${LLM_BACKEND:-cursor}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

mkdir -p logs
exec "${UV_BIN}" run python -m scripts.tools.sync_macro_news "$@"
