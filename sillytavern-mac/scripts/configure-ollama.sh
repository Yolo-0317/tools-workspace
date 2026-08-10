#!/usr/bin/env bash
# 将本机 Ollama 接入 SillyTavern（Chat Completion / Custom OpenAI API）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ST_DATA="$ROOT/vendor/SillyTavern/data/default-user"
SETTINGS="$ST_DATA/settings.json"
SECRETS="$ST_DATA/secrets.json"

OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-}"

if ! curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null; then
  echo "错误: Ollama 未运行或不可达: ${OLLAMA_HOST}"
  echo "请先启动 Ollama，或设置 OLLAMA_HOST"
  exit 1
fi

if [[ -z "$OLLAMA_MODEL" ]]; then
  OLLAMA_MODEL="$(curl -sf "${OLLAMA_HOST}/api/tags" | python3 -c "
import sys, json
models = json.load(sys.stdin).get('models', [])
if not models:
    raise SystemExit('no models')
print(models[0]['name'])
")"
fi

echo "==> Ollama 模型: $OLLAMA_MODEL"
echo "==> API 端点: ${OLLAMA_HOST}/v1"

python3 - "$SETTINGS" "$SECRETS" "$OLLAMA_HOST" "$OLLAMA_MODEL" <<'PY'
import json
import sys
import uuid
from pathlib import Path

settings_path, secrets_path, ollama_host, model = sys.argv[1:5]
endpoint = ollama_host.rstrip("/") + "/v1"

settings = json.loads(Path(settings_path).read_text())
settings["main_api"] = "openai"
power = settings.setdefault("power_user", {})
power["auto_connect"] = True
oai = settings.setdefault("oai_settings", {})
oai["chat_completion_source"] = "custom"
oai["custom_url"] = endpoint
oai["custom_model"] = model
oai["squash_system_messages"] = True
oai["temp_openai"] = 0.9
oai["top_p_openai"] = 0.95
oai["stream_openai"] = True
oai["openai_max_context"] = 8192
oai["openai_max_tokens"] = 512
Path(settings_path).write_text(json.dumps(settings, indent=4, ensure_ascii=False) + "\n")

secrets = {}
if Path(secrets_path).exists():
    secrets = json.loads(Path(secrets_path).read_text() or "{}")

key = "api_key_custom"
entries = secrets.get(key) or []
for e in entries:
    e["active"] = False
entries.append({
    "id": str(uuid.uuid4()),
    "value": "ollama",
    "label": "Ollama local",
    "active": True,
})
secrets[key] = entries
secrets["_migrated"] = "1"
Path(secrets_path).write_text(json.dumps(secrets, indent=4, ensure_ascii=False) + "\n")

print("已写入 settings.json 与 secrets.json")
PY

bash "$(dirname "$0")/patch-openai-autoconnect.sh"

echo ""
echo "完成。请刷新浏览器 http://127.0.0.1:8792/"
echo "已开启 auto_connect：页面加载后会自动检测 Ollama 连接"
echo "API 类型应为 Chat Completion -> Custom (OpenAI-compatible)"
echo "Endpoint: ${OLLAMA_HOST}/v1"
echo "Model: ${OLLAMA_MODEL}"
