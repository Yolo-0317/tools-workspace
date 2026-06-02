"""公开财经 API 防护：限流、反爬 UA、客户端标识、参数上限。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.services.rate_limit import SlidingWindowLimiter

PUBLIC_NEWS_PREFIX = "/api/dashboard/news"
HUB_CLIENT_HEADER = "x-hub-client"
EXPECTED_HUB_CLIENT = "home-hub"

# 常见脚本/爬虫 UA（小写匹配子串）
_BLOCKED_UA_SUBSTRINGS = (
    "python-requests",
    "aiohttp/",
    "httpx/",
    "scrapy/",
    "curl/",
    "wget/",
    "go-http-client",
    "java/",
    "libwww-perl",
    "okhttp/",
    "postmanruntime",
    "insomnia/",
)

_limiter_public: SlidingWindowLimiter | None = None
_limiter_burst: SlidingWindowLimiter | None = None
_limiter_strict: SlidingWindowLimiter | None = None
_limiter_auth: SlidingWindowLimiter | None = None


def _limiter_public_inst() -> SlidingWindowLimiter:
    global _limiter_public
    if _limiter_public is None:
        _limiter_public = SlidingWindowLimiter(
            max_events=settings.news_rate_per_min,
            window_seconds=60.0,
        )
    return _limiter_public


def _limiter_burst_inst() -> SlidingWindowLimiter:
    global _limiter_burst
    if _limiter_burst is None:
        _limiter_burst = SlidingWindowLimiter(
            max_events=settings.news_rate_burst,
            window_seconds=float(settings.news_rate_burst_window),
        )
    return _limiter_burst


def _limiter_strict_inst() -> SlidingWindowLimiter:
    global _limiter_strict
    if _limiter_strict is None:
        _limiter_strict = SlidingWindowLimiter(
            max_events=settings.news_strict_rate_per_min,
            window_seconds=60.0,
        )
    return _limiter_strict


def _limiter_auth_inst() -> SlidingWindowLimiter:
    global _limiter_auth
    if _limiter_auth is None:
        _limiter_auth = SlidingWindowLimiter(
            max_events=settings.news_auth_rate_per_min,
            window_seconds=60.0,
        )
    return _limiter_auth


def is_public_news_path(path: str) -> bool:
    return path.startswith(PUBLIC_NEWS_PREFIX)


def client_ip(request: Request) -> str:
    if settings.trust_proxy:
        forwarded = (request.headers.get("X-Forwarded-For") or "").strip()
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
        real_ip = (request.headers.get("X-Real-IP") or "").strip()
        if real_ip:
            return real_ip[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return "unknown"


def _has_hub_client(request: Request) -> bool:
    return (request.headers.get(HUB_CLIENT_HEADER) or "").strip().lower() == EXPECTED_HUB_CLIENT


def _ua_blocked(ua: str) -> bool:
    raw = (ua or "").strip().lower()
    if not raw:
        return True
    return any(token in raw for token in _BLOCKED_UA_SUBSTRINGS)


def _origin_allowed(request: Request) -> bool:
    """有 Origin/Referer 时须为本站或配置白名单。"""
    allowed = settings.news_allowed_hosts
    for header in ("origin", "referer"):
        value = (request.headers.get(header) or "").strip()
        if not value:
            continue
        try:
            host = urlparse(value).hostname or ""
        except Exception:
            return False
        if host and host.lower() in allowed:
            continue
        return False
    return True


def _clamp_limit_param(request: Request) -> JSONResponse | None:
    raw = request.query_params.get("limit")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"detail": "limit 须为整数"},
        )
    if value < 1 or value > settings.news_max_limit:
        return JSONResponse(
            status_code=400,
            content={"detail": f"limit 须在 1～{settings.news_max_limit} 之间"},
        )
    return None


def check_public_news_request(
    request: Request,
    *,
    authenticated: bool,
    api_token_ok: bool,
) -> JSONResponse | None:
    """未通过时返回 JSONResponse；通过返回 None。"""
    if not settings.news_public_guard:
        return None

    if request.method.upper() != "GET":
        return JSONResponse(status_code=405, content={"detail": "Method Not Allowed"})

    if api_token_ok:
        return _clamp_limit_param(request)

    bad_limit = _clamp_limit_param(request)
    if bad_limit is not None:
        return bad_limit

    ip = client_ip(request)
    ua = request.headers.get("user-agent") or ""

    if _ua_blocked(ua):
        return JSONResponse(
            status_code=403,
            content={"detail": "请求被拒绝"},
            headers={"Cache-Control": "no-store"},
        )

    has_client = _has_hub_client(request)
    if not authenticated and not has_client:
        ok, retry = _limiter_strict_inst().allow(f"strict:{ip}")
        if not ok:
            return _rate_limited(retry, reason="strict")

    if not authenticated and not _origin_allowed(request):
        return JSONResponse(
            status_code=403,
            content={"detail": "来源未授权"},
            headers={"Cache-Control": "no-store"},
        )

    if authenticated:
        ok, retry = _limiter_auth_inst().allow(f"auth:{ip}")
    else:
        ok, retry = _limiter_public_inst().allow(f"pub:{ip}")
    if not ok:
        return _rate_limited(retry, reason="rate")

    ok_burst, retry_burst = _limiter_burst_inst().allow(f"burst:{ip}")
    if not ok_burst:
        return _rate_limited(retry_burst, reason="burst")

    return None


def _rate_limited(retry_after: int, *, reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "请求过于频繁，请稍后再试", "reason": reason},
        headers={
            "Retry-After": str(max(1, retry_after)),
            "Cache-Control": "no-store",
        },
    )


def guard_settings_snapshot() -> dict[str, Any]:
    return {
        "enabled": settings.news_public_guard,
        "rate_per_min": settings.news_rate_per_min,
        "burst": settings.news_rate_burst,
        "strict_per_min": settings.news_strict_rate_per_min,
        "max_limit": settings.news_max_limit,
    }
