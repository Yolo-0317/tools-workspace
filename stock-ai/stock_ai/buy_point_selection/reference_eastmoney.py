"""Eastmoney raw announcement adapter used as an audited CNInfo fallback."""

from __future__ import annotations

from datetime import date, datetime
import math
from time import sleep as default_sleep
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import requests

from .reference_sources import Announcement, AnnouncementPage, ProviderFailure


EASTMONEY_ANNOUNCEMENT_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
EASTMONEY_NOTICE_ROOT = "https://data.eastmoney.com/notices/detail/"
SHANGHAI = ZoneInfo("Asia/Shanghai")
Sleep = Callable[[float], None]


class EastmoneyAnnouncementProvider:
    """Fetch complete raw A-share announcement pages without invoking any AI diagnosis."""

    provider_name = "EASTMONEY"

    def __init__(
        self,
        *,
        session: Any | None = None,
        page_size: int = 100,
        timeout_seconds: float = 20.0,
        request_interval_seconds: float = 0.5,
        sleep: Sleep = default_sleep,
    ) -> None:
        if page_size <= 0 or page_size > 100:
            raise ValueError("page_size must be in [1, 100]")
        if request_interval_seconds < 0:
            raise ValueError("request_interval_seconds must not be negative")
        self._session = session or requests.Session()
        self._page_size = page_size
        self._timeout_seconds = timeout_seconds
        self._request_interval_seconds = request_interval_seconds
        self._sleep = sleep
        self._request_started = False

    def fetch_announcement_page(self, day: date, page_no: int) -> AnnouncementPage:
        if page_no <= 0:
            raise ValueError("page_no must be positive")
        params = {
            "sr": "-1",
            "page_size": str(self._page_size),
            "page_index": str(page_no),
            "ann_type": "SHA,SZA",
            "client_source": "web",
            "f_node": "0",
            "s_node": "0",
            "begin_time": day.isoformat(),
            "end_time": day.isoformat(),
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://data.eastmoney.com/notices/hsa/5.html",
            "User-Agent": "stock-ai-reference-sync/1.0",
        }
        try:
            if self._request_started and self._request_interval_seconds:
                self._sleep(self._request_interval_seconds)
            self._request_started = True
            response = self._session.get(
                EASTMONEY_ANNOUNCEMENT_URL,
                params=params,
                headers=headers,
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            raise ProviderFailure(
                self.provider_name, "announcements", "PROVIDER_UNAVAILABLE"
            ) from exc
        if response.status_code in {403, 429, 567}:
            raise ProviderFailure(
                self.provider_name, "announcements", "PROVIDER_RATE_LIMITED"
            )
        if response.status_code >= 500:
            raise ProviderFailure(
                self.provider_name, "announcements", "PROVIDER_UNAVAILABLE"
            )
        if response.status_code != 200:
            raise ProviderFailure(
                self.provider_name, "announcements", "PROVIDER_SCHEMA_CHANGED"
            )
        try:
            payload = response.json()
            data = payload["data"]
            total_count = int(data["total_hits"])
            raw_records = data["list"] or []
            returned_page = int(data["page_index"])
            returned_size = int(data["page_size"])
            if (
                payload.get("success") not in {1, True}
                or total_count < 0
                or not isinstance(raw_records, list)
                or returned_page != page_no
                or returned_size != self._page_size
            ):
                raise ValueError("invalid announcement response metadata")
            records = tuple(self._announcement(row) for row in raw_records)
            identities = [row.announcement_id for row in records]
            if len(identities) != len(set(identities)):
                raise ValueError("duplicate announcement id")
            page_count = math.ceil(total_count / self._page_size)
            if page_count and page_no > page_count:
                raise ValueError("page exceeds declared count")
            return AnnouncementPage(
                records=records,
                total_count=total_count,
                page_no=page_no,
                page_size=self._page_size,
                page_count=page_count,
            )
        except ProviderFailure:
            raise
        except Exception as exc:
            raise ProviderFailure(
                self.provider_name, "announcements", "PROVIDER_SCHEMA_CHANGED"
            ) from exc

    @staticmethod
    def _announcement(row: Mapping[str, object]) -> Announcement:
        announcement_id = str(row.get("art_code") or "").strip()
        title = str(row.get("title") or "").strip()
        codes = row.get("codes")
        if not isinstance(codes, list):
            raise ValueError("announcement codes must be a list")
        eligible = [
            str(item.get("stock_code") or "").strip()
            for item in codes
            if isinstance(item, Mapping)
            and str(item.get("ann_type") or "").startswith("A")
        ]
        code = next((value for value in eligible if value.isdigit()), "")
        if not announcement_id or not title or not code:
            raise ValueError("announcement identity, title and code are required")
        published_at = None
        raw_time = str(row.get("eiTime") or "").strip()
        if raw_time:
            published_at = datetime.strptime(
                raw_time, "%Y-%m-%d %H:%M:%S:%f"
            ).replace(tzinfo=SHANGHAI)
        return Announcement(
            code=code.zfill(6),
            announcement_id=announcement_id,
            title=title,
            published_at=published_at,
            official_url=f"{EASTMONEY_NOTICE_ROOT}{code.zfill(6)}/{announcement_id}.html",
        )
