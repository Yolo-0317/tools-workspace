#!/usr/bin/env bash
# 公众号草稿：每日 18:20 — 交易日 evening 三篇 / 周日·节假日休市 news 一篇 / 周六跳过
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

# 按日跳过：data/wechat_mp_skip_scheduled.date 内容为 YYYY-MM-DD（Asia/Shanghai）
SKIP_FILE="${ROOT}/data/wechat_mp_skip_scheduled.date"
if [[ -f "${SKIP_FILE}" ]]; then
  skip_day="$(tr -d '[:space:]' < "${SKIP_FILE}")"
  today="$(TZ=Asia/Shanghai date +%Y-%m-%d)"
  if [[ "${skip_day}" == "${today}" ]]; then
    echo "SKIP 今日定时草稿 (${today}) · 见 ${SKIP_FILE}" >&2
    exit 0
  fi
fi

BATCH=""
if [[ $# -gt 0 && "$1" =~ ^(evening|weekend|weekend_skip)$ ]]; then
  BATCH="$1"
  shift
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

_weekday_label() {
  case "$(TZ=Asia/Shanghai date +%w)" in
    0) echo "周日" ;;
    1) echo "周一" ;;
    2) echo "周二" ;;
    3) echo "周三" ;;
    4) echo "周四" ;;
    5) echo "周五" ;;
    6) echo "周六" ;;
  esac
}

if [[ -z "${BATCH}" ]]; then
  BATCH="$(uv run python -c "from scripts.tools.wechat_mp_draft_batch import resolve_scheduled_batch; print(resolve_scheduled_batch())")"
  echo "自动批次: ${BATCH} ($(_weekday_label))" >&2
fi

case "${BATCH}" in
  evening|weekend|weekend_skip) ;;
  *)
    echo "用法: $0 [evening|weekend|weekend_skip] [--dry-run ...]" >&2
    echo "  无参数时自动：交易日=evening，休市日=weekend(news)，周六=weekend_skip(跳过)" >&2
    exit 2
    ;;
esac

mkdir -p logs
exec uv run python -m scripts.tools.wechat_mp_draft_batch --batch "${BATCH}" "$@"
