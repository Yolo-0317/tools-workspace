#!/usr/bin/env bash
# 公司电脑公众号写稿环境自检：不写草稿、不发送通知。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "缺少 stock-ai/.env；先复制 .env.company-wechat.example。" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if ! command -v agent >/dev/null 2>&1; then
  echo "未找到 Cursor CLI agent；请先安装并执行 agent login。" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "未找到 uv；请先安装 uv 后执行 uv sync --group dev。" >&2
  exit 1
fi

if ! command -v opencli >/dev/null 2>&1 && [[ ! -x "${OPENCLI_BIN:-}" ]]; then
  echo "未找到 opencli；热点抓取前请安装 OpenCLI 和 Chrome 扩展。" >&2
  exit 1
fi

echo "== 公司网络公网 IP =="
uv run python -m scripts.tools.wechat_mp_check_whitelist --show-ip
echo "== 公众号 API 白名单与凭证 =="
uv run python -m scripts.tools.wechat_mp_check_whitelist --json
