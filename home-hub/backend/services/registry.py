"""本地服务目录、健康探针、Jellyfin staging 映射。"""

from __future__ import annotations

import asyncio
import os
import socket
import ssl
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml

from backend.config import ROOT

SERVICES_YAML = ROOT / "config" / "services.yaml"


def _load_service_env_files() -> None:
    """读取常见 .env（仅用于「是否已配置」展示，不暴露值）。"""
    from dotenv import load_dotenv

    candidates = [
        ROOT / ".env",
        ROOT.parent / "stock-mysql" / ".env",
        ROOT.parent / "stock-ai" / ".env",
        ROOT.parent / "sidestore-infra" / ".env",
        ROOT.parent / "substore-clash" / ".env",
        Path.home() / "docker" / "jellyfin-stack" / ".env",
        ROOT.parent / "wechat-cursor-acp" / ".env",
        ROOT.parent / "harryputter" / ".env",
    ]
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)


def _expand(path: str) -> Path:
    return Path(path).expanduser()


def load_catalog_raw() -> dict[str, Any]:
    if not SERVICES_YAML.is_file():
        return {"categories": [], "domains": {}, "jellyfin": {}}
    with SERVICES_YAML.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


_CREDENTIAL_ALIASES: dict[str, list[str]] = {
    "HARRYPUTTER_ADMIN_USER": ["READALONG_ADMIN_USER"],
    "HARRYPUTTER_ADMIN_PASSWORD": ["READALONG_ADMIN_PASSWORD"],
}


def _env_credential_status(names: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in names or []:
        val = os.getenv(name, "")
        if not val.strip():
            for alt in _CREDENTIAL_ALIASES.get(name, []):
                val = os.getenv(alt, "")
                if val.strip():
                    break
        out[name] = "已配置" if val.strip() else "未设置"
    return out


def _check_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_http(url: str, timeout: float = 5.0, *, insecure: bool = False) -> bool:
    try:
        req = Request(url, method="GET", headers={"User-Agent": "home-hub/1.0"})
        ctx = None
        if insecure and url.startswith("https://"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            return 200 <= resp.status < 500
    except (URLError, OSError, ValueError):
        return False


def _check_process(match: str) -> bool:
    try:
        out = subprocess.run(
            ["pgrep", "-fl", match],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        return out.returncode == 0 and bool(out.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_health(spec: dict[str, Any] | None) -> dict[str, Any]:
    if not spec:
        return {"status": "unknown", "detail": "无探针配置"}
    kind = spec.get("type")
    if kind == "tcp":
        ok = _check_tcp(str(spec.get("host", "127.0.0.1")), int(spec.get("port", 0)))
        return {"status": "up" if ok else "down", "type": "tcp"}
    if kind in ("http", "https"):
        url = str(spec.get("url", ""))
        insecure = bool(spec.get("insecure")) or kind == "https"
        timeout = float(spec.get("timeout", 5.0))
        ok = _check_http(url, timeout=timeout, insecure=insecure) if url else False
        return {"status": "up" if ok else "down", "type": kind, "url": url}
    if kind == "process":
        pattern = str(spec.get("match", ""))
        ok = _check_process(pattern) if pattern else False
        return {"status": "up" if ok else "down", "type": "process", "match": pattern}
    return {"status": "unknown", "detail": f"未知类型 {kind}"}


def _docker_running_names() -> set[str]:
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
        if out.returncode != 0:
            return set()
        return {line.strip() for line in out.stdout.splitlines() if line.strip()}
    except (OSError, subprocess.TimeoutExpired):
        return set()


def _parse_staging_line(line: str, fmt: str, staging_prefix: str) -> dict[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.split("|")]
    if fmt == "sd-tv" and len(parts) >= 4:
        src_path, src_folder, show, season = parts[0], parts[1], parts[2], parts[3]
        return {
            "source": f"{src_path}/{src_folder}",
            "staging": f"{staging_prefix}/{show}/Season {season.zfill(2)}",
            "title": show,
            "season": season,
        }
    if len(parts) >= 2:
        src_path, title = parts[0], parts[1]
        return {
            "source": src_path,
            "staging": f"{staging_prefix}/{title}",
            "title": title,
            "season": "",
        }
    return {"source": line, "staging": staging_prefix, "title": line, "season": ""}


def load_jellyfin_mappings() -> dict[str, Any]:
    raw = load_catalog_raw()
    jcfg = raw.get("jellyfin") or {}
    stack_dir = _expand(str(jcfg.get("stack_dir", "~/docker/jellyfin-stack")))
    libraries: list[dict[str, Any]] = []

    for entry in jcfg.get("staging_lists") or []:
        rel = str(entry.get("file", ""))
        path = stack_dir / rel
        library = str(entry.get("library", ""))
        staging_prefix = str(entry.get("staging_prefix", ""))
        fmt = str(entry.get("format", "nas-tv"))
        rows: list[dict[str, str]] = []
        if path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                parsed = _parse_staging_line(line, fmt, staging_prefix)
                if parsed:
                    rows.append(parsed)
        libraries.append(
            {
                "library": library,
                "list_file": str(path),
                "staging_prefix": staging_prefix,
                "count": len(rows),
                "items": rows[:80],
            }
        )

    return {
        "stack_dir": str(stack_dir),
        "libraries": libraries,
        "total_items": sum(x["count"] for x in libraries),
    }


def build_catalog(*, with_health: bool = True) -> dict[str, Any]:
    _load_service_env_files()
    raw = load_catalog_raw()
    domains = raw.get("domains") or {}
    docker_names = _docker_running_names()
    categories: list[dict[str, Any]] = []

    for cat in raw.get("categories") or []:
        items_out: list[dict[str, Any]] = []
        for item in cat.get("items") or []:
            compose_dir = item.get("compose_dir")
            container = item.get("docker_container")
            public_url = item.get("public_url")
            internal_url = item.get("internal_url")
            if not internal_url and public_url:
                ext = str(domains.get("external_https_port", 8883))
                intr = str(domains.get("internal_https_port", 8443))
                if f":{ext}" in public_url:
                    internal_url = public_url.replace(f":{ext}", f":{intr}", 1)

            row = {
                "id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description", ""),
                "local_url": item.get("local_url"),
                "dev_url": item.get("dev_url"),
                "internal_url": internal_url,
                "public_url": public_url,
                "public_note": item.get("public_note"),
                "health_note": item.get("health_note"),
                "doc": item.get("doc"),
                "compose_dir": str(_expand(compose_dir)) if compose_dir else None,
                "docker_container": container,
                "docker_running": bool(container and container in docker_names),
                "credentials": _env_credential_status(item.get("credentials_env")),
            }
            if with_health:
                row["health"] = check_health(item.get("health"))
            items_out.append(row)
        categories.append(
            {
                "id": cat.get("id"),
                "name": cat.get("name"),
                "items": items_out,
            }
        )

    base = domains.get("base", "yoloworld.site")
    ext_port = domains.get("external_https_port", 8883)
    return {
        "domains": {
            **domains,
            "public_https_hint": f"https://*.{base}:{ext_port}",
        },
        "categories": categories,
        "docker_containers_running": sorted(docker_names),
    }


async def build_catalog_async(*, with_health: bool = True) -> dict[str, Any]:
    return await asyncio.to_thread(build_catalog, with_health=with_health)


async def load_jellyfin_mappings_async() -> dict[str, Any]:
    return await asyncio.to_thread(load_jellyfin_mappings)
