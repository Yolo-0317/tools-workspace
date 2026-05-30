#!/bin/sh
# 每日战报：东财 Playwright 宏观快讯 + 大盘/持仓 → 微信
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SLOT="${1:-${BRIEFING_SLOT:-$(date '+%H:00')}}"
OUT="${ROOT}/output/daily_briefing_${SLOT//:/}_latest.txt"
WECHAT_ACP_INSTANCE="${WECHAT_ACP_INSTANCE:-tools-workspace}"
WECHAT_TARGET="${WECHAT_TARGET:-o9cq801H5ip_q8SH3ogvkQhhNI2s@im.wechat}"
WECHAT_PUSH_BACKEND="${WECHAT_PUSH_BACKEND:-wechat-acp}"
NEWS_LIMIT="${MACRO_NEWS_LIMIT:-8}"

cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export STOCK_AI_ROOT="${ROOT}"
mkdir -p output logs

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

echo "=========================================="
echo "生成每日战报 (${SLOT})..."
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

uv run python -m scripts.tools.daily_briefing_report \
  --slot "$SLOT" \
  --limit "$NEWS_LIMIT" \
  --output "$OUT" \
  2>&1 | tee "logs/daily_briefing_${SLOT//:/}_$(date '+%Y%m%d_%H%M').log"

if [ ! -s "$OUT" ]; then
  echo "❌ 战报内容为空，生成可能失败" >&2
  exit 1
fi

if [ "${FETCH_ONLY:-0}" = "1" ]; then
  echo "已保存: $OUT"
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
    uv run python scripts/tools/wechat_acp_push_text.py "$OUT"
    ;;
  qclaw)
    export OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-${HOME}/.qclaw}"
    export WEIXIN_ACCOUNT_ID="${WEIXIN_ACCOUNT_ID:-04080d9366d0-im-bot}"
    export WEIXIN_TARGET="$WECHAT_TARGET"
    uv run python scripts/tools/weixin_push_text.py "$OUT"
    ;;
  *)
    echo "❌ 未知 WECHAT_PUSH_BACKEND=$WECHAT_PUSH_BACKEND（wechat-acp | qclaw）" >&2
    exit 1
    ;;
esac

echo "已推送: $OUT (slot=$SLOT, backend=$WECHAT_PUSH_BACKEND)"
