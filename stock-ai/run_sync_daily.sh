#!/bin/sh
# -*- coding: utf-8 -*-
#
# Tushare 日线数据同步脚本
# Docker 定时任务见 docker/daily-sync/
#
# 本机 crontab 示例（每个交易日 17:30，生产以 docker/scheduler/crontab 为准）：
# 30 17 * * 1-5 cd /path/to/stock-ai && ./run_sync_daily.sh >> logs/sync_daily.log 2>&1
#

set -e

cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -z "$TUSHARE_TOKEN" ]; then
  echo "❌ 错误：未设置 TUSHARE_TOKEN 环境变量"
  exit 1
fi

if [ -z "$MYSQL_URL" ]; then
  echo "❌ 错误：未设置 MYSQL_URL 环境变量"
  exit 1
fi

mkdir -p logs

echo "=========================================="
echo "开始同步 Tushare 日线数据..."
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

uv run python scripts/sync_tushare_daily_to_mysql.py \
  --mode by_date \
  --days 2 \
  --sleep 2.0 \
  --max-calls 40

echo ""
echo "=========================================="
echo "同步完成"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
