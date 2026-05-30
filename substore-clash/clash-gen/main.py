#!/usr/bin/env python3
"""Merge Sub-Store / airport subscriptions into a Mihomo (Clash Meta) profile."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
import time
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

# 定时从机场 SUBSCRIPTION_URLS 拉取并生成 YAML（秒）；0 = 仅请求时现拉
DEFAULT_REFRESH_SECONDS = 6 * 3600

_cache_lock = threading.Lock()
_cached_yaml: bytes | None = None
_cached_yaml_verge: bytes | None = None
_cache_updated_at: float = 0.0
_cache_error: str | None = None

# Clash Verge 启动：少规则集、少测速、lazy url-test
VERGE_NODE_LIMIT = 50
# 轻量配置内联 OpenAI 规则（不拉 rule-providers）
VERGE_CHATGPT_RULES: tuple[str, ...] = (
    "DOMAIN-SUFFIX,openai.com,ChatGPT",
    "DOMAIN-SUFFIX,chatgpt.com,ChatGPT",
    "DOMAIN-SUFFIX,oaistatic.com,ChatGPT",
    "DOMAIN-SUFFIX,oaiusercontent.com,ChatGPT",
    "DOMAIN-KEYWORD,openai,ChatGPT",
)

# 与 Loyalsoldier clash-rules 的 rule-providers 一一对应（reject 用内置 REJECT）
LOYAL_GROUP_NAMES = (
    "applications",
    "private",
    "icloud",
    "apple",
    "google",
    "direct",
    "gfw",
    "tld-not-cn",
    "lancidr",
    "cncidr",
    "telegramcidr",
)
# 默认走代理/可选节点的类别（其余规则组默认 DIRECT 优先）
LOYAL_PROXY_FRIENDLY = frozenset(
    {"google", "telegramcidr", "gfw", "tld-not-cn"}
)


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
    if stripped.startswith(
        ("proxies:", "mixed-port:", "port:", "socks-port:", "{", "[")
    ):
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
        return [_normalize_proxy(p) for p in doc["proxies"] if isinstance(p, dict)]
    if isinstance(doc, list):
        return [_normalize_proxy(p) for p in doc if isinstance(p, dict)]
    return []


def _is_invalid_server(server: Any) -> bool:
    host = str(server or "").strip()
    if not host:
        return True
    if host in _INVALID_SERVERS:
        return True
    if host.startswith("127.0.0."):
        return True
    return False


def _is_unsupported_proxy(proxy: dict[str, Any]) -> bool:
    """Drop placeholder / unsupported transports (Stash rejects these on import)."""
    name = str(proxy.get("name", ""))
    if PLACEHOLDER_NODE_PATTERN.search(name):
        return True
    if _is_invalid_server(proxy.get("server")):
        return True
    network = str(proxy.get("network", "")).lower()
    if network in _UNSUPPORTED_NETWORKS:
        return True
    return False


def _normalize_proxy(proxy: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single outbound; ensure required fields for ClashMi / Mihomo / Stash."""
    drop = {"proxy-groups", "rules", "rule-providers", "dns", "mixed-port", "socks-port", "redir-port"}
    out = {k: v for k, v in proxy.items() if k not in drop and v is not None}
    if "name" in out:
        out["name"] = str(out["name"]).strip()

    ptype = str(out.get("type", "")).lower()
    if ptype == "vless":
        # VLESS 无 alterId/cipher；保留会导致 Stash 解析失败
        out.pop("alterId", None)
        out.pop("cipher", None)

    if "port" in out:
        try:
            out["port"] = int(out["port"])
        except (TypeError, ValueError):
            pass

    defaults: dict[str, dict[str, Any]] = {
        "trojan": {"port": 443, "udp": True},
        "ss": {"port": 443},
        "vmess": {"port": 443, "alterId": 0},
        "vless": {"port": 443},
    }
    for key, val in defaults.get(ptype, {"port": 443}).items():
        out.setdefault(key, val)

    if not out.get("port"):
        out["port"] = 443
    if ptype == "trojan" and not out.get("sni") and out.get("server"):
        out.setdefault("sni", out["server"])

    # Stash 3.x 依赖节点级 benchmark 参数触发延迟测试
    out.setdefault("benchmark-url", STASH_BENCHMARK_URL)
    out.setdefault("benchmark-timeout", 5)

    return out


