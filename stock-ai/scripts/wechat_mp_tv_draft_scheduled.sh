#!/usr/bin/env bash
# 每天 11:00 — 影视草稿 tv_trial（scheduler → host-jobs）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

# 按日跳过：data/wechat_mp_skip_tv_scheduled.date 内容为 YYYY-MM-DD（Asia/Shanghai）
SKIP_FILE="${ROOT}/data/wechat_mp_skip_tv_scheduled.date"
if [[ -f "${SKIP_FILE}" ]]; then
  skip_day="$(tr -d '[:space:]' < "${SKIP_FILE}")"
  today="$(TZ=Asia/Shanghai date +%Y-%m-%d)"
  if [[ "${skip_day}" == "${today}" ]]; then
    echo "SKIP 今日影视草稿 (${today}) · 见 ${SKIP_FILE}" >&2
    exit 0
  fi
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

mkdir -p logs
echo "影视草稿 scheduled · tv_trial · 11:00" >&2
uv run python -c "from scripts.tools.wechat_mp_tv_topics import refresh_tv_queue; refresh_tv_queue()" >&2
exec uv run python -m scripts.tools.wechat_mp_draft_batch --batch tv_trial "$@"
