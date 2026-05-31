#!/bin/sh
# 持仓每日快照（失败写 logs/snapshot_alerts.log，默认不阻断调用方）
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SLOT="${1:-eod}"

cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export STOCK_AI_ROOT="${ROOT}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

LOG="logs/snapshot_${SLOT}_$(date '+%Y%m%d').log"
mkdir -p logs

if uv run python -m scripts.tools.dashboard_data snapshot-portfolio --slot "$SLOT" 2>&1 | tee -a "$LOG"; then
  exit 0
fi

echo "⚠️ 持仓快照 slot=${SLOT} 失败，见 logs/snapshot_alerts.log（主流程继续）" >&2
if [ "${SNAPSHOT_STRICT:-0}" = "1" ]; then
  exit 1
fi
exit 0
