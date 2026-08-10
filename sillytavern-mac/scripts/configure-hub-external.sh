#!/usr/bin/env bash
# Hub 外网 / iPhone 访问：修复「发了像没发、后端却有回复」
# 1) CSRF 403 -> /api/chats/save 失败，气泡不落盘（configure 关 CSRF + 重启 ST）
# 2) Caddy encode gzip 在 ST 反代之后 -> 流式响应被缓冲，手机端不回显（sidestore-infra Caddyfile 已把 hub_apps 移到 gzip 前）
#
# 用法:
#   bash scripts/configure-hub-external.sh
#   MOBILE_HUB=1 bash scripts/configure-hub-external.sh   # 外网保守：关 OpenAI 流式，等整段再显示
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$ROOT/vendor/SillyTavern/config.yaml"
SETTINGS="$ROOT/vendor/SillyTavern/data/default-user/settings.json"
MOBILE_HUB="${MOBILE_HUB:-1}"

if [[ ! -f "$CFG" ]]; then
  echo "错误: 缺少 $CFG"
  exit 1
fi

python3 << PY
import json
import re
from pathlib import Path

cfg = Path("$CFG")
text = cfg.read_text(encoding="utf-8")

def set_yaml_bool(key: str, value: bool) -> None:
    global text
    val = "true" if value else "false"
    pat = re.compile(rf"^{re.escape(key)}:\s*(true|false)\s*$", re.M)
    if pat.search(text):
        text = pat.sub(f"{key}: {val}", text, count=1)
    else:
        text = text.rstrip() + f"\n{key}: {val}\n"

set_yaml_bool("enableForwardedWhitelist", False)
set_yaml_bool("disableCsrfProtection", True)
cfg.write_text(text, encoding="utf-8")
print("config.yaml:")
print("  enableForwardedWhitelist=false")
print("  disableCsrfProtection=true")

mobile = "$MOBILE_HUB" == "1"
settings_path = Path("$SETTINGS")
if settings_path.exists():
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    oai = settings.setdefault("oai_settings", {})
    if mobile:
        oai["stream_openai"] = False
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        print("settings.json: stream_openai=false (MOBILE_HUB=1，外网整段返回再显示)")
    else:
        print(f"settings.json: stream_openai={oai.get('stream_openai', True)} (不变)")
PY

bash "$ROOT/scripts/patch-hub-subpath.sh"
bash "$ROOT/scripts/patch-hub-proxy.sh"
bash "$ROOT/scripts/patch-mobile-send-echo.sh"

echo ""
echo "==> 须重启服务后生效："
echo "  # SillyTavern（读 config.yaml CSRF 开关）"
echo "  launchctl kickstart -k gui/$(id -u)/com.user.sillytavern"
echo ""
echo "  # Caddy（若刚改过 sidestore-infra/caddy/Caddyfile 的 gzip 顺序）"
echo "  cd ../sidestore-infra && docker compose restart caddy"
echo ""
echo "==> 手机端操作"
echo "  1. 固定入口: https://hub.yoloworld.site:8883/silly/ （末尾要有 /）"
echo "  2. Safari/Chrome 清除该站点数据，或无痕窗口打开"
echo "  3. 硬刷新后进角色 -> 新建聊天（旧聊可能已脏）"
echo ""
echo "==> 仍异常时可试"
echo "  MOBILE_HUB=1 bash scripts/configure-hub-external.sh && 重启 ST"
echo "  （关流式，慢但外网更稳）"
