#!/bin/sh
# 工作日 17:30：选股 Top5 → 东财 SOP → 同步次日监控 → 收盘甄选战报 → 微信
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
FULL="${ROOT}/output/daily_selection_full_latest.txt"

cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export STOCK_AI_ROOT="${ROOT}"
export PATH="${HOME}/.local/bin:${HOME}/.nvm/versions/node/v24.14.1/bin:${PATH}"
mkdir -p output logs

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ "${REPORT_ONLY:-0}" != "1" ]; then
  echo "=========================================="
  echo "综合选股 + 收盘甄选战报（17:30）"
  echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "=========================================="
  ./run_selection_daily.sh 2>&1 | tee "$FULL"
else
  if [ ! -s "$FULL" ] && ! ls "${ROOT}"/output/stock_selection_combined_*.csv >/dev/null 2>&1; then
    echo "❌ REPORT_ONLY=1 但无选股产物（$FULL 或 stock_selection_combined_*.csv）" >&2
    exit 1
  fi
  echo "REPORT_ONLY=1：跳过选股，仅生成并推送收盘甄选战报"
fi

uv run python -m scripts.tools.selection_watchlist --sync || true

exec "${ROOT}/push_daily_briefing_wechat.sh" 17:30
