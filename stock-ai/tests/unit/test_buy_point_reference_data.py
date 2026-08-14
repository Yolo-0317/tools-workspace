from __future__ import annotations

from datetime import date

from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
    classify_announcement_title,
    membership_on,
    normalize_announcement_flags,
    normalize_sector_memberships,
    normalize_st_flags,
    risk_flags_on,
)


def test_membership_switches_on_normalized_last_active_date() -> None:
    """Catches inclusive/exclusive mistakes that assign one stock to two sectors."""
    rows = (
        SectorMembership(
            code="600001",
            sector_code="801010.SI",
            sector_name="农林牧渔",
            valid_from=date(2024, 1, 2),
            valid_to=date(2025, 6, 30),
            source="tushare-index-member-all",
        ),
        SectorMembership(
            code="600001",
            sector_code="801120.SI",
            sector_name="食品饮料",
            valid_from=date(2025, 7, 1),
            valid_to=None,
            source="tushare-index-member-all",
        ),
    )

    assert membership_on(rows, date(2025, 6, 30))["600001"].sector_name == "农林牧渔"
    assert membership_on(rows, date(2025, 7, 1))["600001"].sector_name == "食品饮料"


def test_sector_normalizer_converts_raw_removal_day_to_previous_trade_day() -> None:
    """Catches treating Tushare's removal day as a second active membership day."""
    rows = [
        {
            "ts_code": "600001.SH",
            "l1_code": "801010.SI",
            "l1_name": "农林牧渔",
            "in_date": "20240102",
            "out_date": "20250701",
        }
    ]

    normalized = normalize_sector_memberships(
        rows,
        previous_trade_date=lambda value: date(2025, 6, 30) if value == date(2025, 7, 1) else None,
    )

    assert normalized == (
        SectorMembership(
            code="600001",
            sector_code="801010.SI",
            sector_name="农林牧渔",
            valid_from=date(2024, 1, 2),
            valid_to=date(2025, 6, 30),
            source="tushare-index-member-all",
        ),
    )


def test_risk_flags_respect_effective_end_date() -> None:
    """Catches permanent vetoes caused by ignoring a historical flag's end date."""
    flags = (
        RiskFlag(
            code="600002",
            flag_type="ST",
            severity="VETO",
            effective_from=date(2025, 8, 1),
            effective_to=date(2025, 8, 20),
            source="tushare-stock-st",
            evidence_ref="stock_st:600002:2025-08-01",
        ),
        RiskFlag(
            code="600003",
            flag_type="REGULATORY_INVESTIGATION",
            severity="VETO",
            effective_from=date(2025, 8, 5),
            effective_to=None,
            source="tushare-anns-d",
            evidence_ref="anns_d:600003:2025-08-05",
        ),
    )

    assert set(risk_flags_on(flags, date(2025, 8, 6))) == {"600002", "600003"}
    assert set(risk_flags_on(flags, date(2025, 8, 21))) == {"600003"}


def test_announcement_classifier_vetoes_only_explicit_material_risk() -> None:
    """Catches ordinary announcements being promoted to deterministic vetoes."""
    assert classify_announcement_title("公司收到中国证监会立案调查告知书") == (
        "REGULATORY_INVESTIGATION",
        "VETO",
    )
    assert classify_announcement_title("关于召开2025年度股东大会的通知") is None


def test_reference_coverage_requires_all_three_point_in_time_datasets() -> None:
    """Catches a partial reference refresh being reported as complete."""
    partial = ReferenceCoverage(date(2025, 8, 6), True, True, False)
    complete = ReferenceCoverage(date(2025, 8, 6), True, True, True)

    assert not partial.complete
    assert complete.complete


def test_st_normalizer_preserves_daily_point_in_time_fact() -> None:
    """Catches collapsing a historical ST row into an unbounded current veto."""
    flags = normalize_st_flags(
        [{"ts_code": "600005.SH", "trade_date": "20250806", "type_name": "风险警示板"}]
    )

    assert flags[0].effective_from == date(2025, 8, 6)
    assert flags[0].effective_to == date(2025, 8, 6)
    assert flags[0].flag_type == "ST"


def test_announcement_normalizer_drops_non_veto_titles() -> None:
    """Catches storing ordinary corporate notices as formal-entry vetoes."""
    flags = normalize_announcement_flags(
        [
            {
                "ts_code": "600006.SH",
                "ann_date": "20250806",
                "title": "公司收到中国证监会立案调查告知书",
                "url": "https://example.test/investigation",
            },
            {
                "ts_code": "600007.SH",
                "ann_date": "20250806",
                "title": "关于召开股东大会的通知",
                "url": "https://example.test/meeting",
            },
        ]
    )

    assert [flag.code for flag in flags] == ["600006"]
    assert flags[0].evidence_ref == "https://example.test/investigation"
