#!/usr/bin/env bash
# 部署 stock_ai_sim_bridge 目录下全部 .py 到 Win11 掘金策略目录
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/_offline_guard.sh"
emquant_require_enabled || exit 1

VM_NAME="${EMQUANT_VM_NAME:-Windows 11}"
STRATEGY_ID="${1:-}"
if [[ -z "$STRATEGY_ID" ]]; then
  echo "用法: $0 <strategy-uuid>" >&2
  exit 1
fi

SRC_DIR="$ROOT/scripts/win/stock_ai_sim_bridge"
RULES="${EMQUANT_RULES:-$ROOT/output/emquant/rules.json}"
DRAGONS="${EMQUANT_DRAGONS:-$ROOT/output/emquant/dragons.json}"
ENTRY="${EMQUANT_ENTRY_FILE:-$ROOT/output/emquant/strategy_entry.json}"
TARGETS="${EMQUANT_TARGETS:-$ROOT/output/emquant/targets.json}"
DEST_DIR="C:\\Users\\yolo\\.emgm3\\projects\\${STRATEGY_ID}"
PY="C:\\Program Files\\Python312-x64\\python.exe"

shopt -s nullglob
PY_FILES=("$SRC_DIR"/*.py)
if [[ ${#PY_FILES[@]} -eq 0 ]]; then
  echo "未找到 $SRC_DIR/*.py" >&2
  exit 1
fi

for src in "${PY_FILES[@]}"; do
  base="$(basename "$src")"
  dest="${DEST_DIR}\\${base}"
  if [[ "$base" == "main.py" || "$base" == "dragon_main.py" || "$base" == "main_combined.py" ]]; then
    TMP="$(mktemp)"
    sed "s/REPLACE_STRATEGY_ID/${STRATEGY_ID}/g" "$src" > "$TMP"
    prlctl exec "$VM_NAME" "$PY" -c "import sys; open(sys.argv[1],'wb').write(sys.stdin.buffer.read())" "$dest" < "$TMP"
    rm -f "$TMP"
  else
    prlctl exec "$VM_NAME" "$PY" -c "import sys; open(sys.argv[1],'wb').write(sys.stdin.buffer.read())" "$dest" < "$src"
  fi
  echo "  -> $base"
done

if [[ -f "$RULES" ]]; then
  prlctl exec "$VM_NAME" "$PY" -c "import sys; open(sys.argv[1],'wb').write(sys.stdin.buffer.read())" "${DEST_DIR}\\rules.json" < "$RULES"
  echo "已部署 rules.json"
else
  echo "提示: 无 $RULES，请先 PYTHONPATH=. python3 -m scripts.tools.export_emquant_rules"
fi

if [[ -f "$DRAGONS" ]]; then
  prlctl exec "$VM_NAME" "$PY" -c "import sys; open(sys.argv[1],'wb').write(sys.stdin.buffer.read())" "${DEST_DIR}\\dragons.json" < "$DRAGONS"
  echo "已部署 dragons.json"
else
  echo "提示: 无 $DRAGONS，龙头策略请先 PYTHONPATH=. python3 -m scripts.tools.export_emotion_dragons"
fi

if [[ -f "$ENTRY" ]]; then
  prlctl exec "$VM_NAME" "$PY" -c "import sys; open(sys.argv[1],'wb').write(sys.stdin.buffer.read())" "${DEST_DIR}\\strategy_entry.json" < "$ENTRY"
  echo "已部署 strategy_entry.json ($(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['entry'])" "$ENTRY" 2>/dev/null || echo '?'))"
else
  echo "提示: 无 $ENTRY，默认 main.py 路由为 dragon"
fi

if [[ -f "$TARGETS" ]] && [[ "${DEPLOY_TARGETS:-0}" == "1" ]]; then
  prlctl exec "$VM_NAME" "$PY" -c "import sys; open(sys.argv[1],'wb').write(sys.stdin.buffer.read())" "${DEST_DIR}\\targets.json" < "$TARGETS"
  echo "已部署 targets.json（DEPLOY_TARGETS=1）"
fi

echo "✅ 已部署 ${#PY_FILES[@]} 个文件到 ${DEST_DIR}"
echo "终端: 仿真 + 关联仿真户 + 运行"
