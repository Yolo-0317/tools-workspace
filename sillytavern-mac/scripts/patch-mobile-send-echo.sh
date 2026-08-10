#!/usr/bin/env bash
# 用户消息先上屏、再 /api/chats/save（外网 Hub 保存慢时，原逻辑会卡住 addOneMessage）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/vendor/SillyTavern/public/script.js"
MARKER="sillytavern-mac: mobile-send-echo"

if [[ ! -f "$SCRIPT" ]]; then
  echo "错误: 未找到 $SCRIPT"
  exit 1
fi

if grep -q "$MARKER" "$SCRIPT"; then
  echo "已 patch: mobile-send-echo"
  exit 0
fi

python3 << PY
from pathlib import Path

path = Path("$SCRIPT")
text = path.read_text(encoding="utf-8")

old = """    } else {
        chat.push(message);
        await saveChatConditional();
        const chat_id = (chat.length - 1);
        await eventSource.emit(event_types.MESSAGE_SENT, chat_id);
        addOneMessage(message);
        await eventSource.emit(event_types.USER_MESSAGE_RENDERED, chat_id);
    }"""

new = """    } else {
        chat.push(message);
        const chat_id = (chat.length - 1);
        await eventSource.emit(event_types.MESSAGE_SENT, chat_id);
        addOneMessage(message); // $MARKER
        await eventSource.emit(event_types.USER_MESSAGE_RENDERED, chat_id);
        await saveChatConditional();
    }"""

if old not in text:
    raise SystemExit("未找到 sendMessageAsUser 预期代码块，SillyTavern 版本可能已变，请手动检查 script.js")

path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("已 patch sendMessageAsUser: 先 addOneMessage 再 saveChatConditional")
PY
