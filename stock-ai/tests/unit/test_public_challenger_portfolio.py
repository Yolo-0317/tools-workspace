from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.models import BuyPointBar
from stock_ai.buy_point_selection.public_challenger_portfolio import (
    ChallengerCandidateDecision,
    eligible_universe_on,
    qualify_track_signals,
    select_capacity_matched,
)
from stock_ai.buy_point_selection.public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    RESIDUAL_TRACK,
    ChallengerSignal,
)
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
)


DAY = date(2026, 1, 12)


def _signal(
    code: str,
    track_id: str,
    *,
    sector: str = "S1",
    score: str = "-0.20",
) -> ChallengerSignal:
    residual = None if track_id == CONTRARIAN_TRACK else Decimal(score)
    return ChallengerSignal(
        track_id=track_id,
        signal_date=DAY,
        code=code,
        sector_code=sector,
        matched_index_id="sh.000001",
        signal_close=Decimal("10"),
        formation_return=Decimal(score),
        residual_5d=residual,
        market_percentile=Decimal("0.01"),
        sector_percentile=Decimal("0.01"),
        reference_bucket="LOSER" if track_id == CONTRARIAN_TRACK else None,
        in_candidate_pool=True,
    )


def _three_track_signals(code: str) -> tuple[ChallengerSignal, ...]:
    return (
        _signal(code, CONTRARIAN_TRACK),
        _signal(code, RESIDUAL_TRACK),
        _signal(code, EXECUTION_TRACK),
    )


def _coverage(*, announcement_complete: bool = True) -> ReferenceCoverage:
    return ReferenceCoverage(DAY, True, True, announcement_complete)


def _veto_flag(code: str) -> RiskFlag:
    return RiskFlag(
        code=code,
        flag_type="REGULATORY_INVESTIGATION",
        severity="VETO",
        effective_from=DAY,
        effective_to=None,
        source="TEST",
    )


def _dates(count: int) -> tuple[date, ...]:
    values: list[date] = []
    current = DAY
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current -= timedelta(days=1)
    return tuple(reversed(values))


def _bars(*, amount_qian: str = "100000") -> tuple[BuyPointBar, ...]:
    return tuple(
        BuyPointBar(
            trade_date=trade_date,
            open=Decimal("10"),
            high=Decimal("10.2"),
            low=Decimal("9.8"),
            close=Decimal("10"),
            pct_chg=Decimal("0"),
            amount_qian=Decimal(amount_qian),
        )
        for trade_date in _dates(60)
    )


def _membership(code: str, sector: str = "S1") -> SectorMembership:
    return SectorMembership(
        code=code,
        sector_code=sector,
        sector_name=sector,
        valid_from=date(2020, 1, 1),
        valid_to=None,
        source="TEST",
    )


def test_missing_announcement_keeps_core_but_blocks_execution() -> None:
    decisions = qualify_track_signals(
        signals=_three_track_signals("600001"),
        coverage=_coverage(announcement_complete=False),
        risk_flags=(),
        held_codes=frozenset(),
    )

    assert decisions[CONTRARIAN_TRACK].research_eligible is True
    assert decisions[RESIDUAL_TRACK].research_eligible is True
    assert decisions[EXECUTION_TRACK].research_eligible is True
    assert decisions[EXECUTION_TRACK].execution_eligible is False
    assert decisions[EXECUTION_TRACK].executable_shares == 0
    assert "RISK_DATA_MISSING" in decisions[EXECUTION_TRACK].reasons


def test_veto_flag_blocks_execution_without_deleting_core_observation() -> None:
    decisions = qualify_track_signals(
        signals=_three_track_signals("600001"),
        coverage=_coverage(),
        risk_flags=(_veto_flag("600001"),),
        held_codes=frozenset(),
    )

    assert decisions[RESIDUAL_TRACK].research_eligible is True
    assert decisions[EXECUTION_TRACK].research_eligible is True
    assert decisions[EXECUTION_TRACK].execution_eligible is False
    assert decisions[EXECUTION_TRACK].trade_permission == "NO-TRADE"
    assert decisions[EXECUTION_TRACK].reasons == ("POINT_IN_TIME_RISK_VETO",)


def test_existing_holding_is_excluded_from_all_three_tracks() -> None:
    decisions = qualify_track_signals(
        signals=_three_track_signals("600001"),
        coverage=_coverage(),
        risk_flags=(),
        held_codes=frozenset({"sh.600001"}),
    )

    assert all(not row.research_eligible for row in decisions.values())
    assert all(row.reasons == ("EXISTING_HOLDING",) for row in decisions.values())


def test_eligible_universe_applies_common_point_in_time_filters() -> None:
    bars_by_code = {
        "600001": _bars(),
        "600002": _bars(amount_qian="99999"),
        "300001": _bars(),
        "600003": _bars(),
        "600004": _bars(),
    }
    memberships = tuple(
        _membership(code)
        for code in ("600001", "600002", "300001", "600004")
    )

    result = eligible_universe_on(
        signal_date=DAY,
        bars_by_code=bars_by_code,
        memberships=memberships,
        held_codes=frozenset({"600004"}),
    )

    assert result == ("600001",)


def _decision(
    code: str,
    sector: str,
    score: str,
    *,
    track_id: str = EXECUTION_TRACK,
    execution_eligible: bool = True,
) -> ChallengerCandidateDecision:
    return ChallengerCandidateDecision(
        signal=_signal(code, track_id, sector=sector, score=score),
        research_eligible=True,
        execution_eligible=execution_eligible,
        trade_permission="NO-TRADE",
        executable_shares=0,
        reasons=(),
    )


def _decisions_across_four_sectors() -> tuple[ChallengerCandidateDecision, ...]:
    return (
        _decision("600004", "S4", "-0.10"),
        _decision("600002", "S2", "-0.30"),
        _decision("600001", "S1", "-0.40"),
        _decision("600003", "S3", "-0.20"),
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    (("ALLOW", 3), ("LIMITED", 1), ("FREEZE", 0)),
)
def test_capacity_matches_market_status(status: str, expected: int) -> None:
    result = select_capacity_matched(
        _decisions_across_four_sectors(),
        market_status=status,
    )

    assert len(result.all_eligible) == 4
    assert len(result.selected) == expected
    assert all(row.trade_permission == "NO-TRADE" for row in result.selected)
    assert all(row.executable_shares == 0 for row in result.selected)


def test_capacity_keeps_one_stock_per_sector_and_counts_rejection() -> None:
    result = select_capacity_matched(
        (
            _decision("600002", "S1", "-0.20"),
            _decision("600001", "S1", "-0.30"),
        ),
        market_status="ALLOW",
    )

    assert [row.signal.code for row in result.selected] == ["600001"]
    assert len(result.all_eligible) == 2
    assert result.funnel_counts["SECTOR_CAPACITY"] == 1


def test_core_track_uses_research_eligibility_for_capacity() -> None:
    result = select_capacity_matched(
        (
            _decision(
                "600001",
                "S1",
                "-0.30",
                track_id=RESIDUAL_TRACK,
                execution_eligible=False,
            ),
        ),
        market_status="ALLOW",
    )

    assert [row.signal.code for row in result.selected] == ["600001"]


def test_capacity_ranking_is_stable_on_code_ties() -> None:
    result = select_capacity_matched(
        (
            _decision("600002", "S2", "-0.20"),
            _decision("600001", "S1", "-0.20"),
        ),
        market_status="LIMITED",
    )

    assert [row.signal.code for row in result.selected] == ["600001"]
