"""Structured JSONL logs for logged-in voice / read-along sessions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ws_call import CallSession

_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = _ROOT / "logs" / "call-sessions.jsonl"
_TEXT_CLIP = 240


def _enabled() -> bool:
    return os.getenv("CALL_SESSION_LOG", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _clip(text: str | None) -> str:
    if not text:
        return ""
    s = " ".join(str(text).split())
    if len(s) <= _TEXT_CLIP:
        return s
    return s[: _TEXT_CLIP - 1] + "…"


def log_call_event(session: CallSession, event: str, **fields: Any) -> None:
    """Append one JSON line when the user is logged in (username set)."""
    if not _enabled():
        return
    user = (getattr(session, "username", None) or "").strip()
    if not user:
        return
    row: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "event": event,
        "user": user,
        "session_id": getattr(session, "registry_id", "") or "",
        "call_mode": getattr(session, "call_mode", ""),
        "lesson_id": getattr(session, "lesson_id", None),
        "stt_enabled": bool(getattr(session, "stt_enabled", False)),
    }
    for key, val in fields.items():
        if val is None:
            continue
        if key in ("expected", "spoken", "merged", "stt_text", "assistant"):
            row[key] = _clip(str(val))
        elif key in ("coverage", "pcm_ms"):
            row[key] = round(float(val), 3) if val != "" else val
        else:
            row[key] = val
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
