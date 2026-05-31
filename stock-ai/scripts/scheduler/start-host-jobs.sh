#!/usr/bin/env bash
# 启动本机 host-jobs HTTP（供 Docker scheduler 触发 OpenCLI 任务）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export HOST_JOB_PORT="${HOST_JOB_PORT:-9876}"
export HOST_JOB_BIND="${HOST_JOB_BIND:-127.0.0.1}"
export PATH="${HOME}/.local/bin:${PATH}"

exec uv run python scripts/scheduler/host_job_server.py
