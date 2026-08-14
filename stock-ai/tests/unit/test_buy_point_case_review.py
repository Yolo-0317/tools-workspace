from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.case_review import (
    BuyableWinner,
    CaseOutcome,
    CaseSignalReplay,
    GateTrace,
    attribute_buyable_winners,
    classify_near_miss,
    classify_case_success,
    evaluate_case_plan,
    find_buyable_winners,
    replay_case_signals,
    summarize_case_outcomes,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    MarketSnapshot,
    SelectionPolicy,
)
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    RiskFlag,
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


@pytest.mark.parametrize(
    ("mfe", "mae", "expected"),
    (
        ("0.0499", "0.01", False),
        ("0.05", "0.03", True),
        ("0.06", "0.0301", False),
    ),
)
def test_case_success_uses_exact_mfe_and_mae_boundaries(
    mfe: str,
    mae: str,
    expected: bool,
) -> None:
    """Catches boundary drift in the agreed five-session success definition."""
    assert classify_case_success(
        triggered=True,
        pending=False,
        mfe=Decimal(mfe),
        mae=Decimal(mae),
    ) is expected


def test_pending_outcome_is_excluded_from_resolved_denominator() -> None:
    """Catches partial current-week data being counted as a strategy failure."""
    outcomes = (
        CaseOutcome("600001", SIGNAL, "STRICT_SHADOW", "PENDING", None, None),
        CaseOutcome(
            "600002",
            SIGNAL,
            "NEAR_MISS",
            "CLOSED",
            Decimal("0.06"),
            Decimal("0.02"),
        ),
    )

    summary = summarize_case_outcomes(outcomes)

    assert summary.total == 2
    assert summary.pending == 1
    assert summary.resolved == 1
    assert summary.successes == 1


def test_case_plan_uses_two_entry_sessions_and_five_post_trigger_sessions() -> None:
    """Catches calendar-day slicing or a partial five-session horizon being resolved."""
    codes = tuple(f"60000{index}" for index in range(1, 6))
    memberships = tuple(
        SectorMembership(code, "S1", "测试行业", SIGNAL, None, "fixture")
        for code in codes
    )
    future_dates = tuple(SIGNAL + timedelta(days=index) for index in range(1, 7))
    replay = replay_case_signals(
        signal_dates=(SIGNAL,),
        trading_dates=(SIGNAL, *future_dates),
        bars_by_code={code: _first_launch_bars(SIGNAL) for code in codes},
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
    candidate = replay.strict_shadow[0]
    future = tuple(
        BuyPointBar(
            trade_date=day,
            open=Decimal("10.40"),
            high=Decimal("11.00"),
            low=Decimal("10.20"),
            close=Decimal("10.80"),
            pct_chg=Decimal("1"),
            amount_qian=Decimal("200000"),
        )
        for day in future_dates
    )

    partial = evaluate_case_plan(
        candidate,
        future,
        outcome_cutoff=future_dates[2],
    )
    complete = evaluate_case_plan(
        candidate,
        future,
        outcome_cutoff=future_dates[4],
    )

    assert partial.status == "PENDING"
    assert partial.success is None
    assert complete.status == "CLOSED"
    assert complete.success is True


def test_buyable_winner_excludes_unbuyable_and_hard_veto_cases() -> None:
    """Catches hindsight winners being counted when no compliant entry existed."""
    codes = {
        "normal": "600001",
        "locked": "600002",
        "gap": "600003",
        "risk": "600004",
        "illiquid": "600005",
        "holding": "600006",
    }
    outcome_date = SIGNAL + timedelta(days=1)
    bars_by_code = {}
    for label, code in codes.items():
        history = tuple(
            _flat_bar(SIGNAL - timedelta(days=4 - index))
            for index in range(5)
        )
        if label == "illiquid":
            history = tuple(
                replace(value, amount_qian=Decimal("50000")) for value in history
            )
        outcome = BuyPointBar(
            trade_date=outcome_date,
            open=Decimal("10.20"),
            high=Decimal("10.60"),
            low=Decimal("10.10"),
            close=Decimal("10.50"),
            pct_chg=Decimal("5"),
            amount_qian=Decimal("200000"),
        )
        if label == "locked":
            outcome = replace(
                outcome,
                open=Decimal("11.00"),
                high=Decimal("11.00"),
                low=Decimal("11.00"),
                close=Decimal("11.00"),
                pct_chg=Decimal("10"),
            )
        elif label == "gap":
            outcome = replace(outcome, open=Decimal("10.31"))
        bars_by_code[code] = history + (outcome,)

    winners = find_buyable_winners(
        signal_date=SIGNAL,
        outcome_dates=(outcome_date,),
        bars_by_code=bars_by_code,
        risk_flags=(
            RiskFlag(
                codes["risk"],
                "ST",
                "VETO",
                SIGNAL,
                None,
                "fixture",
            ),
        ),
        holding_codes=frozenset({codes["holding"]}),
    )

    assert tuple(item.code for item in winners) == (codes["normal"],)
    assert winners[0].maximum_gain == Decimal("0.06")
    assert winners[0].first_buyable_date == outcome_date


def test_missed_winner_uses_signal_date_first_rejection_trace() -> None:
    """Catches hindsight attribution using a later gate result or current state."""
    winner = BuyableWinner(
        "600001",
        SIGNAL,
        Decimal("0.06"),
        SIGNAL + timedelta(days=1),
    )
    replay = CaseSignalReplay(
        traces={
            (SIGNAL, "600001"): GateTrace(
                "600001",
                SIGNAL,
                ("NO_BUY_POINT_SETUP",),
                ("LATEST_BAR", "MARKET", "BASE"),
                {},
            )
        },
        incomplete_dates=(),
    )

    attributed = attribute_buyable_winners((winner,), replay)

    assert attributed[0].captured_tiers == ()
    assert attributed[0].first_rejection == "NO_BUY_POINT_SETUP"
