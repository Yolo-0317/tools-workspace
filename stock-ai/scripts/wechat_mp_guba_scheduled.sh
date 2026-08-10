#!/usr/bin/env bash
# 交易日 15:15 — 东财人气 Top12 → 4 帖股吧正文 → 飞书（标题+正文 × 4）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

SKIP_FILE="${ROOT}/data/wechat_mp_skip_scheduled.date"
if [[ -f "${SKIP_FILE}" ]]; then
  skip_day="$(tr -d '[:space:]' < "${SKIP_FILE}")"
  today="$(TZ=Asia/Shanghai date +%Y-%m-%d)"
  if [[ "${skip_day}" == "${today}" ]]; then
    echo "SKIP 今日东财股吧 (${today}) · 见 ${SKIP_FILE}" >&2
    exit 0
  fi
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

BATCH="$(uv run python -c "from scripts.tools.wechat_mp_draft_batch import resolve_scheduled_batch; print(resolve_scheduled_batch())")"
if [[ "${BATCH}" != "evening" ]]; then
  echo "SKIP 非交易日东财股吧 (batch=${BATCH})" >&2
  exit 0
fi

export WECHAT_MP_GUBA_MODE=hot12
export WECHAT_MP_GUBA_FEISHU=1
export WECHAT_MP_GUBA_DRAFT=0
export WECHAT_MP_GUBA_NOTES=0
export WECHAT_MP_GUBA_USE_CACHE=0

mkdir -p logs
echo "东财股吧 scheduled · ${BATCH} · Top12→4帖 · 飞书" >&2
exec uv run python -m scripts.tools.wechat_mp_guba_sector --feishu "$@"
