#!/bin/sh
# 综合选股 + Top5 东财 SOP（供 17:45 收盘甄选战报调用；scheduler 17:45 触发）
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

echo "预热东财全市场名称缓存（clist / OpenCLI A 股列表，ST 过滤）..."
uv run python -m scripts.tools.warm_stock_name_cache 2>&1 \
  | tee -a "logs/selection_warm_names_$(date '+%Y%m%d').log" \
  || echo "⚠️ 名称缓存预热失败，ST 过滤可能不完整"

echo "检查 MySQL 当日日线是否已更新（17:30 同步后较稳，不足则 Tushare 补同步）..."
uv run python -m scripts.tools.ensure_daily_bars --sync-if-stale --require-ready

echo "并行选股（四轨 ProcessPool）：combined+watch / ma5 / 五因子 / 筑底+放量突破..."
uv run python -m scripts.selection.run_parallel_selection 2>&1 \
  | tee "logs/selection_parallel_$(date '+%Y%m%d').log"

uv run python -m scripts.selection.daily_selection_report --skip-selection $SOP_ARGS 2>&1 \
  | tee -a "logs/selection_daily_$(date '+%Y%m%d').log"

echo "OpenCLI 档案 enrich（五策略合并 Top5，按总分）..."
uv run python -m scripts.tools.enrich_selection_profiles --trade-date latest 2>&1 \
  | tee -a "logs/selection_enrich_top5_$(date '+%Y%m%d').log" \
  || echo "⚠️ enrich Top5 失败，继续"
