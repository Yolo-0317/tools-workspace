#!/usr/bin/env bash
# 投顾周五周复盘 → MySQL + output/advisor_weekly/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
exec uv run python -m scripts.tools.advisor_weekly_review --save "$@"
