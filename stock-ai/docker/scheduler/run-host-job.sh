#!/bin/sh
# 从 scheduler 容器触发本机 OpenCLI / 微信任务
set -eu

JOB="${1:?job name required}"
HOST="${HOST_JOB_HOST:-host.docker.internal}"
PORT="${HOST_JOB_PORT:-9876}"
TOKEN="${HOST_JOB_TOKEN:-}"
URL="http://${HOST}:${PORT}/run/${JOB}"

# 每日战报 09/12/15/20 已停用；快讯见 launchd com.user.stock-macro-news-sync
BODY="{}"

echo "[scheduler] trigger host job: $JOB -> $URL"
if [ -n "$TOKEN" ]; then
  curl -sfS -X POST "$URL" \
    -H "Content-Type: application/json" \
    -H "X-Job-Token: ${TOKEN}" \
    -d "$BODY"
else
  curl -sfS -X POST "$URL" \
    -H "Content-Type: application/json" \
    -d "$BODY"
fi
