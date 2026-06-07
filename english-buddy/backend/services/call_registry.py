"""In-process registry of active WebSocket voice-call sessions."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CallRecord:
    session_id: str
    connected_at: float = field(default_factory=time.time)
    user_id: Optional[str] = None
    username: Optional[str] = None
    call_started: bool = False
    call_mode: str = ""
    lesson_id: Optional[str] = None
    program_id: Optional[str] = None

    def public_dict(self) -> Dict[str, Any]:
        now = time.time()
        return {
            "session_id": self.session_id,
            "username": self.username or "匿名",
            "call_started": self.call_started,
            "call_mode": self.call_mode or None,
            "lesson_id": self.lesson_id,
            "program_id": self.program_id,
            "connected_seconds": max(0, int(now - self.connected_at)),
        }


class CallRegistry:
    def __init__(self) -> None:
        self._sessions: Dict[str, CallRecord] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        *,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> str:
        session_id = uuid.uuid4().hex
        record = CallRecord(
            session_id=session_id,
            user_id=user_id,
            username=username,
        )
        async with self._lock:
            self._sessions[session_id] = record
        return session_id

    async def unregister(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def update(self, session_id: str, **fields: Any) -> None:
        async with self._lock:
            record = self._sessions.get(session_id)
            if not record:
                return
            for key, value in fields.items():
                if hasattr(record, key):
                    setattr(record, key, value)

    async def read_along_active_count(
        self, *, exclude_session_id: Optional[str] = None
    ) -> int:
        async with self._lock:
            return sum(
                1
                for sid, record in self._sessions.items()
                if sid != exclude_session_id
                and record.call_started
                and record.call_mode == "read_along"
            )

    async def free_chat_active_count(
        self, *, exclude_session_id: Optional[str] = None
    ) -> int:
        async with self._lock:
            return sum(
                1
                for sid, record in self._sessions.items()
                if sid != exclude_session_id
                and record.call_started
                and record.call_mode == "free"
            )

    async def snapshot(self) -> Dict[str, Any]:
        from services.free_chat_limits import max_free_chat_sessions
        from services.read_along_limits import max_read_along_sessions

        async with self._lock:
            records = list(self._sessions.values())
        connected = len(records)
        calls_started = sum(1 for r in records if r.call_started)
        read_along_active = sum(
            1
            for r in records
            if r.call_started and r.call_mode == "read_along"
        )
        free_chat_active = sum(
            1
            for r in records
            if r.call_started and r.call_mode == "free"
        )
        read_along_max = max_read_along_sessions()
        free_chat_max = max_free_chat_sessions()
        return {
            "connected": connected,
            "calls_started": calls_started,
            "read_along_active": read_along_active,
            "read_along_max": read_along_max,
            "read_along_full": read_along_active >= read_along_max,
            "free_chat_active": free_chat_active,
            "free_chat_max": free_chat_max,
            "free_chat_full": free_chat_active >= free_chat_max,
            "sessions": [r.public_dict() for r in records],
        }


call_registry = CallRegistry()
