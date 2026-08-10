"""Track active WebSocket device sessions for MCP-triggered playback."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from server.ws_server import DeviceSession

log = logging.getLogger(__name__)


class PlaybackSession(Protocol):
    session_id: str

    async def play_quark_from_mcp(
        self,
        query: str,
        *,
        user_text: str = "",
        media_hint: str = "any",
    ) -> dict:
        ...


_sessions: dict[str, PlaybackSession] = {}
_last_active_id: str | None = None


def register(session: PlaybackSession) -> None:
    global _last_active_id
    _sessions[session.session_id] = session
    _last_active_id = session.session_id
    log.info("Device registered for MCP playback session=%s", session.session_id)


def unregister(session_id: str) -> None:
    global _last_active_id
    _sessions.pop(session_id, None)
    if _last_active_id == session_id:
        _last_active_id = next(iter(_sessions), None)
    log.info("Device unregistered session=%s", session_id)


def touch(session_id: str) -> None:
    global _last_active_id
    if session_id in _sessions:
        _last_active_id = session_id


def get_active_session() -> PlaybackSession | None:
    if _last_active_id and _last_active_id in _sessions:
        return _sessions[_last_active_id]
    if len(_sessions) == 1:
        return next(iter(_sessions.values()))
    return None


def status() -> dict:
    return {
        "connected": len(_sessions),
        "active_session_id": _last_active_id,
        "session_ids": list(_sessions.keys()),
        "ts": int(time.time()),
    }