def _filter_names(names: list[str], pattern: str) -> list[str]:
    rx = re.compile(pattern)
    return [n for n in names if rx.search(n)]


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


# 不纳入配置的商业/游戏线路（节点名匹配即丢弃）
EXCLUDED_NODE_PATTERN = re.compile(r"商务|游戏")
# 机场订阅里的信息/占位节点（127.0.0.x、0.0.0.0 等，Stash 导入会失败）
PLACEHOLDER_NODE_PATTERN = re.compile(
    r"[-—]{4,}|剩余[:：]|官网[:：]|下载新客户端|最新客户端|一元机场\.asia"
)
_INVALID_SERVERS = frozenset({"0.0.0.0", "127.0.0.1"})
_UNSUPPORTED_NETWORKS = frozenset({"xhttp"})
# Stash 文档推荐 HTTP；gstatic 204 用于 url-test 组级探测
STASH_BENCHMARK_URL = "http://www.apple.com"
URL_TEST_URL = "http://www.gstatic.com/generate_204"
# 分区 url-test：Stash iOS 对单组 50+ 节点常不在启动时跑完测速
AUTO_REGIONS: tuple[tuple[str, str], ...] = (
    ("自动选择-港", r"香港|HK|沪港"),
    ("自动选择-日", r"日本|JP"),
    ("自动选择-美", r"美国|US"),
    ("自动选择-台", r"台湾|TW"),
)
AUTO_SELECT_NAME = "自动选择"
# Stash iOS 单组测速上限（过多节点启动时不跑完）
AUTO_REGION_NODE_LIMIT = 10


def _node_benchmark_priority(name: str) -> tuple[int, str]:
    """Prefer 空闲 > 均衡 > default > 爆满 for url-test shortlists."""
    if "空闲" in name:
        rank = 0
    elif "均衡" in name:
        rank = 1
    elif "爆满" in name:
        rank = 3
    else:
        rank = 2
    return (rank, name)


def _exclude_unwanted_proxies(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        p
        for p in proxies
        if not EXCLUDED_NODE_PATTERN.search(str(p.get("name", "")))
        and not _is_unsupported_proxy(p)
    ]


def _select_group(name: str, proxies: list[str]) -> dict[str, Any]:
    """Select group; preferred option must be first (Stash rejects top-level `default`)."""
    group: dict[str, Any] = {"name": name, "type": "select", "proxies": proxies}
    # Stash：含 url-test 子组时加 interval，触发递归测速
    if AUTO_SELECT_NAME in proxies or any(p.startswith("自动选择-") for p in proxies):
        group["interval"] = 120
    return group


def _url_test_group(
    name: str, members: list[str], *, lazy: bool = False
) -> dict[str, Any]:
    """url-test group tuned for Stash (no lazy — Stash skips idle probes when lazy: true)."""
    group: dict[str, Any] = {
        "name": name,
        "type": "url-test",
        "url": URL_TEST_URL,
        "interval": 120,
        "tolerance": 50,
        "proxies": members,
    }
    if lazy:
        group["lazy"] = True
        group["interval"] = 300
    return group


