#!/bin/sh
set -e

mkdir -p /app/logs

echo "[stock-daily-sync] TZ=${TZ:-unset}  schedule:"
cat /etc/cron.d/stock-daily-sync

exec /usr/local/bin/supercronic -passthrough-logs /etc/cron.d/stock-daily-sync
