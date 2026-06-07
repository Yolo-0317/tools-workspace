#!/bin/sh
# 持仓盘中监控（原：Docker scheduler 每 5 分钟 → host-jobs；2026-06-04 起默认停用）
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# 恢复：在 .env 设 HOLDINGS_MONITOR_ENABLED=1，并取消 docker/scheduler/crontab 里 monitor 行注释
if [ "${HOLDINGS_MONITOR_ENABLED:-0}" != "1" ]; then
  echo "持仓盘中监控已停用（设 HOLDINGS_MONITOR_ENABLED=1 可恢复）" >&2
  exit 0
fi

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
