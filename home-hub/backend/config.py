"""Home Hub 运行时配置。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "chat.db"

load_dotenv(ROOT / ".env")


def _truthy(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    host: str = os.getenv("HUB_HOST", "127.0.0.1")
    port: int = int(os.getenv("HUB_PORT", "8780"))
    api_token: str = os.getenv("HUB_API_TOKEN", "").strip()

    require_auth: bool = _truthy("HUB_REQUIRE_AUTH", "1")
    admin_username: str = os.getenv("HUB_ADMIN_USER", "admin").strip()
    admin_password: str = os.getenv("HUB_ADMIN_PASSWORD", "").strip()
    share_username: str = os.getenv("HUB_SHARE_USER", "share").strip()
    share_password: str = os.getenv("HUB_SHARE_PASSWORD", "").strip()
    session_ttl_hours: int = int(os.getenv("HUB_SESSION_TTL_HOURS", "168"))
    session_cookie_secure: bool = _truthy("HUB_SESSION_COOKIE_SECURE", "0")
    session_cookie_samesite: str = os.getenv("HUB_SESSION_COOKIE_SAMESITE", "lax").strip().lower()

    agent_model: str = os.getenv("HUB_AGENT_MODEL", "auto")
    agent_cwd: Path = Path(
        os.getenv(
            "HUB_AGENT_CWD",
            str(ROOT.parent / "stock-ai" / "investment-agent"),
        )
    ).expanduser()
    forward_thoughts: bool = _truthy("HUB_FORWARD_THOUGHTS")

    chat_rate_limit: int = int(os.getenv("HUB_CHAT_RATE_LIMIT", "10"))
    session_idle_hours: int = int(os.getenv("HUB_SESSION_IDLE_HOURS", "24"))
    agent_run_timeout: int = int(os.getenv("HUB_AGENT_RUN_TIMEOUT", "120"))
    agent_acp_prompt_timeout: int = int(os.getenv("HUB_ACP_PROMPT_TIMEOUT", "600"))

    stock_ai_root: Path = Path(
        os.getenv("STOCK_AI_ROOT", str(ROOT.parent / "stock-ai"))
    ).expanduser()


settings = Settings()
