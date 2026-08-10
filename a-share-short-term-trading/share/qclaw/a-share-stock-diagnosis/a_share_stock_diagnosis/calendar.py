"""Strict SSE calendar backed by an audited annual closure snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path


@dataclass(frozen=True)
class BundledTradingCalendar:
    year: int
    closed_weekdays: frozenset[date]
    source_url: str

    @classmethod
    def load(cls, path: Path) -> "BundledTradingCalendar":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            year = int(payload["year"])
            source_url = str(payload["source_url"])
            closed = frozenset(date.fromisoformat(item) for item in payload["closed_weekdays"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("交易日历文件无效") from exc
        if not source_url.startswith("https://www.sse.com.cn/"):
            raise ValueError("交易日历来源必须是上交所 HTTPS 页面")
        if any(item.year != year or item.weekday() >= 5 for item in closed):
            raise ValueError("交易日历休市日期无效")
        return cls(year=year, closed_weekdays=closed, source_url=source_url)

    def status(self, value: date) -> bool | None:
        if value.year != self.year:
            return None
        if value.weekday() >= 5:
            return False
        return value not in self.closed_weekdays

    def latest_on_or_before(self, value: date) -> date | None:
        current = value
        for _ in range(370):
            status = self.status(current)
            if status is None:
                return None
            if status:
                return current
            current -= timedelta(days=1)
        return None

    def next_on_or_after(self, value: date) -> date | None:
        current = value
        for _ in range(370):
            status = self.status(current)
            if status is None:
                return None
            if status:
                return current
            current += timedelta(days=1)
        return None

