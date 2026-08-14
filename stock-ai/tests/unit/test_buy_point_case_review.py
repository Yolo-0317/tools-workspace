from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from stock_ai.buy_point_selection.case_review import (
    GateTrace,
    classify_near_miss,
    replay_case_signals,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    MarketSnapshot,
    SelectionPolicy,
)
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    SectorMembership,
)


SIGNAL = date(2026, 8, 3)


def test_exactly_one_allowed_soft_gate_enters_near_miss() -> None:
    """Catches an explainable sector near miss being discarded with hard failures."""
    trace = GateTrace(
        code="600001",
        signal_date=SIGNAL,
        failed_reasons=("SECTOR_BREADTH_WEAK",),
        passed_stages=("BASE", "SETUP", "ANTI_CHASE"),
        metrics={"boundary_deviation": Decimal("0.10")},
    )

    decision = classify_near_miss(
        trace,
        setup_quality=Decimal("0.8"),
        average_amount5_qian=Decimal("200000"),
    )

    assert decision.admitted
    assert decision.soft_reason == "SECTOR_BREADTH_WEAK"
    assert decision.ranking_key == (
        Decimal("0.10"),
        Decimal("-0.8"),
        Decimal("-200000"),
        "600001",
    )


def test_hard_or_two_soft_failures_never_enter_near_miss() -> None:
    """Catches the diagnostic lane accidentally weakening hard or multiple gates."""
    hard = GateTrace(
        code="600001",
        signal_date=SIGNAL,
        failed_reasons=("LIQUIDITY_TOO_LOW",),
        passed_stages=(),
        metrics={},
    )
    two_soft = GateTrace(
        code="600002",
        signal_date=SIGNAL,
        failed_reasons=(
            "SECTOR_BREADTH_WEAK",
            "INSUFFICIENT_TWO_R_SPACE",
        ),
        passed_stages=("BASE", "SETUP", "ANTI_CHASE"),
        metrics={},
    )

    assert not classify_near_miss(
        hard,
        setup_quality=Decimal("1"),
        average_amount5_qian=Decimal("200000"),
    ).admitted
    assert not classify_near_miss(
        two_soft,
        setup_quality=Decimal("1"),
        average_amount5_qian=Decimal("200000"),
    ).admitted


def _flat_bar(day: date, *, close: str = "10.00") -> BuyPointBar:
    return BuyPointBar(
        trade_date=day,
        open=Decimal(close),
        high=Decimal(close) + Decimal("0.10"),
        low=Decimal(close) - Decimal("0.10"),
        close=Decimal(close),
        pct_chg=Decimal("0"),
        amount_qian=Decimal("200000"),
    )


def _first_launch_bars(signal_date: date) -> tuple[BuyPointBar, ...]:
    closes = [Decimal("10.00")] * 57 + [
        Decimal("10.40"),
        Decimal("10.35"),
        Decimal("10.30"),
    ]
    amounts = [Decimal("100000")] * 57 + [
        Decimal("150000"),
        Decimal("100000"),
        Decimal("100000"),
    ]
    start = signal_date - timedelta(days=len(closes) - 1)
    bars = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        bars.append(
            BuyPointBar(
                trade_date=start + timedelta(days=index),
                open=close,
                high=(Decimal("10.42") if index == 57 else close + Decimal("0.10")),
                low=(Decimal("10.35") if index == 57 else close - Decimal("0.10")),
                close=close,
                pct_chg=(close / previous - Decimal("1")) * Decimal("100"),
                amount_qian=amounts[index],
            )
        )
    return tuple(bars)


def test_signal_replay_never_reads_future_bars_and_records_first_rejection() -> None:
    """Catches outcome-week prices leaking into setup detection or gate attribution."""
    history = tuple(
        _flat_bar(SIGNAL - timedelta(days=59 - index))
        for index in range(60)
    )
    future_spike = _flat_bar(SIGNAL + timedelta(days=1), close="12.00")

    replay = replay_case_signals(
        signal_dates=(SIGNAL,),
        trading_dates=(
            SIGNAL,
            SIGNAL + timedelta(days=1),
            SIGNAL + timedelta(days=2),
        ),
        bars_by_code={"600001": history + (future_spike,)},
        memberships=(),
        risk_flags=(),
        coverage_by_date={
            SIGNAL: ReferenceCoverage(SIGNAL, True, True, True),
        },
        market_snapshots={
            SIGNAL: MarketSnapshot(3, 60.0, 1.1, True),
        },
    )

    trace = replay.traces[(SIGNAL, "600001")]
    assert trace.analysis_bar_date == SIGNAL
    assert future_spike.trade_date not in trace.consumed_bar_dates
    assert trace.first_rejection == "NO_BUY_POINT_SETUP"


def test_signal_replay_attributes_missing_sector_after_a_real_setup() -> None:
    """Catches setup survivors disappearing without their next failing gate."""
    replay = replay_case_signals(
        signal_dates=(SIGNAL,),
        trading_dates=(
            SIGNAL,
            SIGNAL + timedelta(days=1),
            SIGNAL + timedelta(days=2),
        ),
        bars_by_code={"600001": _first_launch_bars(SIGNAL)},
        memberships=(),
        risk_flags=(),
        coverage_by_date={
            SIGNAL: ReferenceCoverage(SIGNAL, True, True, True),
        },
        market_snapshots={
            SIGNAL: MarketSnapshot(3, 60.0, 1.1, True),
        },
    )

    trace = replay.traces[(SIGNAL, "600001")]
    assert trace.first_rejection == "SECTOR_MISSING"
    assert trace.passed_stages[-1] == "ANTI_CHASE"


