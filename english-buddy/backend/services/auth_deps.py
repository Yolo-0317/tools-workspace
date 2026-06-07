"""FastAPI auth dependencies."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

from services.auth_settings import SESSION_COOKIE, require_auth
from services.session_store import get_session
from services.user_store import get_user_by_id


def _session_user(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE, "")
    sess = get_session(token)
    if not sess:
        return None
    return get_user_by_id(sess["user_id"])


def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    if not require_auth():
        return None
    return _session_user(request)


def require_user(request: Request) -> dict:
    if not require_auth():
        raise HTTPException(status_code=503, detail="未配置登录账号")
    user = _session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def ws_user_from_cookies(cookies: Dict[str, str]) -> Optional[Dict[str, Any]]:
    if not require_auth():
        return None
    token = cookies.get(SESSION_COOKIE, "")
    sess = get_session(token)
    if not sess:
        return None
    return get_user_by_id(sess["user_id"])
