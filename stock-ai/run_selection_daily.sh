#!/bin/sh
# 综合选股 + Top5 东财 SOP（供 17:30 收盘甄选战报调用）
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

SOP_ARGS="--sop-workers ${SOP_WORKERS:-3} --deepseek-workers ${DEEPSEEK_WORKERS:-3}"
if [ "${DISABLE_SOP_TOP5:-0}" = "1" ]; then
  SOP_ARGS="--no-sop"
  echo "⚠️ 已禁用东财 SOP（DISABLE_SOP_TOP5=1），改用轻量 DeepSeek 简评"
else
  echo "东财 SOP 并发分析（Top5 → 战报 → 次日监控）workers=${SOP_WORKERS:-3}"
fi

echo "=========================================="
echo "开始综合选股 + SOP..."
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

uv run python -m scripts.selection.daily_selection_report $SOP_ARGS 2>&1 | tee "logs/selection_daily_$(date '+%Y%m%d').log"
