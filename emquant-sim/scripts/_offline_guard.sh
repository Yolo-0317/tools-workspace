#!/usr/bin/env bash
# 掘金量化总开关：EMQUANT_ENABLED=1 才允许 deploy / push / 自动推送
# 用法: source "$(dirname "$0")/_offline_guard.sh" && emquant_require_enabled || exit 0

_emquant_root() {
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  printf '%s' "$here"
}

emquant_enabled() {
  local root env_file enabled
  root="$(_emquant_root)"
  env_file="${EMQUANT_ENV:-$root/.env.emquant}"
  enabled="${EMQUANT_ENABLED:-}"
  if [[ -z "$enabled" && -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    set -a && source "$env_file" && set +a
    enabled="${EMQUANT_ENABLED:-0}"
  fi
  [[ "${enabled:-0}" == "1" ]]
}

emquant_require_enabled() {
  if emquant_enabled; then
    return 0
  fi
  echo "[emquant] 量化已下线（EMQUANT_ENABLED≠1）。见 emquant-sim/OFFLINE.md" >&2
  return 1
}
