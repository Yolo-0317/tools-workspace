#!/usr/bin/env bash
# 清理 OpenCLI：关闭各会话全部 tab + 释放 lease（减轻 Chrome 标签分组堆积）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"
OPENCLI="${OPENCLI_BIN:-${HOME}/.nvm/versions/node/v24.14.1/bin/opencli}"

if [[ ! -x "${OPENCLI}" ]]; then
  echo "未找到 opencli: ${OPENCLI}" >&2
  exit 1
fi

echo "关闭 OpenCLI 各会话的全部 tab 并释放 lease…"
cd "${ROOT}"
uv run python - <<'PY'
from scripts.tools.fetch_eastmoney_quotes import force_close_opencli_browser

force_close_opencli_browser(rounds=3)
print("OK: tab + session lease 已清理")
PY

if [[ "${1:-}" == "--stop-daemon" ]]; then
  echo "停止 opencli daemon…"
  "${OPENCLI}" daemon stop 2>/dev/null || true
fi

echo ""
echo "若 Chrome 里仍有 OpenCLI 标签分组：在对应窗口右键分组 →「解散分组」→ 关掉空白标签。"
echo "日常标签不受影响；仅清理 OpenCLI 自动化会话（stock/default/mp）。"
