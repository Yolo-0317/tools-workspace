#!/usr/bin/env bash
# 热点深评定时草稿：09:00 / 11:00 / 15:00 / 18:00（scheduler → host-jobs）
# 用法：bash scripts/wechat_mp_hotspot_draft_scheduled.sh [hotspot_early|hotspot_morning|hotspot_afternoon|hotspot_evening]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

BATCH="${1:-hotspot_afternoon}"
case "${BATCH}" in
  hotspot_early|hotspot_morning|hotspot_afternoon|hotspot_evening) ;;
  *)
    echo "未知 batch=${BATCH}；可选: hotspot_early hotspot_morning hotspot_afternoon hotspot_evening" >&2
    exit 2
    ;;
esac

SKIP_FILE="${ROOT}/data/wechat_mp_skip_scheduled.date"
if [[ -f "${SKIP_FILE}" ]]; then
  skip_day="$(tr -d '[:space:]' < "${SKIP_FILE}")"
  today="$(TZ=Asia/Shanghai date +%Y-%m-%d)"
  if [[ "${skip_day}" == "${today}" ]]; then
    echo "SKIP 今日热点草稿 (${today}) · 见 ${SKIP_FILE}" >&2
    exit 0
  fi
fi

SLOT_SKIP_FILE="${ROOT}/data/wechat_mp_skip_${BATCH}.date"
if [[ -f "${SLOT_SKIP_FILE}" ]]; then
  skip_day="$(tr -d '[:space:]' < "${SLOT_SKIP_FILE}")"
  today="$(TZ=Asia/Shanghai date +%Y-%m-%d)"
  if [[ "${skip_day}" == "${today}" ]]; then
    echo "SKIP 今日 ${BATCH} (${today}) · 见 ${SLOT_SKIP_FILE}" >&2
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
echo "热点深评 scheduled · ${BATCH} · $(TZ=Asia/Shanghai date '+%H:%M')" >&2
exec uv run python -m scripts.tools.wechat_mp_draft_batch --batch "${BATCH}" "${@:2}"
