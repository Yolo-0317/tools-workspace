"""Home Hub 账号与访问控制。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from backend.config import settings
from backend.services.passwords import verify_password

HubRole = Literal["admin", "share"]

SESSION_COOKIE = "hub_session"

# 分享账号仅可读选股相关 API
SHARE_API_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/auth/logout",
    "/api/auth/whoami",
    "/api/dashboard/selection",
)

PUBLIC_API_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/auth/login",
    # 财经快讯（东财 7×24 + AI 解读快照，只读）
    "/api/dashboard/news",
)


@dataclass(frozen=True)
class HubAccount:
    username: str
    password: str
    role: HubRole


def list_accounts() -> list[HubAccount]:
    accounts: list[HubAccount] = []
    if settings.admin_username and settings.admin_password:
        accounts.append(
            HubAccount(settings.admin_username, settings.admin_password, "admin")
        )
    if settings.share_username and settings.share_password:
        accounts.append(
            HubAccount(settings.share_username, settings.share_password, "share")
        )
    return accounts


def authenticate(username: str, password: str) -> HubAccount | None:
    name = username.strip()
    for account in list_accounts():
        if account.username != name:
            continue
        stored = account.password
        if stored.startswith("pbkdf2_sha256$"):
            if verify_password(password, stored):
                return account
        elif stored == password:
            return account
    return None


def public_api_allowed(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in PUBLIC_API_PREFIXES)


def share_api_allowed(path: str, method: str) -> bool:
    if method.upper() not in {"GET", "POST"}:
        return False
    return any(path.startswith(prefix) for prefix in SHARE_API_PREFIXES)


def sanitize_selection_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.pop("holding_codes", None)
    return out
