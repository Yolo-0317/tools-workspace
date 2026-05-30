#!/usr/bin/env bash
# Deprecated: use tools-workspace/wechat-cursor-acp instead.
set -euo pipefail

BRIDGE="$(cd "$(dirname "$0")/../../.." && pwd)/wechat-cursor-acp/scripts/start.sh"

if [[ ! -x "${BRIDGE}" ]]; then
  echo "Error: wechat-cursor-acp not found at ${BRIDGE}" >&2
  exit 1
fi

echo "Note: start-wechat-acp.sh forwards to wechat-cursor-acp/scripts/start.sh" >&2
exec "${BRIDGE}" "$@"