def _build_auto_select_groups(names: list[str]) -> list[dict[str, Any]]:
    """Tier-1 regional url-test + tier-2 自动选择 (Stash recurses into child groups)."""
    groups: list[dict[str, Any]] = []
    region_group_names: list[str] = []
    assigned: set[str] = set()

    for region_name, pattern in AUTO_REGIONS:
        region_nodes = sorted(
            [n for n in names if re.search(pattern, n, re.I)],
            key=_node_benchmark_priority,
        )[:AUTO_REGION_NODE_LIMIT]
        if not region_nodes:
            continue
        region_group_names.append(region_name)
        assigned.update(region_nodes)
        groups.append(_url_test_group(region_name, region_nodes))

    others = [n for n in names if n not in assigned]
    if others:
        others = sorted(others, key=_node_benchmark_priority)[:AUTO_REGION_NODE_LIMIT]
        region_group_names.append("自动选择-其他")
        groups.append(_url_test_group("自动选择-其他", others))

    if not region_group_names:
        return [_url_test_group(AUTO_SELECT_NAME, names)]

    if len(region_group_names) == 1:
        # 单区节点：扁平 url-test，避免多余嵌套
        only = groups[0]
        only["name"] = AUTO_SELECT_NAME
        return [only]

    groups.append(_url_test_group(AUTO_SELECT_NAME, region_group_names))
    return groups


def _build_loyal_policy_groups() -> list[dict[str, Any]]:
    """Loyalsoldier 同名策略组；禁止组间互相引用，避免 loop is detected。"""
    groups: list[dict[str, Any]] = []
    for name in LOYAL_GROUP_NAMES:
        if name in LOYAL_PROXY_FRIENDLY:
            proxies = [AUTO_SELECT_NAME, "ChatGPT", "DIRECT"]
        else:
            proxies = ["DIRECT", AUTO_SELECT_NAME]
        groups.append(_select_group(name, proxies))
    return groups


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
    all_proxies = _exclude_unwanted_proxies(all_proxies)
    names = _proxy_names(all_proxies)
    if not names:
        raise ValueError("no proxies parsed — check SUBSCRIPTION_URLS or SUBSTORE_COLLECTION_URL")

    chatgpt_nodes = _filter_names(names, r"(?i)chatgpt")
    chatgpt_group = (
        [AUTO_SELECT_NAME, "DIRECT", *chatgpt_nodes]
        if chatgpt_nodes
        else [AUTO_SELECT_NAME, "DIRECT"]
    )

    config = _base_profile_dict(all_proxies)
    config["proxy-groups"] = [
        *_build_auto_select_groups(names),
        _select_group("ChatGPT", chatgpt_group),
        *_build_loyal_policy_groups(),
        _select_group("PROXY", [AUTO_SELECT_NAME, "ChatGPT", "DIRECT"]),
        _select_group("GLOBAL", ["PROXY", AUTO_SELECT_NAME, "ChatGPT", "DIRECT"]),
    ]
    config["rule-providers"] = RULE_PROVIDERS["rule-providers"]
    config["rules"] = RULES_ORDER["rules"]
    return config


def _base_profile_dict(all_proxies: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "external-controller": os.environ.get(
            "CLASH_EXTERNAL_CONTROLLER", "127.0.0.1:9097"
        ),
        "profile": {
            "store-selected": True,
            "store-fake-ip": True,
        },
        "dns": {
            "enable": True,
            "ipv6": False,
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "default-nameserver": ["223.5.5.5", "119.29.29.29"],
            "nameserver": ["223.5.5.5", "119.29.29.29"],
            "fallback": ["1.1.1.1", "8.8.8.8"],
            "fallback-filter": {"geoip": True, "geoip-code": "CN"},
        },
        "proxies": all_proxies,
    }


