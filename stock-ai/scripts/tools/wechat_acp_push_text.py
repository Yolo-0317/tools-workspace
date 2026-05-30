#!/usr/bin/env python3
"""Push plain text to WeChat via wechat-acp instance token (iLink sendmessage API)."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import uuid
from pathlib import Path

import requests

INSTANCE = os.environ.get("WECHAT_ACP_INSTANCE", "tools-workspace")
INSTANCE_DIR = Path.home() / ".wechat-acp" / "instances" / INSTANCE
TOKEN_FILE = INSTANCE_DIR / "token.json"
STATE_FILE = INSTANCE_DIR / "state.json"
CHANNEL_VERSION = "1.0.2"
MESSAGE_TYPE_BOT = 2
MESSAGE_STATE_FINISH = 2
TEXT_CHUNK_LIMIT = 4000


def _random_wechat_uin() -> str:
    import base64

    uin = secrets.randbits(32)
    return base64.b64encode(str(uin).encode()).decode()


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"❌ 未找到: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_target(target: str | None, state: dict, token_data: dict) -> str:
    if target:
        return target
    if state.get("lastActiveUserId"):
        return str(state["lastActiveUserId"])
    if token_data.get("userId"):
        return str(token_data["userId"])
    raise SystemExit("❌ 未指定推送目标，且 state/token 中无 lastActiveUserId")


def _context_token(state: dict, target: str) -> str:
    users = state.get("users") or {}
    entry = users.get(target) or {}
    token = entry.get("contextToken")
    if isinstance(token, str) and token:
        return token
    raise SystemExit(
        "❌ 缺少 context_token：请先在微信给 wechat-acp 机器人发一条消息，再重试推送。"
    )


def _split_text(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    segments: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            segments.append(remaining)
            break
        break_at = remaining.rfind("\n", 0, max_len)
        if break_at <= 0:
            break_at = max_len
        segments.append(remaining[:break_at])
        remaining = remaining[break_at:].lstrip("\n")
    return segments


def _api_post(base_url: str, endpoint: str, body: dict, token: str) -> dict:
    url = f"{base_url.rstrip('/')}/{endpoint}"
    payload = {**body, "base_info": {"channel_version": CHANNEL_VERSION}}
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {token}",
        "X-WECHAT-UIN": _random_wechat_uin(),
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    raw = resp.text.strip()
    return json.loads(raw) if raw else {}


def send_wechat_acp_text(
    text: str,
    *,
    target: str | None = None,
    instance: str = INSTANCE,
) -> list[str]:
    instance_dir = Path.home() / ".wechat-acp" / "instances" / instance
    token_data = _load_json(instance_dir / "token.json")
    state = _load_json(instance_dir / "state.json")

    to_user = _resolve_target(target, state, token_data)
    context_token = _context_token(state, to_user)
    base_url = str(token_data.get("baseUrl", "https://ilinkai.weixin.qq.com"))
    bot_token = str(token_data["token"])

    client_ids: list[str] = []
    for segment in _split_text(text, TEXT_CHUNK_LIMIT):
        client_id = f"wechat-acp-{uuid.uuid4()}"
        data = _api_post(
            base_url,
            "ilink/bot/sendmessage",
            {
                "msg": {
                    "from_user_id": "",
                    "to_user_id": to_user,
                    "client_id": client_id,
                    "message_type": MESSAGE_TYPE_BOT,
                    "message_state": MESSAGE_STATE_FINISH,
                    "context_token": context_token,
                    "item_list": [{"type": 1, "text_item": {"text": segment}}],
                },
            },
            bot_token,
        )
        ret = data.get("ret", 0)
        if ret != 0:
            errmsg = data.get("errmsg") or data.get("errMsg") or ""
            raise SystemExit(
                f"❌ 微信 API ret={ret} errmsg={errmsg}\n"
                "   context_token 可能已过期，请向 wechat-acp 机器人发一条消息后重试。"
            )
        client_ids.append(client_id)
    return client_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Push text via wechat-acp iLink token")
    parser.add_argument("text_file", nargs="?", help="Text file (default: stdin)")
    parser.add_argument("--target", default=os.environ.get("WECHAT_TARGET"))
    parser.add_argument("--instance", default=INSTANCE)
    args = parser.parse_args()

    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()
    else:
        text = sys.stdin.read().strip()

    if not text:
        print("❌ 消息内容为空", file=sys.stderr)
        return 1

    ids = send_wechat_acp_text(text, target=args.target, instance=args.instance)
    print(f"✅ 微信推送成功（wechat-acp/{args.instance}）segments={len(ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
