"""CNInfo adapter for SW industry history and fully-audited announcement pages."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
import math
from typing import Any
from zoneinfo import ZoneInfo

from pandas import isna
import requests

from .reference_normalization import SW_STANDARD
from .reference_sources import (
    Announcement,
    AnnouncementPage,
    IndustryCategory,
    IndustryChange,
    ProviderFailure,
)


CNINFO_ANNOUNCEMENT_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_ROOT = "https://static.cninfo.com.cn/"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _optional_date(value: object) -> date | None:
    if value is None or bool(isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "nat", "none"}:
        return None
    return date.fromisoformat(raw[:10])


def _date_value(value: object) -> date:
    resolved = _optional_date(value)
    if resolved is None:
        raise ValueError("date is required")
    return resolved


def _records(frame: object) -> list[Mapping[str, object]]:
    to_dict = getattr(frame, "to_dict", None)
    if not callable(to_dict):
        raise TypeError("CNInfo industry result must be a DataFrame")
    return [dict(row) for row in to_dict("records")]


def _code6(value: object) -> str:
    raw = str(value or "").strip().split(".")[0]
    if not raw.isdigit():
        raise ValueError("stock code must be numeric")
    return raw.zfill(6)


class CninfoReferenceProvider:
    provider_name = "CNINFO"

    def __init__(
        self,
        *,
        category_fetcher: Callable[[str], object] | None = None,
        change_fetcher: Callable[..., object] | None = None,
        session: Any | None = None,
        page_size: int = 30,
        timeout_seconds: float = 20.0,
    ) -> None:
        if category_fetcher is None or change_fetcher is None:
            import akshare as ak

            category_fetcher = category_fetcher or ak.stock_industry_category_cninfo
            change_fetcher = change_fetcher or ak.stock_industry_change_cninfo
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        self._category_fetcher = category_fetcher
        self._change_fetcher = change_fetcher
        self._session = session or requests.Session()
        self._page_size = page_size
        self._timeout_seconds = timeout_seconds

    def fetch_industry_categories(self) -> tuple[IndustryCategory, ...]:
        try:
            rows = _records(self._category_fetcher(SW_STANDARD))
            values = tuple(
                IndustryCategory(
                    code=str(row.get("类目编码") or "").strip(),
                    parent_code=str(row.get("父类编码") or "").strip(),
                    name=str(row.get("类目名称") or "").strip(),
                    level=int(row.get("分级")),
                    terminated_on=_optional_date(row.get("终止日期")),
                )
                for row in rows
            )
            if not values or any(not row.code or not row.name for row in values):
                raise ValueError("empty or malformed industry categories")
            return tuple(sorted(values, key=lambda row: (row.level, row.code)))
        except ProviderFailure:
            raise
        except Exception as exc:
            raise ProviderFailure(
                self.provider_name, "industry_categories", "PROVIDER_SCHEMA_CHANGED"
            ) from exc

    def fetch_industry_changes(
        self, code: str, start: date, end: date
    ) -> tuple[IndustryChange, ...]:
        try:
            rows = _records(
                self._change_fetcher(
                    symbol=_code6(code),
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                )
            )
            values = []
            for row in rows:
                standard = str(row.get("分类标准") or "").strip()
                if standard != SW_STANDARD:
                    continue
                values.append(
                    IndustryChange(
                        code=_code6(row.get("证券代码") or code),
                        changed_on=_date_value(row.get("变更日期")),
                        standard=standard,
                        industry_code=str(row.get("行业编码") or "").strip(),
                    )
                )
            if any(not row.industry_code for row in values):
                raise ValueError("industry code is required")
            return tuple(
                sorted(values, key=lambda row: (row.changed_on, row.industry_code))
            )
        except ProviderFailure:
            raise
        except KeyError as exc:
            if exc.args == ("变更日期",):
                return ()
            raise ProviderFailure(
                self.provider_name, "industry_changes", "PROVIDER_SCHEMA_CHANGED"
            ) from exc
        except Exception as exc:
            error_code = (
                "PROVIDER_UNAVAILABLE"
                if isinstance(exc, requests.RequestException)
                else "PROVIDER_SCHEMA_CHANGED"
            )
            raise ProviderFailure(
                self.provider_name, "industry_changes", error_code
            ) from exc

    def fetch_announcement_page(self, day: date, page_no: int) -> AnnouncementPage:
        if page_no <= 0:
            raise ValueError("page_no must be positive")
        payload = {
            "pageNum": str(page_no),
            "pageSize": str(self._page_size),
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": "",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{day.isoformat()}~{day.isoformat()}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch",
            "User-Agent": "stock-ai-reference-sync/1.0",
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            response = self._session.post(
                CNINFO_ANNOUNCEMENT_URL,
                data=payload,
                headers=headers,
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            raise ProviderFailure(
                self.provider_name, "announcements", "PROVIDER_UNAVAILABLE"
            ) from exc
        if response.status_code == 429:
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
            data = response.json()
            total_count = int(data["totalAnnouncement"])
            raw_announcements = data["announcements"] or []
            if total_count < 0 or not isinstance(raw_announcements, list):
                raise ValueError("invalid announcement counts")
            records = tuple(self._announcement(row) for row in raw_announcements)
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
        announcement_id = str(row.get("announcementId") or "").strip()
        code = _code6(row.get("secCode"))
        title = (
            str(row.get("announcementTitle") or "")
            .replace("<em>", "")
            .replace("</em>", "")
            .strip()
        )
        adjunct_url = str(row.get("adjunctUrl") or "").strip().lstrip("/")
        if not announcement_id or not title or not adjunct_url:
            raise ValueError("announcement identity, title and URL are required")
        raw_time = row.get("announcementTime")
        published_at = None
        if raw_time not in (None, ""):
            published_at = datetime.fromtimestamp(
                int(raw_time) / 1000,
                tz=timezone.utc,
            ).astimezone(SHANGHAI)
        return Announcement(
            code=code,
            announcement_id=announcement_id,
            title=title,
            published_at=published_at,
            official_url=f"{CNINFO_STATIC_ROOT}{adjunct_url}",
        )
