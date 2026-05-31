"""全局 Agent 互斥锁（Web 与 wechat-acp 同时只能一路活跃）。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class LockState:
    holder: str | None = None
    since: datetime | None = None


class AgentLock:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.state = LockState()

    @asynccontextmanager
    async def acquire(self, owner: str):
        if self._lock.locked():
            raise AgentBusyError(
                f"Agent 正被 {self.state.holder or '其他会话'} 占用，请稍后再试"
            )
        async with self._lock:
            self.state = LockState(holder=owner, since=datetime.now(timezone.utc))
            try:
                yield
            finally:
                self.state = LockState()

    def status(self) -> dict:
        return {
            "busy": self._lock.locked(),
            "holder": self.state.holder,
            "since": self.state.since.isoformat() if self.state.since else None,
        }


class AgentBusyError(Exception):
    pass


agent_lock = AgentLock()
