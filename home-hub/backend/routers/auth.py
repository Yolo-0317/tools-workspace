"""登录 / 会话 / 当前用户。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.config import settings
from backend.services import hub_auth, session_store

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


def _cookie_secure(request: Request) -> bool:
    if settings.session_cookie_secure:
        return True
    if settings.trust_proxy:
        proto = (
            request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        )
        if proto == "https":
            return True
    return False


def _set_session_cookie(response: Response, request: Request, token: str, expires) -> None:
    response.set_cookie(
        key=hub_auth.SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=_cookie_secure(request),
        samesite=settings.session_cookie_samesite,
        max_age=int(settings.session_ttl_hours * 3600),
        path=settings.session_cookie_path,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=hub_auth.SESSION_COOKIE, path=settings.session_cookie_path
    )
    # 迁移：清掉旧版 Path=/hub/ 的会话
    if settings.session_cookie_path.rstrip("/") != "/hub":
        response.delete_cookie(key=hub_auth.SESSION_COOKIE, path="/hub/")


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict[str, Any]:
    account = hub_auth.authenticate(body.username, body.password)
    if not account:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token, _expires = session_store.create_session(account.username, account.role)
    _set_session_cookie(response, request, token, _expires)
    return {
        "ok": True,
        "username": account.username,
        "role": account.role,
        "share_only": account.role == "share",
    }


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(hub_auth.SESSION_COOKIE, "")
    if token:
        session_store.delete_session(token)
    _clear_session_cookie(response)
    return {"ok": True}


@router.get("/whoami")
async def whoami(request: Request) -> dict[str, Any]:
    role = getattr(request.state, "hub_role", None)
    username = getattr(request.state, "hub_user", None)
    if not settings.require_auth:
        return {
            "authenticated": True,
            "role": "admin",
            "username": username,
            "share_only": False,
        }
    if not username or not role:
        raise HTTPException(status_code=401, detail="未登录")
    return {
        "authenticated": True,
        "role": role,
        "username": username,
        "share_only": role == "share",
    }
