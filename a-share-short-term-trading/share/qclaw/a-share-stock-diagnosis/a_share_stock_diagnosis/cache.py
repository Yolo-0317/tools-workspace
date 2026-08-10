"""Small JSON cache restricted to public symbol and completed-bar data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from typing import Any


_ALLOWED_KINDS = frozenset({"symbols", "daily"})


def default_cache_root() -> Path:
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA")
        if base:
            return Path(base) / "a-share-stock-diagnosis"
    return Path.home() / ".cache" / "a-share-stock-diagnosis"


class PublicDataCache:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_cache_root()

    @staticmethod
    def _validate(kind: str, key: str) -> None:
        if kind not in _ALLOWED_KINDS:
            raise ValueError("缓存仅允许 symbols 和 daily 公共数据")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
            raise ValueError("缓存键包含非法字符")

    def _path(self, kind: str, key: str) -> Path:
        self._validate(kind, key)
        return self.root / kind / f"{key}.json"

    def read(self, kind: str, key: str, max_age: timedelta | None) -> Any | None:
        path = self._path(kind, key)
        try:
            if max_age is not None:
                age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
                if age > max_age.total_seconds():
                    return None
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def write(self, kind: str, key: str, payload: Any) -> None:
        path = self._path(kind, key)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(path)

