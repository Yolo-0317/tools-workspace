#!/usr/bin/env bash
# 设置加载后自动检测 OpenAI/Custom API 连接（避免顶部长期显示「未连接」）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/vendor/SillyTavern/public/script.js"
MARKER="sillytavern-mac: openai autoconnect after settings load"

if [[ ! -f "$SCRIPT" ]]; then
  echo "跳过 patch-openai-autoconnect: 未找到 $SCRIPT"
  exit 0
fi

if grep -q "$MARKER" "$SCRIPT"; then
  echo "==> patch-openai-autoconnect 已应用"
  exit 0
fi

python3 - "$SCRIPT" "$MARKER" <<'PY'
import sys
from pathlib import Path

path, marker = sys.argv[1:3]
text = Path(path).read_text()
needle = "        changeMainAPI();\n\n        //Load User's Name and Avatar"
insert = f"""        changeMainAPI();

        // {marker}
        if (main_api === 'openai') {{
            setTimeout(() => $('#api_button_openai').trigger('click'), 300);
        }}

        //Load User's Name and Avatar"""

if needle not in text:
    raise SystemExit(f"patch anchor not found in {path}")
Path(path).write_text(text.replace(needle, insert, 1))
print("==> 已 patch script.js: OpenAI 设置加载后自动连接检测")
PY
