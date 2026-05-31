#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
LABEL="com.user.stock-holdings-monitor"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

chmod +x "${ROOT}/push_holdings_monitor.sh"

cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"

echo "已加载: ${DST}"
echo "间隔: 每 5 分钟（脚本内仅交易时段 9:30-11:30 / 13:00-15:00 生效）"
echo "规则: MySQL alert_rules（改执行卡后运行 sync_portfolio_from_card）"
echo "现价: 东财行情页（OpenCLI Browser）"
echo "手动: uv run python -m scripts.monitor.monitor_holdings_alerts --force --push"
