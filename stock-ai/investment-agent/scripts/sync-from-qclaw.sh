#!/usr/bin/env bash
# 从 QClaw 工作区单向同步核心文件到本项目
set -euo pipefail

SRC="${HOME}/.qclaw/workspace"
DEST="$(cd "$(dirname "$0")/.." && pwd)"

echo "Syncing from ${SRC} → ${DEST}"

for f in MEMORY.md 持仓执行卡.md USER.md SOUL.md 复盘日志.md; do
  if [[ -f "${SRC}/${f}" ]]; then
    cp "${SRC}/${f}" "${DEST}/${f}"
    echo "  ✓ ${f}"
  fi
done

if [[ -d "${SRC}/memory" ]]; then
  rsync -a --delete "${SRC}/memory/" "${DEST}/memory/"
  echo "  ✓ memory/"
fi

if [[ -d "${SRC}/scripts" ]]; then
  for py in "${SRC}/scripts/"*.py; do
    [[ -f "$py" ]] || continue
    cp "$py" "${DEST}/scripts/"
    echo "  ✓ scripts/$(basename "$py")"
  done
fi

echo "Done."
