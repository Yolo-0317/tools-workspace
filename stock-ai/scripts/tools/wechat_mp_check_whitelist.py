#!/usr/bin/env python3
"""监控家用公网 IP 与微信公众号 API 白名单是否仍有效。"""

from __future__ import annotations

import argparse
import json
import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    append_alert,
    check_api_reachable,
    get_public_ip,
    mp_configured,
)


def _maybe_push_wechat(message: str) -> None:
    if not message.strip():
        return
    try:
        from scripts.tools.wechat_acp_push_text import send_wechat_acp_text

        send_wechat_acp_text(message)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 微信推送失败: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查公众号 API IP 白名单与 token")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--push-wechat", action="store_true", help="异常时推送到 wechat-acp")
    parser.add_argument("--show-ip", action="store_true", help="仅打印当前公网 IP")
    args = parser.parse_args()

    if args.show_ip:
        print(get_public_ip())
        return 0

    if not mp_configured():
        msg = "未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET，见 stock-ai/.env.example"
        print(f"❌ {msg}", file=sys.stderr)
        return 1

    result = check_api_reachable()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        ip = result["current_ip"]
        print(f"OK 公众号 API 可达，公网 IP={ip}")
    else:
        print(f"❌ {result.get('errmsg') or result}", file=sys.stderr)
        if result.get("ip_whitelist_error"):
            print(
                "   → 请在微信开发者平台更新 IP 白名单: "
                f"{result.get('current_ip')}",
                file=sys.stderr,
            )

    if not result["ok"]:
        append_alert(json.dumps(result, ensure_ascii=False))
        if args.push_wechat:
            lines = [
                "【公众号 API 告警】",
                f"当前 IP: {result.get('current_ip')}",
                f"期望 IP: {result.get('expected_ip') or '（未设 WECHAT_MP_WHITELIST_IP）'}",
                f"错误: {result.get('errmsg')}",
            ]
            if result.get("ip_whitelist_error"):
                lines.append("请在微信开发者平台更新 IP 白名单后重试。")
            _maybe_push_wechat("\n".join(lines))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
