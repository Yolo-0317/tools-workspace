#!/usr/bin/env bash
# SillyTavern (酒馆) — macOS 最小安装
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor/SillyTavern"
BRANCH="${SILLYTAVERN_BRANCH:-release}"

echo "==> sillytavern-mac 安装"
echo "    项目目录: $ROOT"
echo "    分支: $BRANCH"

if ! command -v git >/dev/null 2>&1; then
  echo "错误: 未找到 git"
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "错误: 未找到 node（需要 Node.js 20+）"
  exit 1
fi

NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]")"
if [[ "$NODE_MAJOR" -lt 20 ]]; then
  echo "错误: Node.js 版本过低 ($(node -v))，需要 20+"
  exit 1
fi

if [[ ! -d "$VENDOR/.git" ]]; then
  echo "==> 克隆 SillyTavern ($BRANCH) ..."
  mkdir -p "$ROOT/vendor"
  git clone --depth 1 -b "$BRANCH" https://github.com/SillyTavern/SillyTavern.git "$VENDOR"
else
  echo "==> 已存在 $VENDOR，跳过 clone"
fi

mkdir -p "$ROOT/logs"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "==> 已生成 .env（可按需修改端口）"
fi

echo "==> 安装 npm 依赖（首次较慢）..."
(cd "$VENDOR" && npm install --no-audit --no-fund)

bash scripts/patch-hub-subpath.sh
bash scripts/patch-hub-proxy.sh
bash scripts/patch-openai-autoconnect.sh
bash scripts/patch-mobile-send-echo.sh

echo ""
echo "安装完成。启动: bash scripts/start.sh"
echo "浏览器: http://127.0.0.1:8792"
echo "Hub:    https://hub.yoloworld.site:8883/silly/"
