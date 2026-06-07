#!/usr/bin/env bash
# 兼容旧入口：现包含 ani / config / hub
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/setup-local-dns.sh" "$@"
