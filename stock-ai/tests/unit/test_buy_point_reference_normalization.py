from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from stock_ai.buy_point_selection.reference_normalization import (
    normalize_baostock_risk_flags,
    normalize_cninfo_announcement_flags,
    normalize_cninfo_memberships,
)
from stock_ai.buy_point_selection.reference_sources import (
    Announcement,
    IndustryCategory,
    IndustryChange,
    SecurityStatus,
)


def test_cninfo_changes_become_non_overlapping_l1_intervals() -> None:
    """Catches a child industry or next effective day overlapping the old L1 interval."""
    categories = (
        IndustryCategory("801000", "", "农林牧渔", 1, None),
        IndustryCategory("801010", "801000", "种植业", 2, None),
        IndustryCategory("801120", "", "食品饮料", 1, None),
    )
    changes = {
        "600001": (
            IndustryChange(
                "600001",
                date(2023, 1, 3),
                "申银万国行业分类标准",
                "801010",
            ),
            IndustryChange(
                "600001",
                date(2025, 7, 1),
                "申银万国行业分类标准",
                "801120",
            ),
        )
    }

    rows = normalize_cninfo_memberships(
        categories,
        changes,
        previous_trade_date=lambda value: (
            date(2025, 6, 30) if value == date(2025, 7, 1) else None
        ),
    )

    assert [(row.sector_code, row.sector_name, row.valid_from, row.valid_to) for row in rows] == [
        ("801000", "农林牧渔", date(2023, 1, 3), date(2025, 6, 30)),
        ("801120", "食品饮料", date(2025, 7, 1), None),
    ]
    assert all(row.source == "CNINFO" for row in rows)


def test_baostock_snapshot_emits_daily_st_and_suspension_vetoes() -> None:
    """Catches current-name inference or a suspended ST losing one of its two vetoes."""
    rows = normalize_baostock_risk_flags(
        (
            SecurityStatus("600001", " *ST 示例 ", "0", date(2025, 8, 6)),
            SecurityStatus("600002", "普通股份", "1", date(2025, 8, 6)),
        )
    )

    assert {(row.code, row.flag_type) for row in rows} == {
        ("600001", "ST"),
        ("600001", "SUSPENDED"),
    }
    assert all(row.effective_from == date(2025, 8, 6) for row in rows)
    assert all(row.effective_to == date(2025, 8, 6) for row in rows)
    assert all(row.severity == "VETO" and row.source == "BAOSTOCK" for row in rows)


def test_after_close_cninfo_announcement_starts_next_trade_day() -> None:
    """Catches a post-close announcement leaking into that day's historical selection."""
    flags = normalize_cninfo_announcement_flags(
        (
            Announcement(
                "600003",
                "ann-1",
                "公司收到中国证监会立案调查告知书",
                datetime(
                    2025,
                    8,
                    8,
                    18,
                    tzinfo=ZoneInfo("Asia/Shanghai"),
                ),
                "https://static.cninfo.com.cn/finalpage/ann-1.PDF",
            ),
        ),
        is_trade_date=lambda value: value == date(2025, 8, 8),
        next_trade_date=lambda value: date(2025, 8, 11),
    )

    assert len(flags) == 1
    assert flags[0].effective_from == date(2025, 8, 11)
    assert flags[0].effective_to is None
    assert flags[0].source == "CNINFO"
    assert flags[0].evidence_ref == "https://static.cninfo.com.cn/finalpage/ann-1.PDF"


def test_cninfo_announcement_without_time_uses_next_trade_day() -> None:
    """Catches missing publication time being treated as known before the cutoff."""
    flags = normalize_cninfo_announcement_flags(
        (
            Announcement(
                "600004",
                "ann-2",
                "公司股票可能被终止上市的风险提示公告",
                None,
                "https://static.cninfo.com.cn/finalpage/ann-2.PDF",
            ),
        ),
        is_trade_date=lambda value: False,
        next_trade_date=lambda value: date(2025, 8, 11),
        fallback_date=date(2025, 8, 9),
    )

    assert flags[0].effective_from == date(2025, 8, 11)
