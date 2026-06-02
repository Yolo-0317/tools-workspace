#!/usr/bin/env bash
# 工作日收盘后：生成四篇公众号草稿（市场 / Top5 / 龙头 / 工作区技术分享）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

if [[ "$(date +%u)" -ge 6 ]]; then
  echo "周末跳过 wechat_mp_draft"
  exit 0
fi

exec uv run python -m scripts.tools.wechat_mp_draft "$@"
