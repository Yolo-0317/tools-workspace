#!/bin/sh
# 情绪周期日检 → MySQL（供 home-hub /emotion 看板）
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export STOCK_AI_ROOT="${ROOT}"

# launchd 定时任务可能不注入 HOME，导致 ~/.local/bin/uv 与 opencli 找不到
if [ -z "${HOME:-}" ]; then
  HOME="$(/usr/bin/dscl . -read "/Users/$(whoami)" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
fi
if [ -z "${HOME:-}" ]; then
  HOME="/Users/$(whoami)"
fi
export HOME
export PATH="/usr/local/bin:${HOME}/.local/bin:${HOME}/.nvm/versions/node/v24.14.1/bin:${PATH}"
export OPENCLI_BIN="${OPENCLI_BIN:-${HOME}/.nvm/versions/node/v24.14.1/bin/opencli}"
if [ -f /.dockerenv ]; then
  UV_BIN="${UV_BIN:-/usr/local/bin/uv}"
else
  UV_BIN="${UV_BIN:-${HOME}/.local/bin/uv}"
fi
if [ ! -x "${UV_BIN}" ] && command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
fi

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# 本机直跑时用 127.0.0.1；容器内保留 host.docker.internal
if [ ! -f /.dockerenv ]; then
  export MYSQL_URL="$(printf '%s' "${MYSQL_URL:-}" | sed 's/host\.docker\.internal/127.0.0.1/g')"
fi

SLOT="${1:-eod}"
if [ "$SLOT" != "eod" ]; then
  echo "[$(date '+%F %T')] warn: slot=${SLOT} 已废弃，仅用 eod" >&2
  SLOT=eod
fi
echo "[$(date '+%F %T')] sync_emotion_cycle slot=${SLOT}"
"${UV_BIN}" run python -m scripts.tools.sync_emotion_cycle_daily --slot "$SLOT"
SYNC_RC=$?

# 入库成功后 → 可选推送 Win11 量化（EMQUANT_ENABLED=1 时）
if [ "$SYNC_RC" -eq 0 ]; then
  EMQUANT_ROOT="$(dirname "$ROOT")/emquant-sim"
  EMQUANT_ENV_FILE="${EMQUANT_ROOT}/.env.emquant"
  EMQUANT_ON="${EMQUANT_ENABLED:-}"
  if [ -z "$EMQUANT_ON" ] && [ -f "$EMQUANT_ENV_FILE" ]; then
    EMQUANT_ON="$(grep -E '^EMQUANT_ENABLED=' "$EMQUANT_ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \r')"
  fi
  PUSH_SH="${EMQUANT_ROOT}/scripts/push_dragons_to_win11.sh"
  if [ "$EMQUANT_ON" = "1" ] && [ -d "$EMQUANT_ROOT" ] && [ -f "$PUSH_SH" ]; then
    (
      cd "$EMQUANT_ROOT"
      PYTHONPATH=. python3 -m scripts.tools.export_emotion_dragons --slot "$SLOT" \
        || PYTHONPATH=. python3 -m scripts.tools.export_emotion_dragons --slot eod
      bash "$PUSH_SH"
    ) || echo "[$(date '+%F %T')] warn: export/push dragons.json failed (量化可沿用旧文件)"
  elif [ -d "$EMQUANT_ROOT" ] && [ -f "$EMQUANT_ENV_FILE" ] && [ "${EMQUANT_ON:-0}" != "1" ]; then
    echo "[$(date '+%F %T')] emquant push skipped (EMQUANT_ENABLED≠1，见 emquant-sim/OFFLINE.md)"
  fi
fi

exit "$SYNC_RC"
