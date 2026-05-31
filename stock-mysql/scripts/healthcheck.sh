#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] && set -a && source .env && set +a
: "${MYSQL_ROOT_PASSWORD:?}"
DB="${MYSQL_DATABASE:-stock_data}"
docker exec mysql8 mysqladmin ping -h 127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" >/dev/null
docker exec mysql8 mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SELECT COUNT(*) FROM stock_daily" "$DB" | xargs echo "stock_daily rows:"
docker exec mysql8 mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SHOW TABLES LIKE 'portfolio%'" "$DB"
