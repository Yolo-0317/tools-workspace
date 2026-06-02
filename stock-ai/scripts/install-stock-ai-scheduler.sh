#!/usr/bin/env bash
# 安装 stock-ai 统一调度：host-jobs launchd + Docker scheduler，并停用旧 launchd 定时任务
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
AGENTS="${HOME}/Library/LaunchAgents"
UID_GUI="gui/$(id -u)"

chmod +x "${ROOT}/scripts/scheduler/start-host-jobs.sh"
chmod +x "${ROOT}/docker/scheduler/run-host-job.sh"

echo "==> 1/4 安装 host-jobs launchd"
cp "${WORKSPACE}/launchd/com.user.stock-ai-host-jobs.plist" "${AGENTS}/"
launchctl bootout "${UID_GUI}" "${AGENTS}/com.user.stock-ai-host-jobs.plist" 2>/dev/null || true
launchctl bootstrap "${UID_GUI}" "${AGENTS}/com.user.stock-ai-host-jobs.plist"
echo "    host-jobs: http://127.0.0.1:${HOST_JOB_PORT:-9876}/health"

echo "==> 2/4 停用旧 stock-ai launchd 定时任务（改由 Docker scheduler 触发）"
for label in \
  com.user.stock-ai-daily-selection \
  com.user.stock-ai-daily-briefing \
  com.user.stock-holdings-monitor; do
  plist="${AGENTS}/${label}.plist"
  if launchctl print "${UID_GUI}/${label}" &>/dev/null; then
    launchctl bootout "${UID_GUI}" "${plist}" 2>/dev/null || true
    echo "    已停用 ${label}"
  fi
done

echo "==> 3/4 停止旧 stock-daily-sync 容器（若存在）"
docker stop stock-daily-sync 2>/dev/null || true
docker rm stock-daily-sync 2>/dev/null || true

echo "==> 4/5 构建并启动 stock-ai-scheduler"
(cd "${ROOT}/docker/scheduler" && docker compose up -d --build)

echo "==> 5/5 安装盘中龙头 launchd（OpenCLI 每 15 分钟）"
"${ROOT}/scripts/install-emotion-intraday-launchd.sh"

echo ""
echo "完成。验证："
echo "  curl -s http://127.0.0.1:${HOST_JOB_PORT:-9876}/health"
echo "  curl -s -X POST http://127.0.0.1:${HOST_JOB_PORT:-9876}/run/emotion-intraday -H 'Content-Type: application/json' -d '{}'"
echo "  launchctl print ${UID_GUI}/com.user.stock-emotion-intraday"
echo ""
echo "可选：在 stock-ai/.env 设置 HOST_JOB_TOKEN=随机字符串（容器与 host-jobs 共用）"
echo "若容器 curl 失败，设 HOST_JOB_BIND=0.0.0.0 后重启 host-jobs"
