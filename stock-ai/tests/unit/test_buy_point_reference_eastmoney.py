from __future__ import annotations

from datetime import date

import pytest

from stock_ai.buy_point_selection.reference_eastmoney import (
    EastmoneyAnnouncementProvider,
)
from stock_ai.buy_point_selection.reference_sources import ProviderFailure


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests = []

    def get(self, url, *, params, headers, timeout):
        self.requests.append((url, dict(params), dict(headers), timeout))
        return self.response


def _payload(*, total: int = 101) -> dict:
    return {
        "success": 1,
        "data": {
            "page_index": 1,
            "page_size": 100,
            "total_hits": total,
            "list": [
                {
                    "art_code": "AN202406121636117443",
                    "title": "公司关于新增部分债务逾期的公告",
                    "eiTime": "2024-06-12 20:01:28:000",
                    "codes": [
                        {
                            "ann_type": "A",
                            "stock_code": "603363",
                        }
                    ],
                }
            ],
        },
    }


def test_eastmoney_announcement_page_preserves_pit_time_and_paging() -> None:
    session = FakeSession(FakeResponse(200, _payload()))
    provider = EastmoneyAnnouncementProvider(session=session)

    page = provider.fetch_announcement_page(date(2024, 6, 12), 1)

    assert page.total_count == 101
    assert page.page_count == 2
    assert page.page_no == 1 and page.page_size == 100
    assert page.records[0].code == "603363"
    assert page.records[0].published_at.isoformat() == "2024-06-12T20:01:28+08:00"
    assert page.records[0].official_url == (
        "https://data.eastmoney.com/notices/detail/603363/"
        "AN202406121636117443.html"
    )
    assert session.requests[0][1]["begin_time"] == "2024-06-12"
    assert session.requests[0][1]["f_node"] == "0"
    assert session.requests[0][1]["ann_type"] == "SHA,SZA"


def test_eastmoney_spaces_subsequent_requests_without_delaying_first() -> None:
    sleeps: list[float] = []
    session = FakeSession(FakeResponse(200, _payload(total=1)))
    provider = EastmoneyAnnouncementProvider(
        session=session,
        request_interval_seconds=0.5,
        sleep=sleeps.append,
    )

    provider.fetch_announcement_page(date(2024, 6, 12), 1)
    provider.fetch_announcement_page(date(2024, 6, 13), 1)

    assert sleeps == [0.5]
    assert len(session.requests) == 2


def test_eastmoney_rejects_negative_request_interval() -> None:
    with pytest.raises(ValueError, match="request_interval_seconds"):
        EastmoneyAnnouncementProvider(request_interval_seconds=-0.1)


@pytest.mark.parametrize(
    ("response", "error_code"),
    [
        (FakeResponse(403, {}), "PROVIDER_RATE_LIMITED"),
        (FakeResponse(429, {}), "PROVIDER_RATE_LIMITED"),
        (FakeResponse(567, {}), "PROVIDER_RATE_LIMITED"),
        (FakeResponse(503, {}), "PROVIDER_UNAVAILABLE"),
        (FakeResponse(200, {"success": 1}), "PROVIDER_SCHEMA_CHANGED"),
    ],
)
def test_eastmoney_announcement_failures_use_safe_codes(
    response: FakeResponse, error_code: str
) -> None:
    provider = EastmoneyAnnouncementProvider(session=FakeSession(response))

    with pytest.raises(ProviderFailure) as caught:
        provider.fetch_announcement_page(date(2024, 6, 12), 1)

    assert caught.value.error_code == error_code
    assert str(caught.value) == f"EASTMONEY:announcements:{error_code}"
