#!/usr/bin/env bash
# Install KeepAlive launchd for cloud MCP pipe (quark-audio).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.user.xiaozhi-mcp-pipe"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing venv: $PYTHON" >&2
  exit 1
fi
if ! grep -q '^MCP_ENDPOINT=' "$ROOT/.env" 2>/dev/null; then
  echo "MCP_ENDPOINT missing in $ROOT/.env" >&2
  exit 1
fi

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>-u</string>
    <string>${ROOT}/scripts/mcp_pipe.py</string>
    <string>quark-audio</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/xiaozhi-mcp-pipe.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/xiaozhi-mcp-pipe.log</string>
</dict>
</plist>
EOF

# Load .env into plist via a wrapper would be better; mcp_pipe loads dotenv from WorkingDirectory.
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"
echo "Installed $PLIST"
echo "log: /tmp/xiaozhi-mcp-pipe.log"
echo "status: launchctl print gui/$(id -u)/${LABEL} | head"
