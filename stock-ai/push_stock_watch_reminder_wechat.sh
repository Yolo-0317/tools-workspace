#!/bin/sh
# 一次性：2026-06-01 09:00 汉缆股份 + 中国电建关注提醒 → 微信（wechat-acp）
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${ROOT}/output/stock_watch_reminder_20260601.txt"
MARKER="${HOME}/.cache/stock-ai-stock-watch-reminder-20260601.done"
TARGET_DATE="${STOCK_WATCH_REMINDER_DATE:-2026-06-01}"
WECHAT_ACP_INSTANCE="${WECHAT_ACP_INSTANCE:-tools-workspace}"
WECHAT_TARGET="${WECHAT_TARGET:-o9cq801H5ip_q8SH3ogvkQhhNI2s@im.wechat}"
WECHAT_PUSH_BACKEND="${WECHAT_PUSH_BACKEND:-wechat-acp}"

cd "$ROOT"
mkdir -p output logs "${HOME}/.cache"

if [ -f "$MARKER" ]; then
  echo "已推送过，跳过: $MARKER"
  exit 0
fi

TODAY="$(date '+%Y-%m-%d')"
if [ "$TODAY" != "$TARGET_DATE" ]; then
  echo "非目标日期（$TODAY != $TARGET_DATE），跳过"
  exit 0
fi

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

cat > "$OUT" <<'EOF'
📌 关注提醒（6月1日）

① 汉缆股份(002498)：此前大跌约-9%接近跌停，关注能否守住 8.08 元附近。

② 中国电建(601669)：估值偏低(PB约0.62)，等 Q2 业绩拐点或放量突破 5.55 元再考虑。

（决策支持，非投资建议；当前近满仓，不宜盲目新开仓）
EOF

export WECHAT_ACP_INSTANCE
export WECHAT_TARGET

case "$WECHAT_PUSH_BACKEND" in
  wechat-acp)
    if [ ! -f "${HOME}/.wechat-acp/instances/${WECHAT_ACP_INSTANCE}/token.json" ]; then
      echo "❌ 未找到 wechat-acp token" >&2
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
    echo "❌ 未知 WECHAT_PUSH_BACKEND=$WECHAT_PUSH_BACKEND" >&2
    exit 1
    ;;
esac

touch "$MARKER"
echo "已推送: $OUT (date=$TARGET_DATE, backend=$WECHAT_PUSH_BACKEND)"
