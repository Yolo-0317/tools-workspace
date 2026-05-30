#!/usr/bin/env python3
"""Push plain text to WeChat via openclaw-weixin ilink API (with context_token)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import time
import uuid
from pathlib import Path

import requests

STATE_DIR = Path(os.environ.get("OPENCLAW_STATE_DIR", Path.home() / ".qclaw"))
DEFAULT_ACCOUNT = "04080d9366d0-im-bot"
DEFAULT_TARGET = "o9cq801H5ip_q8SH3ogvkQhhNI2s@im.wechat"
ILINK_APP_ID = "bot"
CHANNEL_VERSION = "2.4.1"
MESSAGE_TYPE_BOT = 2
MESSAGE_ITEM_TEXT = 1
MESSAGE_STATE_FINISH = 2


def _build_client_version(version: str = CHANNEL_VERSION) -> int:
    parts = [int(x) for x in version.split(".")]
    major, minor, patch = (parts + [0, 0, 0])[:3]
    return ((major & 0xFF) << 16) | ((minor & 0xFF) << 8) | (patch & 0xFF)


def _load_account(account_id: str) -> dict:
    path = STATE_DIR / "openclaw-weixin" / "accounts" / f"{account_id}.json"
    if not path.exists():
        raise SystemExit(f"❌ 未找到微信账号配置: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_context_token(account_id: str, target: str) -> str | None:
    path = STATE_DIR / "openclaw-weixin" / "accounts" / f"{account_id}.context-tokens.json"
    if not path.exists():
        return None
    tokens = json.loads(path.read_text(encoding="utf-8"))
    token = tokens.get(target)
    return token if isinstance(token, str) and token else None


def send_weixin_text(
    text: str,
    *,
    account_id: str = DEFAULT_ACCOUNT,
    target: str = DEFAULT_TARGET,
) -> dict:
    context_token = _load_context_token(account_id, target)
    if not context_token:
        raise SystemExit(
            "❌ 缺少 context_token：请先在微信给 QClaw 机器人发任意一条消息，再重试推送。"
        )

    account = _load_account(account_id)
    base_url = account.get("baseUrl", "https://ilinkai.weixin.qq.com").rstrip("/") + "/"
    bot_token = account["token"]
    client_id = f"openclaw-weixin:{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
    uin = secrets.randbits(32)
    wechat_uin = base64.b64encode(str(uin).encode()).decode()

    body = {
        "msg": {
            "from_user_id": "",
            "to_user_id": target,
            "client_id": client_id,
            "message_type": MESSAGE_TYPE_BOT,
            "message_state": MESSAGE_STATE_FINISH,
            "item_list": [{"type": MESSAGE_ITEM_TEXT, "text_item": {"text": text}}],
            "context_token": context_token,
        },
        "base_info": {
            "channel_version": CHANNEL_VERSION,
            "bot_agent": "OpenClaw",
        },
    }

    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {bot_token}",
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": str(_build_client_version()),
        "X-WECHAT-UIN": wechat_uin,
    }

    resp = requests.post(
        f"{base_url}ilink/bot/sendmessage",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        timeout=20,
    )
    resp.raise_for_status()
    raw = resp.text.strip()
    data = json.loads(raw) if raw else {}
    ret = data.get("ret", 0)
    if ret != 0:
        errmsg = data.get("errmsg") or data.get("errMsg") or ""
        raise SystemExit(
            f"❌ 微信 API ret={ret} errmsg={errmsg}\n"
            "   context_token 可能已过期，请向 QClaw 机器人发一条消息后重试。"
        )
    return {"ret": ret, "client_id": client_id, "raw": data}


def main() -> int:
    parser = argparse.ArgumentParser(description="Push text to WeChat via openclaw-weixin")
    parser.add_argument("text_file", nargs="?", help="Text file to send (default: stdin)")
    parser.add_argument("--account", default=os.environ.get("WEIXIN_ACCOUNT_ID", DEFAULT_ACCOUNT))
    parser.add_argument("--target", default=os.environ.get("WEIXIN_TARGET", DEFAULT_TARGET))
    args = parser.parse_args()

    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()
    else:
        text = sys.stdin.read().strip()

    if not text:
        print("❌ 消息内容为空", file=sys.stderr)
        return 1

    result = send_weixin_text(text, account_id=args.account, target=args.target)
    print(f"✅ 微信推送成功 client_id={result['client_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
