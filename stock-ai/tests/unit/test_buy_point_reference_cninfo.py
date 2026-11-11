from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from stock_ai.buy_point_selection.reference_cninfo import CninfoReferenceProvider
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

    def post(self, url, *, data, headers, timeout):
        self.requests.append((url, dict(data), dict(headers), timeout))
        return self.response


def _category_fetcher(symbol: str):
    assert symbol == "申银万国行业分类标准"
    return pd.DataFrame(
        [
            {
                "类目编码": "801000",
                "父类编码": "",
                "类目名称": "农林牧渔",
                "分级": 1,
                "终止日期": None,
            }
        ]
    )


def _change_fetcher(*, symbol: str, start_date: str, end_date: str):
    assert (symbol, start_date, end_date) == ("600001", "19900101", "20250806")
    return pd.DataFrame(
        [
            {
                "证券代码": "600001",
                "变更日期": date(2024, 1, 2),
                "分类标准": "申银万国行业分类标准",
                "行业编码": "801000",
            },
            {
                "证券代码": "600001",
                "变更日期": date(2024, 2, 1),
                "分类标准": "证监会行业分类标准",
                "行业编码": "A01",
            },
        ]
    )


def _announcement_payload(*, total: int = 31, duplicate: bool = False) -> dict:
    timestamp = int(datetime(2025, 8, 6, 10, tzinfo=timezone.utc).timestamp() * 1000)
    item = {
        "secCode": "600001",
        "announcementId": "ann-1",
        "announcementTitle": "公司收到中国证监会立案调查告知书",
        "announcementTime": timestamp,
        "adjunctUrl": "finalpage/2025-08-06/ann-1.PDF",
    }
    return {
        "totalAnnouncement": total,
        "announcements": [item, dict(item)] if duplicate else [item],
    }


def test_cninfo_adapter_maps_only_sw_industry_rows() -> None:
    """Catches mixed classification standards entering the SW membership ledger."""
    provider = CninfoReferenceProvider(
        category_fetcher=_category_fetcher,
        change_fetcher=_change_fetcher,
        session=FakeSession(FakeResponse(200, _announcement_payload())),
    )

    categories = provider.fetch_industry_categories()
    changes = provider.fetch_industry_changes(
        "600001", date(1990, 1, 1), date(2025, 8, 6)
    )

    assert [(row.code, row.name, row.level) for row in categories] == [
        ("801000", "农林牧渔", 1)
    ]
    assert [(row.code, row.industry_code) for row in changes] == [
        ("600001", "801000")
    ]


def test_cninfo_adapter_treats_pandas_nat_as_missing_termination_date() -> None:
    """Catches an open category interval becoming an uncomparable pandas NaT value."""

    def categories_with_nat(symbol: str):
        assert symbol == "申银万国行业分类标准"
        return pd.DataFrame(
            [
                {
                    "类目编码": "801000",
                    "父类编码": "",
                    "类目名称": "农林牧渔",
                    "分级": 1,
                    "终止日期": pd.NaT,
                }
            ]
        )

    provider = CninfoReferenceProvider(
        category_fetcher=categories_with_nat,
        change_fetcher=_change_fetcher,
        session=FakeSession(FakeResponse(200, _announcement_payload())),
    )

    assert provider.fetch_industry_categories()[0].terminated_on is None


def test_cninfo_empty_industry_history_is_a_valid_uncovered_result() -> None:
    """Catches a stable no-record security being mislabeled as a provider failure."""

    def transient_empty(**kwargs):
        raise KeyError("变更日期")

    provider = CninfoReferenceProvider(
        category_fetcher=_category_fetcher,
        change_fetcher=transient_empty,
        session=FakeSession(FakeResponse(200, _announcement_payload())),
    )

    assert provider.fetch_industry_changes(
        "000017", date(1990, 1, 1), date(2025, 8, 6)
    ) == ()


def test_cninfo_announcement_page_preserves_declared_totals_and_timezone() -> None:
    """Catches a transport that hides missing pages or treats UTC as Shanghai time."""
    session = FakeSession(FakeResponse(200, _announcement_payload(total=31)))
    provider = CninfoReferenceProvider(
        category_fetcher=_category_fetcher,
        change_fetcher=_change_fetcher,
        session=session,
        page_size=30,
    )

    page = provider.fetch_announcement_page(date(2025, 8, 6), 1)

    assert page.total_count == 31
    assert page.page_count == 2
    assert page.page_no == 1 and page.page_size == 30
    assert page.records[0].published_at.hour == 18
    assert str(page.records[0].published_at.tzinfo) == "Asia/Shanghai"
    assert page.records[0].official_url == (
        "https://static.cninfo.com.cn/finalpage/2025-08-06/ann-1.PDF"
    )
    assert session.requests[0][1]["seDate"] == "2025-08-06~2025-08-06"


@pytest.mark.parametrize(
    ("response", "error_code"),
    [
        (FakeResponse(403, {}), "PROVIDER_RATE_LIMITED"),
        (FakeResponse(429, {}), "PROVIDER_RATE_LIMITED"),
        (FakeResponse(503, {}), "PROVIDER_UNAVAILABLE"),
        (FakeResponse(200, {"announcements": []}), "PROVIDER_SCHEMA_CHANGED"),
    ],
)
def test_cninfo_announcement_failures_use_safe_codes(
    response: FakeResponse, error_code: str
) -> None:
    """Catches raw HTTP or provider payloads leaking into CLI/audit errors."""
    provider = CninfoReferenceProvider(
        category_fetcher=_category_fetcher,
        change_fetcher=_change_fetcher,
        session=FakeSession(response),
    )

    with pytest.raises(ProviderFailure) as caught:
        provider.fetch_announcement_page(date(2025, 8, 6), 1)

    assert caught.value.error_code == error_code
    assert str(caught.value) == f"CNINFO:announcements:{error_code}"


def test_cninfo_rejects_duplicate_announcement_ids_within_page() -> None:
    """Catches duplicate page contents falsely satisfying the declared total."""
    provider = CninfoReferenceProvider(
        category_fetcher=_category_fetcher,
        change_fetcher=_change_fetcher,
        session=FakeSession(FakeResponse(200, _announcement_payload(duplicate=True))),
    )

    with pytest.raises(ProviderFailure) as caught:
        provider.fetch_announcement_page(date(2025, 8, 6), 1)

    assert caught.value.error_code == "PROVIDER_SCHEMA_CHANGED"
