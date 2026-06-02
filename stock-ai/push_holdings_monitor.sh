#!/bin/sh
# 持仓盘中监控（交易时段每 5 分钟由 launchd 调用）
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# launchd 定时任务可能不注入 HOME，导致 ~/.local/bin/uv 找不到
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

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

exec "${UV_BIN}" run python -m scripts.monitor.monitor_holdings_alerts --push "$@"
