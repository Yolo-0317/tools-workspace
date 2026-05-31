#!/usr/bin/env bash
# 在已有 MySQL 数据目录上应用 sql/*.sql（initdb 仅对空库生效，已有 stock_daily 时用本脚本）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${MYSQL_ROOT_PASSWORD:?请配置 .env 中的 MYSQL_ROOT_PASSWORD}"
DB="${MYSQL_DATABASE:-stock_data}"

if ! docker ps --format '{{.Names}}' | grep -qx mysql8; then
  echo "mysql8 未运行，请先: docker compose up -d"
  exit 1
fi

for f in "$ROOT"/sql/*.sql; do
  [[ -f "$f" ]] || continue
  echo "apply: $(basename "$f")"
  docker exec -i mysql8 mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$DB" <"$f"
done

echo "done. tables:"
docker exec mysql8 mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SHOW TABLES" "$DB"
