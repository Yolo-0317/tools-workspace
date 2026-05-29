#!/usr/bin/env python3
"""Merge Sub-Store / airport subscriptions into a Mihomo (Clash Meta) profile."""

from __future__ import annotations

import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests
import yaml

BASE_DIR = Path(__file__).resolve().parent
RULE_PROVIDERS = yaml.safe_load((BASE_DIR / "rule_providers.yaml").read_text(encoding="utf-8"))
RULES_ORDER = yaml.safe_load((BASE_DIR / "rules_order.yaml").read_text(encoding="utf-8"))

USER_AGENT = "clash-verge/v2.0.0"


def _split_pipe(value: str) -> list[str]:
    return [p.strip() for p in value.split("|") if p.strip()]


def _fetch_subscription(url: str, timeout: int = 60) -> str:
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        allow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text


def _decode_if_base64(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith(("proxies:", "mixed-port:", "{", "[")):
        return text
    if _looks_like_share_links(stripped):
        return stripped
    try:
        decoded = base64.b64decode(stripped + "==="[: (4 - len(stripped) % 4) % 4]).decode(
            "utf-8", errors="strict"
        )
        if decoded.strip():
            return decoded
    except Exception:
        pass
    return text


def _looks_like_share_links(body: str) -> bool:
    for line in body.splitlines()[:30]:
        s = line.strip()
        if s.startswith(
            (
                "trojan://",
                "ss://",
                "vmess://",
                "vless://",
                "hysteria://",
                "hysteria2://",
                "tuic://",
            )
        ):
            return True
    return False


def _parse_trojan(uri: str) -> dict[str, Any] | None:
    u = urlparse(uri)
    if u.scheme != "trojan" or not u.hostname:
        return None
    qs = parse_qs(u.query)
    name = unquote(u.fragment) if u.fragment else f"{u.hostname}:{u.port or 443}"
    proxy: dict[str, Any] = {
        "name": name,
        "type": "trojan",
        "server": u.hostname,
        "port": int(u.port or 443),
        "password": unquote(u.username or ""),
        "udp": True,
    }
    sni = (qs.get("sni") or [None])[0] or u.hostname
    proxy["sni"] = sni
    if (qs.get("allowInsecure") or qs.get("skip-cert-verify") or ["0"])[0] in (
        "1",
        "true",
        "True",
    ):
        proxy["skip-cert-verify"] = True
    network = (qs.get("type") or ["tcp"])[0]
    if network and network != "tcp":
        proxy["network"] = network
    return proxy


def _parse_share_link(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if line.startswith("trojan://"):
        return _parse_trojan(line)
    return None


def _parse_share_links(body: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in body.splitlines():
        proxy = _parse_share_link(line.strip())
        if proxy:
            out.append(proxy)
    return out


def _extract_proxies(raw: str) -> list[dict[str, Any]]:
    body = _decode_if_base64(raw)
    if _looks_like_share_links(body):
        return _parse_share_links(body)
    if body.lstrip().startswith("{"):
        data = json.loads(body)
        if isinstance(data, dict) and "proxies" in data:
            return list(data["proxies"])
        if isinstance(data, list):
            return data
    try:
        doc = yaml.safe_load(body)
    except yaml.YAMLError:
        return _parse_share_links(body)
    if not doc:
        return []
    if isinstance(doc, dict) and "proxies" in doc:
        return list(doc["proxies"])
    if isinstance(doc, list):
        return doc
    return []


def _prefix_proxy_names(proxies: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in proxies:
        item = dict(p)
        name = str(item.get("name", "node"))
        if label and not name.startswith(f"[{label}]"):
            item["name"] = f"[{label}]{name}"
        out.append(item)
    return out


def _dedupe_proxies(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for p in proxies:
        name = str(p.get("name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(p)
    return out


def _proxy_names(proxies: list[dict[str, Any]]) -> list[str]:
    return [str(p["name"]) for p in proxies if p.get("name")]


def build_profile(
    subscription_urls: list[str],
    source_labels: list[str],
    substore_url: str | None = None,
) -> dict[str, Any]:
    all_proxies: list[dict[str, Any]] = []

    if substore_url:
        raw = _fetch_subscription(substore_url)
        all_proxies.extend(_extract_proxies(raw))
    else:
        for idx, url in enumerate(subscription_urls):
            label = source_labels[idx] if idx < len(source_labels) else f"src{idx + 1}"
            raw = _fetch_subscription(url)
            chunk = _extract_proxies(raw)
            all_proxies.extend(_prefix_proxy_names(chunk, label))

    all_proxies = _dedupe_proxies(all_proxies)
    names = _proxy_names(all_proxies)
    if not names:
        raise ValueError("no proxies parsed — check SUBSCRIPTION_URLS or SUBSTORE_COLLECTION_URL")

    chatgpt_filter = "(?i)chatgpt"

    profile: dict[str, Any] = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "external-controller": "127.0.0.1:9090",
        "unified-delay": True,
        "tcp-concurrent": True,
        "dns": {
            "enable": True,
            "listen": "0.0.0.0:1053",
            "ipv6": False,
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "use-hosts": True,
            "default-nameserver": ["223.5.5.5", "119.29.29.29"],
            "nameserver": ["https://223.5.5.5/dns-query", "https://dns.alidns.com/dns-query"],
            "fallback": ["https://1.1.1.1/dns-query", "https://dns.google/dns-query"],
            "fallback-filter": {"geoip": True, "geoip-code": "CN"},
        },
        "proxies": all_proxies,
        "proxy-groups": [
            {
                "name": "ChatGPT",
                "type": "select",
                "include-all": True,
                "filter": chatgpt_filter,
            },
            {
                "name": "AI-优选",
                "type": "select",
                "include-all": True,
                "filter": "(?i)chatgpt|claude|gpt|ai",
            },
            {
                "name": "自动选择",
                "type": "url-test",
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "tolerance": 50,
                "proxies": names,
            },
            {
                "name": "PROXY",
                "type": "select",
                "proxies": ["自动选择", "ChatGPT", "AI-优选", "DIRECT", *names],
            },
        ],
        "rule-providers": RULE_PROVIDERS["rule-providers"],
        "rules": RULES_ORDER["rules"],
    }
    return profile


def generate_yaml() -> str:
    substore = os.environ.get("SUBSTORE_COLLECTION_URL", "").strip() or None
    urls = _split_pipe(os.environ.get("SUBSCRIPTION_URLS", ""))
    labels = _split_pipe(os.environ.get("SUB_SOURCE_LABELS", ""))

    if not substore and not urls:
        raise ValueError(
            "set SUBSTORE_COLLECTION_URL or SUBSCRIPTION_URLS in environment"
        )

    profile = build_profile(urls, labels, substore_url=substore)
    return yaml.dump(
        profile,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "clash-gen/1.0"

    def _authorized(self) -> bool:
        token = os.environ.get("CLASH_SUB_TOKEN", "").strip()
        if not token:
            return True
        qs = parse_qs(urlparse(self.path).query)
        return qs.get("token", [""])[0] == token

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if path not in ("/", "/clash.yaml", "/config.yaml"):
            self.send_error(404)
            return

        if not self._authorized():
            self.send_error(403, "invalid token")
            return

        try:
            body = generate_yaml().encode("utf-8")
        except Exception as exc:
            self.send_error(500, str(exc))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/yaml; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="clash.yaml"')
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    port = int(os.environ.get("CLASH_GEN_PORT", "8787"))
    host = os.environ.get("CLASH_GEN_HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"clash-gen listening on http://{host}:{port}/clash.yaml", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        print(generate_yaml())
    else:
        main()
