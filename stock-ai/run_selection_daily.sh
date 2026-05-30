#!/bin/sh
# 综合选股 + 微信摘要（供 QClaw cron 调用）
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
mkdir -p logs

export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export STOCK_AI_ROOT="${ROOT}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

export MYSQL_URL="${MYSQL_URL//host.docker.internal/127.0.0.1}"

SOP_ARGS=""
if [ "${ENABLE_SOP_TOP5:-0}" = "1" ]; then
  SOP_ARGS="--with-sop --sop-only --sop-workers ${SOP_WORKERS:-3} --deepseek-workers ${DEEPSEEK_WORKERS:-3}"
  echo "东财 SOP 并发分析已启用（workers=${SOP_WORKERS:-3}）"
fi

echo "=========================================="
echo "开始综合选股..."
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

uv run python -m scripts.selection.daily_selection_report $SOP_ARGS 2>&1 | tee "logs/selection_daily_$(date '+%Y%m%d').log"
