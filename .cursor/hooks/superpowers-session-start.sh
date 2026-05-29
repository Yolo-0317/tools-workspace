#!/usr/bin/env bash
# 注入 Superpowers using-superpowers 技能上下文（sessionStart）
set -euo pipefail

if [[ -n "${CURSOR_PLUGIN_ROOT:-}" && -x "${CURSOR_PLUGIN_ROOT}/hooks/session-start" ]]; then
  exec "${CURSOR_PLUGIN_ROOT}/hooks/session-start"
fi

# 使用本机已缓存的 Cursor 插件目录
PLUGIN_ROOT="$(ls -d "${HOME}/.cursor/plugins/cache/cursor-public/superpowers"/*/ 2>/dev/null | sort | tail -1)"
PLUGIN_ROOT="${PLUGIN_ROOT%/}"

if [[ -z "${PLUGIN_ROOT}" || ! -x "${PLUGIN_ROOT}/hooks/session-start" ]]; then
  printf '%s\n' '{"additional_context": "Superpowers plugin not found. In Agent chat run: /add-plugin superpowers"}'
  exit 0
fi

export CURSOR_PLUGIN_ROOT="${PLUGIN_ROOT}"
exec "${PLUGIN_ROOT}/hooks/session-start"
