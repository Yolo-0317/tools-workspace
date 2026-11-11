#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR/backend"
if [ ! -x ../.venv/bin/python ]; then
  echo '请先按 README 安装项目依赖。'
  exit 1
fi
if [ ! -f ../frontend/dist/index.html ]; then
  echo '请先构建前端：cd frontend && npm ci && npm run build'
  exit 1
fi
exec ../.venv/bin/python -m zhouyi.run