def test_one_sector_soft_failure_creates_zero_share_near_misses() -> None:
    """Catches the case lane either losing near misses or making them executable."""
    codes = tuple(f"60000{index}" for index in range(1, 6))
    memberships = tuple(
        SectorMembership(code, "S1", "测试行业", SIGNAL, None, "fixture")
        for code in codes
    )
    replay = replay_case_signals(
        signal_dates=(SIGNAL,),
        trading_dates=(
            SIGNAL,
            SIGNAL + timedelta(days=1),
            SIGNAL + timedelta(days=2),
        ),
        bars_by_code={code: _first_launch_bars(SIGNAL) for code in codes},
        memberships=memberships,
        risk_flags=(),
        coverage_by_date={SIGNAL: ReferenceCoverage(SIGNAL, True, True, True)},
        market_snapshots={SIGNAL: MarketSnapshot(3, 60.0, 1.1, True)},
        policy=SelectionPolicy(
            sector_return_percentile_min=0,
            sector_strengthening_members_min=0,
            sector_breadth_min=0.50,
            sector_amount_ratio_min=0,
        ),
    )

    assert replay.strict_shadow == ()
    assert len(replay.near_misses) == 5
    assert {item.soft_reason for item in replay.near_misses} == {
        "SECTOR_BREADTH_WEAK"
    }
    assert all(item.executable_shares == 0 for item in replay.near_misses)


def test_two_r_space_is_a_single_near_miss_with_a_frozen_diagnostic_plan() -> None:
    """Catches the final 2R hard gate becoming invisible to outcome review."""
    codes = tuple(f"60000{index}" for index in range(1, 6))
    bars = {}
    for code in codes:
        values = list(_first_launch_bars(SIGNAL))
        values[0] = replace(values[0], high=Decimal("10.70"))
        bars[code] = tuple(values)
    memberships = tuple(
        SectorMembership(code, "S1", "测试行业", SIGNAL, None, "fixture")
        for code in codes
    )

    replay = replay_case_signals(
        signal_dates=(SIGNAL,),
        trading_dates=(
            SIGNAL,
            SIGNAL + timedelta(days=1),
            SIGNAL + timedelta(days=2),
        ),
        bars_by_code=bars,
        memberships=memberships,
        risk_flags=(),
        coverage_by_date={SIGNAL: ReferenceCoverage(SIGNAL, True, True, True)},
        market_snapshots={SIGNAL: MarketSnapshot(3, 60.0, 1.1, True)},
        policy=SelectionPolicy(
            sector_return_percentile_min=0,
            sector_strengthening_members_min=0,
            sector_breadth_min=0,
            sector_amount_ratio_min=0,
        ),
    )

    assert replay.strict_shadow == ()
    assert len(replay.near_misses) == 5
    assert {item.soft_reason for item in replay.near_misses} == {
        "INSUFFICIENT_TWO_R_SPACE"
    }
    assert all(item.plan.target_2r > item.plan.trigger_price for item in replay.near_misses)


def test_risk_distance_is_a_single_near_miss_with_a_frozen_diagnostic_plan() -> None:
    """Catches wide but measurable structures being absent from case attribution."""
    codes = tuple(f"60000{index}" for index in range(1, 6))
    bars = {}
    for code in codes:
        values = list(_first_launch_bars(SIGNAL))
        values[-1] = replace(values[-1], low=Decimal("9.50"))
        bars[code] = tuple(values)
    memberships = tuple(
        SectorMembership(code, "S1", "测试行业", SIGNAL, None, "fixture")
        for code in codes
    )

    replay = replay_case_signals(
        signal_dates=(SIGNAL,),
        trading_dates=(
            SIGNAL,
            SIGNAL + timedelta(days=1),
            SIGNAL + timedelta(days=2),
        ),
        bars_by_code=bars,
        memberships=memberships,
        risk_flags=(),
        coverage_by_date={SIGNAL: ReferenceCoverage(SIGNAL, True, True, True)},
        market_snapshots={SIGNAL: MarketSnapshot(3, 60.0, 1.1, True)},
        policy=SelectionPolicy(
            sector_return_percentile_min=0,
            sector_strengthening_members_min=0,
            sector_breadth_min=0,
            sector_amount_ratio_min=0,
        ),
    )

    assert len(replay.near_misses) == 5
    assert {item.soft_reason for item in replay.near_misses} == {
        "RISK_DISTANCE_OUT_OF_RANGE"
    }


def test_near_misses_are_deterministically_capped_at_ten_per_signal_date() -> None:
    """Catches an unbounded diagnostic list overwhelming the daily review."""
    codes = tuple(f"600{index:03d}" for index in range(1, 12))
    memberships = tuple(
        SectorMembership(code, "S1", "测试行业", SIGNAL, None, "fixture")
        for code in codes
    )
    replay = replay_case_signals(
        signal_dates=(SIGNAL,),
        trading_dates=(
            SIGNAL,
            SIGNAL + timedelta(days=1),
            SIGNAL + timedelta(days=2),
        ),
        bars_by_code={code: _first_launch_bars(SIGNAL) for code in reversed(codes)},
        memberships=memberships,
        risk_flags=(),
        coverage_by_date={SIGNAL: ReferenceCoverage(SIGNAL, True, True, True)},
        market_snapshots={SIGNAL: MarketSnapshot(3, 60.0, 1.1, True)},
        policy=SelectionPolicy(
            sector_return_percentile_min=0,
            sector_strengthening_members_min=0,
            sector_breadth_min=0.50,
            sector_amount_ratio_min=0,
        ),
    )

    assert tuple(item.code for item in replay.near_misses) == codes[:10]
