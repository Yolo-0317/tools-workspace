#!/usr/bin/env bash
set -euo pipefail

SIDESTORE_HOME="${SIDESTORE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$SIDESTORE_HOME"

docker compose --env-file .env pull
docker compose --env-file .env up -d
"$SIDESTORE_HOME/scripts/healthcheck.sh"
