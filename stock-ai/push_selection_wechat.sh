#!/bin/sh
# 生成每日综合选股战报并推送到微信（默认 wechat-acp 链路）
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${ROOT}/output/daily_selection_push_latest.txt"
WECHAT_ACP_INSTANCE="${WECHAT_ACP_INSTANCE:-tools-workspace}"
WECHAT_TARGET="${WECHAT_TARGET:-o9cq801H5ip_q8SH3ogvkQhhNI2s@im.wechat}"
# wechat-acp | qclaw（旧 openclaw-weixin 账号）
WECHAT_PUSH_BACKEND="${WECHAT_PUSH_BACKEND:-wechat-acp}"

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

if [ "${REPORT_ONLY:-0}" != "1" ]; then
  ./run_selection_daily.sh 2>&1 | awk '/^📈 综合选股 Top5/{p=1} p' > "$OUT"
else
  if [ ! -s "$OUT" ]; then
    echo "❌ REPORT_ONLY=1 但 $OUT 不存在或为空" >&2
    exit 1
  fi
fi

if [ ! -s "$OUT" ]; then
  echo "❌ 战报内容为空，选股脚本可能失败" >&2
  exit 1
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

echo "已推送: $OUT (backend=$WECHAT_PUSH_BACKEND)"
