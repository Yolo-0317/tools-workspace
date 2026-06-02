#!/usr/bin/env bash
# 仅推送 dragons.json 到 Win11 掘金策略目录（intraday 每 5min 调用）
set -euo pipefail

VM_NAME="${EMQUANT_VM_NAME:-Windows 11}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRAGONS="${EMQUANT_DRAGONS:-$ROOT/output/emquant/dragons.json}"
ENV_FILE="${EMQUANT_ENV:-$ROOT/.env.emquant}"
PY="C:\\Program Files\\Python312-x64\\python.exe"

if [[ ! -f "$DRAGONS" ]]; then
  echo "❌ 未找到 $DRAGONS，请先 export_emotion_dragons" >&2
  exit 1
fi

STRATEGY_ID="${EMQUANT_STRATEGY_ID:-}"
if [[ -z "$STRATEGY_ID" && -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$ENV_FILE" && set +a
  STRATEGY_ID="${EMQUANT_STRATEGY_ID:-}"
fi

if [[ -z "$STRATEGY_ID" ]]; then
  echo "❌ 未设置 EMQUANT_STRATEGY_ID（.env.emquant）" >&2
  exit 1
fi

DEST="C:\\Users\\yolo\\.emgm3\\projects\\${STRATEGY_ID}\\dragons.json"
prlctl exec "$VM_NAME" "$PY" -c "import sys; open(sys.argv[1],'wb').write(sys.stdin.buffer.read())" "$DEST" < "$DRAGONS"
echo "[$(date '+%F %T')] pushed dragons.json → ${DEST}"
