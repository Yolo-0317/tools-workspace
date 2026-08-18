#!/usr/bin/env python3
"""探测 api.weixin.qq.com 各 IPv4 目标对应的微信侧出口。"""

from __future__ import annotations

import argparse
import json
import socket
from ipaddress import IPv4Address
from typing import Any

import requests

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (  # noqa: E402
    API_BASE,
    FixedWeChatAPIAdapter,
    _mp_parse_json,
    invalid_ip_from_error,
    mp_credentials,
)


def resolve_api_ipv4() -> list[str]:
    answers = socket.getaddrinfo(
        "api.weixin.qq.com",
        443,
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
    )
    return sorted({str(IPv4Address(item[4][0])) for item in answers})


def _public_probe_result(
    *,
    target_ip: str,
    token: str,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "target_ip": target_ip,
        "ok": bool(token) and not error,
        "errcode": (error or {}).get("errcode"),
        "observed_egress_ip": invalid_ip_from_error(error),
    }


def probe_target(ip: str) -> dict[str, Any]:
    target_ip = str(IPv4Address(ip))
    appid, secret = mp_credentials()
    if not appid or not secret:
        return _public_probe_result(
            target_ip=target_ip,
            token="",
            error={"errcode": -1, "errmsg": "公众号凭证未配置"},
        )

    session = requests.Session()
    session.trust_env = False
    session.mount(
        "https://api.weixin.qq.com/",
        FixedWeChatAPIAdapter(resolve_ip=target_ip),
    )
    try:
        response = session.get(
            f"{API_BASE}/token",
            params={
                "grant_type": "client_credential",
                "appid": appid,
                "secret": secret,
            },
            timeout=20,
        )
        data = _mp_parse_json(response)
    except requests.RequestException:
        data = {"errcode": -2, "errmsg": "网络请求失败"}

    token = str(data.get("access_token") or "")
    error = data if data.get("errcode") or not token else None
    return _public_probe_result(
        target_ip=target_ip,
        token=token,
        error=error,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="探测微信公众号 API 目标与出口映射")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="只探测指定 IPv4，可重复传入；默认探测当前全部 A 记录",
    )
    args = parser.parse_args()
    targets = [str(IPv4Address(ip)) for ip in args.target] or resolve_api_ipv4()
    results = [probe_target(ip) for ip in targets]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if any(item["ok"] or item["observed_egress_ip"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