def build_profile_verge(
    subscription_urls: list[str],
    source_labels: list[str],
    substore_url: str | None = None,
) -> dict[str, Any]:
    """Clash Verge 轻量配置：无 rule-providers，避免首次激活长时间下载/测速转圈。"""
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
    all_proxies = _exclude_unwanted_proxies(all_proxies)
    names = _proxy_names(all_proxies)
    if not names:
        raise ValueError("no proxies parsed — check SUBSCRIPTION_URLS or SUBSTORE_COLLECTION_URL")

    shortlist = sorted(names, key=_node_benchmark_priority)[:VERGE_NODE_LIMIT]
    chatgpt_nodes = _filter_names(names, r"(?i)chatgpt")
    include_names = list(dict.fromkeys([*shortlist, *chatgpt_nodes]))
    include_set = set(include_names)
    verge_proxies = []
    for p in all_proxies:
        if str(p.get("name", "")) not in include_set:
            continue
        item = {k: v for k, v in p.items() if k not in ("benchmark-url", "benchmark-timeout")}
        verge_proxies.append(item)
    chatgpt_in_profile = [n for n in chatgpt_nodes if n in include_set]
    chatgpt_group = (
        [AUTO_SELECT_NAME, "DIRECT", *chatgpt_in_profile]
        if chatgpt_in_profile
        else [AUTO_SELECT_NAME, "DIRECT"]
    )
    config = _base_profile_dict(verge_proxies)
    config.pop("external-controller", None)
    config["proxy-groups"] = [
        _url_test_group(AUTO_SELECT_NAME, shortlist),
        _select_group("ChatGPT", chatgpt_group),
        _select_group("PROXY", [AUTO_SELECT_NAME, "ChatGPT", "DIRECT"]),
        _select_group("GLOBAL", ["PROXY", AUTO_SELECT_NAME, "ChatGPT", "DIRECT"]),
    ]
    config["rules"] = [
        "GEOIP,LAN,DIRECT",
        "GEOIP,CN,DIRECT",
        *VERGE_CHATGPT_RULES,
        f"MATCH,{AUTO_SELECT_NAME}",
    ]
    return config


def _dump_yaml(profile: dict[str, Any]) -> str:
    """YAML safe for ClashMi / Mihomo (explicit proxies on every group)."""

    class Dumper(yaml.SafeDumper):
        pass

    def _str_repr(dumper: yaml.SafeDumper, value: str) -> Any:
        if value.startswith("(?i)") or (":" in value and "%" in value):
            return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="'")
        return dumper.represent_scalar("tag:yaml.org,2002:str", value)

    Dumper.add_representer(str, _str_repr)
    return yaml.dump(
        profile,
        Dumper=Dumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def _profile_sources() -> tuple[list[str], list[str], str | None]:
    substore = os.environ.get("SUBSTORE_COLLECTION_URL", "").strip() or None
    urls = _split_pipe(os.environ.get("SUBSCRIPTION_URLS", ""))
    labels = _split_pipe(os.environ.get("SUB_SOURCE_LABELS", ""))
    if not substore and not urls:
        raise ValueError(
            "set SUBSTORE_COLLECTION_URL or SUBSCRIPTION_URLS in environment"
        )
    return urls, labels, substore


def generate_yaml(*, verge: bool = False) -> str:
    urls, labels, substore = _profile_sources()
    if verge:
        profile = build_profile_verge(urls, labels, substore_url=substore)
    else:
        profile = build_profile(urls, labels, substore_url=substore)
    return _dump_yaml(profile)


def _refresh_interval_seconds() -> int:
    raw = os.environ.get("SUBSCRIPTION_REFRESH_SECONDS", "").strip()
    if not raw:
        return DEFAULT_REFRESH_SECONDS
    return max(0, int(raw))


def refresh_cache() -> None:
    """从机场/Sub-Store 拉取最新节点并更新内存缓存。"""
    global _cached_yaml, _cached_yaml_verge, _cache_updated_at, _cache_error
    try:
        body = generate_yaml(verge=False).encode("utf-8")
        body_verge = generate_yaml(verge=True).encode("utf-8")
    except Exception as exc:
        with _cache_lock:
            _cache_error = str(exc)
        sys.stderr.write(f"clash-gen refresh failed: {exc}\n")
        raise
    with _cache_lock:
        _cached_yaml = body
        _cached_yaml_verge = body_verge
        _cache_updated_at = time.time()
        _cache_error = None
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(_cache_updated_at))
    sys.stderr.write(
        f"clash-gen refreshed at {ts} (full {len(body)}B, verge {len(body_verge)}B)\n"
    )


