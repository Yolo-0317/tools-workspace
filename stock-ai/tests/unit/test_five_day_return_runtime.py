from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

import pytest

from stock_ai.buy_point_selection.five_day_return_runtime import (
    discover_five_day_signal_plans,
    entry_blockers_by_date,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    MarketSnapshot,
    SectorSnapshot,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
)


SIGNAL = date(2026, 7, 30)
CODE = "600001"
SECTOR = "801010"


def _bars(*, amount_qian: str = "200000") -> tuple[BuyPointBar, ...]:
    start = SIGNAL - timedelta(days=59)
    return tuple(
        BuyPointBar(
            trade_date=start + timedelta(days=index),
            open=Decimal("9.80"),
            high=Decimal("9.90"),
            low=Decimal("9.70"),
            close=Decimal("9.80"),
            pct_chg=Decimal("0"),
            amount_qian=Decimal(amount_qian),
        )
        for index in range(60)
    )


def _setup(
    bars: Sequence[BuyPointBar],
    *,
    structure_low: str = "9.60",
    quality: str = "0.80",
    setup_type: SetupType = SetupType.TREND_PULLBACK,
) -> DetectedSetup:
    return DetectedSetup(
        code=CODE,
        setup_type=setup_type,
        analysis_date=bars[-1].trade_date,
        structure_start=bars[-10].trade_date,
        structure_high=Decimal("10.00"),
        structure_low=Decimal(structure_low),
        quality=Decimal(quality),
        reasons=("FIXTURE_SETUP",),
        metrics={},
    )


def _sector_builder(
    *,
    resonating: bool,
):
    def build(
        panel: Mapping[str, Sequence[BuyPointBar]],
        memberships: Mapping[str, SectorMembership],
        policy: SelectionPolicy,
    ) -> Mapping[str, SectorSnapshot]:
        del panel, memberships, policy
        if resonating:
            return {
                SECTOR: SectorSnapshot(
                    SECTOR,
                    "能源",
                    0.90,
                    6,
                    3,
                    0.60,
                    1.00,
                    True,
                )
            }
        return {
            SECTOR: SectorSnapshot(
                SECTOR,
                "能源",
                0.20,
                6,
                0,
                0.10,
                0.50,
                True,
            )
        }

    return build


def _fixture_inputs(
    *,
    market_status: str = "ALLOW",
    sector_resonating: bool = True,
    anti_chase_passed: bool = True,
    hard_failure: str | None = None,
    structure_low: str = "9.60",
    bars: Sequence[BuyPointBar] | None = None,
    setups: Sequence[DetectedSetup] | None = None,
) -> dict[str, object]:
    resolved_bars = tuple(bars or _bars())
    if not anti_chase_passed:
        resolved_bars = (
            *resolved_bars[:-1],
            replace(resolved_bars[-1], pct_chg=Decimal("6")),
        )
    coverage = ReferenceCoverage(SIGNAL, True, True, True)
    risk_flags: tuple[RiskFlag, ...] = ()
    memberships: tuple[SectorMembership, ...] = (
        SectorMembership(CODE, SECTOR, "能源", SIGNAL, None, "fixture"),
    )
    if hard_failure == "POINT_IN_TIME_COVERAGE_INCOMPLETE":
        coverage = replace(coverage, announcement_complete=False)
    elif hard_failure == "POINT_IN_TIME_RISK_VETO":
        risk_flags = (
            RiskFlag(CODE, "ST", "VETO", SIGNAL, None, "fixture"),
        )
    elif hard_failure == "LIQUIDITY_TOO_LOW":
        resolved_bars = tuple(
            replace(value, amount_qian=Decimal("99999"))
            if index >= 55
            else value
            for index, value in enumerate(resolved_bars)
        )
    elif hard_failure == "MARKET_FREEZE":
        market_status = "FREEZE"
    elif hard_failure == "SECTOR_MISSING":
        memberships = ()

    market = {
        "ALLOW": MarketSnapshot(3, 60.0, 1.0, True),
        "LIMITED": MarketSnapshot(2, 48.0, 0.9, True),
        "FREEZE": MarketSnapshot(1, 30.0, 1.0, True),
    }[market_status]

    def detect(
        code: str,
        bounded: Sequence[BuyPointBar],
        policy: SelectionPolicy,
    ) -> Sequence[DetectedSetup]:
        del code, policy
        if setups is not None:
            return setups
        return (_setup(bounded, structure_low=structure_low),)

    return {
        "signal_dates": (SIGNAL,),
        "trading_dates": (
            SIGNAL - timedelta(days=1),
            SIGNAL,
            SIGNAL + timedelta(days=1),
            SIGNAL + timedelta(days=2),
        ),
        "bars_by_code": {CODE: resolved_bars},
        "memberships": memberships,
        "risk_flags": risk_flags,
        "coverage_by_date": {SIGNAL: coverage},
        "market_snapshots": {SIGNAL: market},
        "setup_detector": detect,
        "sector_snapshot_builder": _sector_builder(
            resonating=sector_resonating
        ),
    }


def test_discovery_keeps_limited_and_weak_evidence_as_soft_features() -> None:
    result = discover_five_day_signal_plans(
        **_fixture_inputs(
            market_status="LIMITED",
            sector_resonating=False,
            anti_chase_passed=False,
        )
    )

    assert len(result.plans) == 4
    assert {value.candidate.market_status for value in result.plans} == {
        "LIMITED"
    }
    assert {value.candidate.sector_resonating for value in result.plans} == {
        False
    }
    assert {value.candidate.anti_chase_passed for value in result.plans} == {
        False
    }
    assert all(value.executable_shares == 0 for value in result.plans)


