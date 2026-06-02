#!/bin/sh
# 工作日 17:30：选股 Top5 → 东财 SOP → 同步次日监控 → 微信推送选股报告
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

WECHAT_ACP_INSTANCE="${WECHAT_ACP_INSTANCE:-tools-workspace}"
WECHAT_TARGET="${WECHAT_TARGET:-o9cq801H5ip_q8SH3ogvkQhhNI2s@im.wechat}"
WECHAT_PUSH_BACKEND="${WECHAT_PUSH_BACKEND:-wechat-acp}"

if [ "${REPORT_ONLY:-0}" != "1" ]; then
  echo "=========================================="
  echo "综合选股 + SOP（17:30）"
  echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "=========================================="
  ./run_selection_daily.sh 2>&1 | tee "$FULL"
else
  if ! uv run python -c "
from scripts.tools.selection_results import resolve_selection_df
_, df, _ = resolve_selection_df()
raise SystemExit(0 if len(df) > 0 else 1)
" 2>/dev/null; then
    if [ ! -s "$FULL" ] && ! ls "${ROOT}"/output/stock_selection_combined_*.csv >/dev/null 2>&1; then
      echo "❌ REPORT_ONLY=1 但无选股产物（MySQL selection_daily_results / $FULL / CSV）" >&2
      exit 1
    fi
  fi
  echo "REPORT_ONLY=1：跳过选股，仅推送已有选股报告"
fi

uv run python -m scripts.tools.selection_watchlist --sync || true

"${ROOT}/scripts/tools/run_portfolio_snapshot.sh" eod

if [ ! -s "$FULL" ]; then
  echo "❌ 选股报告为空，无法推送" >&2
  exit 1
fi

if [ "${PUSH_WECHAT:-1}" = "0" ]; then
  echo "已保存: $FULL（PUSH_WECHAT=0 跳过微信）"
  exit 0
fi

export WECHAT_ACP_INSTANCE
export WECHAT_TARGET

case "$WECHAT_PUSH_BACKEND" in
  wechat-acp)
    if [ ! -f "${HOME}/.wechat-acp/instances/${WECHAT_ACP_INSTANCE}/token.json" ]; then
      echo "❌ 未找到 wechat-acp token，请先启动 wechat-cursor-acp 并完成扫码登录" >&2
      exit 1
    fi
    uv run python scripts/tools/wechat_acp_push_text.py "$FULL"
    ;;
  qclaw)
    export OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-${HOME}/.qclaw}"
    export WEIXIN_ACCOUNT_ID="${WEIXIN_ACCOUNT_ID:-04080d9366d0-im-bot}"
    export WEIXIN_TARGET="$WECHAT_TARGET"
    uv run python scripts/tools/weixin_push_text.py "$FULL"
    ;;
  *)
    echo "❌ 未知 WECHAT_PUSH_BACKEND=$WECHAT_PUSH_BACKEND（wechat-acp | qclaw）" >&2
    exit 1
    ;;
esac

echo "已推送选股报告: $FULL"