def _get_yaml_bytes(*, force: bool = False, verge: bool = False) -> bytes:
    interval = _refresh_interval_seconds()
    if interval <= 0 and not force:
        return generate_yaml(verge=verge).encode("utf-8")

    if force:
        refresh_cache()
        with _cache_lock:
            cached = _cached_yaml_verge if verge else _cached_yaml
            assert cached is not None
            return cached

    with _cache_lock:
        cached = _cached_yaml_verge if verge else _cached_yaml
        if cached is not None:
            return cached
        err = _cache_error

    if err:
        raise RuntimeError(err)
    refresh_cache()
    with _cache_lock:
        cached = _cached_yaml_verge if verge else _cached_yaml
        assert cached is not None
        return cached


def _background_refresh_loop() -> None:
    interval = _refresh_interval_seconds()
    if interval <= 0:
        return
    while True:
        try:
            refresh_cache()
        except Exception:
            pass
        time.sleep(interval)


def _start_background_refresh() -> None:
    interval = _refresh_interval_seconds()
    if interval <= 0:
        sys.stderr.write(
            "clash-gen: SUBSCRIPTION_REFRESH_SECONDS=0, fetch on each /clash.yaml request\n"
        )
        return
    threading.Thread(target=_background_refresh_loop, daemon=True).start()
    sys.stderr.write(
        f"clash-gen: background refresh every {interval}s ({interval // 3600}h)\n"
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "clash-gen/1.0"
    protocol_version = "HTTP/1.1"

    def _authorized(self) -> bool:
        token = os.environ.get("CLASH_SUB_TOKEN", "").strip()
        if not token:
            return True
        qs = parse_qs(urlparse(self.path).query)
        return qs.get("token", [""])[0] == token

    def _yaml_route(self) -> tuple[bool, bool] | None:
        """Return (verge, force) for YAML routes, or None if not a YAML path."""
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        if path not in (
            "/",
            "/clash.yaml",
            "/config.yaml",
            "/clash-verge.yaml",
            "/verge.yaml",
        ):
            return None
        verge = path in ("/clash-verge.yaml", "/verge.yaml") or qs.get("verge", [""])[
            0
        ] in ("1", "true", "yes")
        force = qs.get("force", [""])[0] in ("1", "true", "yes")
        return verge, force

    def _send_yaml(self, *, verge: bool, force: bool, send_body: bool) -> None:
        if not self._authorized():
            self.send_error(403, "invalid token")
            return
        try:
            body = _get_yaml_bytes(force=force, verge=verge)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        fname = "clash-verge.yaml" if verge else "clash.yaml"
        self.send_response(200)
        self.send_header("Content-Type", "text/yaml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        with _cache_lock:
            if _cache_updated_at:
                self.send_header("X-Cache-Updated", str(int(_cache_updated_at)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path in ("/health", "/healthz"):
            payload = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            return
        route = self._yaml_route()
        if route is None:
            self.send_error(404)
            return
        self._send_yaml(verge=route[0], force=route[1], send_body=False)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            with _cache_lock:
                age = (
                    int(time.time() - _cache_updated_at)
                    if _cache_updated_at
                    else -1
                )
            self.wfile.write(f"ok cache_age_sec={age}\n".encode())
            return

        if path in ("/refresh", "/refresh/"):
            if not self._authorized():
                self.send_error(403, "invalid token")
                return
            try:
                refresh_cache()
                with _cache_lock:
                    ts = _cache_updated_at
                    nbytes = len(_cached_yaml or b"")
                msg = json.dumps(
                    {"ok": True, "updated_at": ts, "bytes": nbytes},
                    ensure_ascii=False,
                )
            except Exception as exc:
                self.send_error(500, str(exc))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(msg.encode())
            return

        route = self._yaml_route()
        if route is None:
            self.send_error(404)
            return
        self._send_yaml(verge=route[0], force=route[1], send_body=True)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    port = int(os.environ.get("CLASH_GEN_PORT", "8787"))
    host = os.environ.get("CLASH_GEN_HOST", "0.0.0.0")
    _start_background_refresh()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"clash-gen listening on http://{host}:{port}/clash.yaml", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        print(generate_yaml())
    else:
        main()
