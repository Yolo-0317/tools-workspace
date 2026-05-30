#!/usr/bin/env bash
# 同步 QClaw daily_briefing 定时任务 → 东财 Playwright 战报脚本
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

chmod +x "${ROOT}/push_daily_briefing_wechat.sh"

export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
uv run python -m scripts.tools.patch_qclaw_daily_briefing_jobs

echo ""
echo "手动试跑:"
echo "  FETCH_ONLY=1 ${ROOT}/push_daily_briefing_wechat.sh 09:00"
echo "  ${ROOT}/push_daily_briefing_wechat.sh 15:00"
