#!/bin/sh
set -e

mkdir -p /app/logs

echo "[stock-ai-scheduler] TZ=${TZ:-unset} schedule:"
cat /etc/cron.d/stock-ai-scheduler

exec /usr/local/bin/supercronic -passthrough-logs /etc/cron.d/stock-ai-scheduler
