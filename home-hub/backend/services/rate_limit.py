"""进程内滑动窗口限流（单 worker launchd 场景）。"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, *, max_events: int, window_seconds: float) -> None:
        self.max_events = max(1, max_events)
        self.window_seconds = max(1.0, window_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """返回 (是否允许, Retry-After 秒)。"""
        now = time.monotonic()
        with self._lock:
            q = self._events[key]
            cutoff = now - self.window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_events:
                retry = max(1, int(q[0] + self.window_seconds - now) + 1)
                return False, retry
            q.append(now)
            if len(self._events) > 5000:
                self._prune_locked(now)
            return True, 0

    def _prune_locked(self, now: float) -> None:
        cutoff = now - self.window_seconds
        stale = [k for k, q in self._events.items() if not q or q[-1] < cutoff]
        for k in stale[:2000]:
            self._events.pop(k, None)
