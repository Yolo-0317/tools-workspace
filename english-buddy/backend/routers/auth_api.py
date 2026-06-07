"""Login / session / current user."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from services.free_chat_access import (
    free_chat_enabled_for_username,
    free_chat_users_public,
)
from services.stt_access import stt_enabled_for_username, stt_users_public
from pydantic import BaseModel, Field

from services.auth_deps import get_optional_user, require_user
from services.auth_settings import (
    SESSION_COOKIE,
    cookie_path,
    cookie_samesite,
    cookie_secure,
    require_auth,
    session_ttl_hours,
)
from services.session_store import create_session, delete_session
from services.user_store import authenticate

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
        max_age=int(session_ttl_hours() * 3600),
        path=cookie_path(),
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path=cookie_path())


@router.get("/config")
async def auth_config(request: Request) -> dict[str, Any]:
    user = get_optional_user(request)
    username = user["username"] if user else None
    return {
        "require_auth": require_auth(),
        "stt_enabled_for_me": stt_enabled_for_username(username),
        "stt_users": stt_users_public(),
        "free_chat_enabled_for_me": free_chat_enabled_for_username(username),
        "free_chat_users": free_chat_users_public(),
    }


@router.post("/login")
async def login(body: LoginBody, response: Response) -> dict[str, Any]:
    if not require_auth():
        raise HTTPException(status_code=503, detail="未启用登录（请配置 ENGLISH_BUDDY_USERS）")
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token, _expires = create_session(user["id"])
    _set_session_cookie(response, token)
    return {
        "ok": True,
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
    }


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        delete_session(token)
    _clear_session_cookie(response)
    return {"ok": True}


@router.get("/whoami")
async def whoami(request: Request) -> dict[str, Any]:
    if not require_auth():
        return {"authenticated": False, "require_auth": False}
    user = get_optional_user(request)
    if not user:
        return {"authenticated": False, "require_auth": True}
    return {
        "authenticated": True,
        "require_auth": True,
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
    }
