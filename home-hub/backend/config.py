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

    stock_ai_root: Path = Path(
        os.getenv("STOCK_AI_ROOT", str(ROOT.parent / "stock-ai"))
    ).expanduser()

    trust_proxy: bool = _truthy("HUB_TRUST_PROXY", "1")

    # 公开财经 API 防护（/api/dashboard/news/*）
    news_public_guard: bool = _truthy("HUB_NEWS_PUBLIC_GUARD", "1")
    news_rate_per_min: int = int(os.getenv("HUB_NEWS_RATE_PER_MIN", "45"))
    news_rate_burst: int = int(os.getenv("HUB_NEWS_RATE_BURST", "12"))
    news_rate_burst_window: int = int(os.getenv("HUB_NEWS_RATE_BURST_WINDOW", "10"))
    news_strict_rate_per_min: int = int(os.getenv("HUB_NEWS_STRICT_PER_MIN", "8"))
    news_auth_rate_per_min: int = int(os.getenv("HUB_NEWS_AUTH_RATE_PER_MIN", "120"))
    news_max_limit: int = int(os.getenv("HUB_NEWS_MAX_LIMIT", "100"))

    @property
    def news_allowed_hosts(self) -> frozenset[str]:
        raw = os.getenv(
            "HUB_NEWS_ALLOWED_HOSTS",
            "127.0.0.1,localhost,hub.yoloworld.site",
        )
        hosts = {h.strip().lower() for h in raw.split(",") if h.strip()}
        return frozenset(hosts)


settings = Settings()