@pytest.mark.parametrize(
    "reason",
    (
        "POINT_IN_TIME_COVERAGE_INCOMPLETE",
        "POINT_IN_TIME_RISK_VETO",
        "LIQUIDITY_TOO_LOW",
        "MARKET_FREEZE",
        "SECTOR_MISSING",
    ),
)
def test_discovery_fails_closed_on_each_hard_gate(reason: str) -> None:
    result = discover_five_day_signal_plans(
        **_fixture_inputs(hard_failure=reason)
    )

    assert result.plans == ()
    assert result.rejection_counts[reason] >= 1


def test_discovery_expands_one_setup_into_the_exact_four_profiles() -> None:
    result = discover_five_day_signal_plans(**_fixture_inputs())

    assert tuple(value.profile.profile_id for value in result.plans) == (
        "BREAKOUT_TRIGGER__FIXED_3_PERCENT",
        "BREAKOUT_TRIGGER__STRUCTURE_ATR",
        "PULLBACK_RECLAIM__FIXED_3_PERCENT",
        "PULLBACK_RECLAIM__STRUCTURE_ATR",
    )
    assert len({value.structure_id for value in result.plans}) == 4
    assert {value.breakout_trigger for value in result.plans} == {
        Decimal("10.01")
    }
    assert {value.signal_close for value in result.plans} == {Decimal("9.80")}
    assert tuple(value.reference_entry for value in result.plans) == (
        Decimal("10.01"),
        Decimal("10.01"),
        Decimal("9.80"),
        Decimal("9.80"),
    )
    assert {value.candidate.valid_through_trade_date for value in result.plans} == {
        SIGNAL + timedelta(days=2)
    }
    assert all(value.status == "CASE_ANALYSIS_ONLY" for value in result.plans)
    assert all(value.trade_permission == "NO-TRADE" for value in result.plans)


def test_discovery_rejects_an_explicit_empty_profile_matrix() -> None:
    with pytest.raises(ValueError, match="profile matrix"):
        discover_five_day_signal_plans(
            **_fixture_inputs(),
            profiles=(),
        )


def test_discovery_chooses_the_highest_quality_setup_deterministically() -> None:
    bars = _bars()
    lower = _setup(
        bars,
        quality="0.40",
        setup_type=SetupType.PRE_BREAKOUT,
    )
    higher = _setup(
        bars,
        quality="0.80",
        setup_type=SetupType.TREND_PULLBACK,
    )

    result = discover_five_day_signal_plans(
        **_fixture_inputs(bars=bars, setups=(lower, higher))
    )

    assert all(value.candidate.setup == higher for value in result.plans)


def test_discovery_ignores_future_bars_in_stop_and_resistance_evidence() -> None:
    bars = _bars()
    future = (
        replace(
            bars[-1],
            trade_date=SIGNAL + timedelta(days=1),
            high=Decimal("12.00"),
            low=Decimal("1.00"),
        ),
        replace(
            bars[-1],
            trade_date=SIGNAL + timedelta(days=2),
            high=Decimal("20.00"),
            low=Decimal("1.00"),
        ),
        replace(
            bars[-1],
            trade_date=SIGNAL + timedelta(days=3),
            high=Decimal("12.00"),
            low=Decimal("1.00"),
        ),
    )

    baseline = discover_five_day_signal_plans(
        **_fixture_inputs(bars=bars)
    )
    with_future = discover_five_day_signal_plans(
        **_fixture_inputs(bars=(*bars, *future))
    )

    assert with_future.plans == baseline.plans


def test_missing_structure_stop_rejects_only_structure_profiles() -> None:
    result = discover_five_day_signal_plans(
        **_fixture_inputs(structure_low="0.01")
    )

    assert tuple(value.profile.stop_kind for value in result.plans) == (
        "FIXED_3_PERCENT",
        "FIXED_3_PERCENT",
    )
    assert result.rejection_counts["STRUCTURE_STOP_UNAVAILABLE"] == 2


def test_entry_blockers_keep_allow_and_limited_dates_open() -> None:
    allow = SIGNAL + timedelta(days=1)
    limited = SIGNAL + timedelta(days=2)
    complete = {
        value: ReferenceCoverage(value, True, True, True)
        for value in (allow, limited)
    }

    result = entry_blockers_by_date(
        CODE,
        (limited, allow, allow),
        coverage_by_date=complete,
        risk_flags=(),
        market_snapshots={
            allow: MarketSnapshot(3, 60.0, 1.0, True),
            limited: MarketSnapshot(2, 48.0, 0.9, True),
        },
    )

    assert tuple(result) == (allow, limited)
    assert result == {allow: (), limited: ()}


def test_entry_blockers_combine_and_sort_all_hard_reasons() -> None:
    entry_date = SIGNAL + timedelta(days=1)

    result = entry_blockers_by_date(
        CODE,
        (entry_date,),
        coverage_by_date={
            entry_date: ReferenceCoverage(entry_date, True, True, False)
        },
        risk_flags=(
            RiskFlag(CODE, "SUSPENSION", "VETO", entry_date, entry_date, "fixture"),
        ),
        market_snapshots={
            entry_date: MarketSnapshot(1, 30.0, 1.0, True)
        },
    )

    assert result[entry_date] == (
        "MARKET_FREEZE",
        "POINT_IN_TIME_COVERAGE_INCOMPLETE",
        "POINT_IN_TIME_RISK_VETO",
    )


def test_entry_blockers_treat_missing_market_snapshot_as_freeze() -> None:
    entry_date = SIGNAL + timedelta(days=1)

    result = entry_blockers_by_date(
        CODE,
        (entry_date,),
        coverage_by_date={
            entry_date: ReferenceCoverage(entry_date, True, True, True)
        },
        risk_flags=(),
        market_snapshots={},
    )

    assert result[entry_date] == ("MARKET_FREEZE",)
