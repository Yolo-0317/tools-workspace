from __future__ import annotations

from datetime import date, timedelta

import pytest

from stock_ai.short_term_selection import CandidateSignal, SelectionBar
from stock_ai.technical_execution import (
    ProxyOpportunity,
    TechnicalProxyPlan,
    build_proxy_plan,
    simulate_proxy_portfolio,
    simulate_proxy_trade,
)


SIGNAL_DATE = date(2026, 8, 10)


def _bar(
    offset: int,
    *,
    open: float,
    high: float,
    low: float,
    close: float,
) -> SelectionBar:
    return SelectionBar(
        trade_date=SIGNAL_DATE + timedelta(days=offset),
        open=open,
        high=high,
        low=low,
        close=close,
        pct_chg=0.0,
        amount_qian=200_000.0,
    )


def _plan(
    *,
    code: str = "600001",
    signal_date: date = SIGNAL_DATE,
    trigger: float = 10.00,
    ceiling: float = 10.15,
    invalidation: float = 9.70,
    target: float = 10.45,
    status: str = "READY",
) -> TechnicalProxyPlan:
    return TechnicalProxyPlan(
        code=code,
        candidate_type="BREAKOUT",
        signal_date=signal_date,
        trigger_price=trigger,
        entry_ceiling=ceiling,
        invalidation_price=invalidation,
        target_price=target,
        risk_distance=trigger - invalidation,
        risk_ratio=(trigger - invalidation) / trigger,
        status=status,
    )


def _signal(candidate_type: str = "BREAKOUT", **metrics: float) -> CandidateSignal:
    defaults = {
        "atr14": 1.0,
        "prior_high20": 10.0,
        "ma10": 9.8,
    }
    defaults.update(metrics)
    return CandidateSignal(
        code="600001",
        name="测试",
        sector="测试",
        candidate_type=candidate_type,
        setup_score=80.0,
        liquidity_score=0.8,
        trend_score=0.8,
        catalyst_score=0.0,
        source_strategies=("fixture",),
        reasons=("fixture",),
        metrics=defaults,
    )


def _history(latest_low: float = 9.6, latest_high: float = 10.0) -> list[SelectionBar]:
    return [
        _bar(
            index - 59,
            open=9.8,
            high=latest_high if index == 59 else 10.0,
            low=latest_low if index == 59 else 9.7,
            close=9.9,
        )
        for index in range(60)
    ]


def test_breakout_proxy_plan_uses_literal_structural_prices() -> None:
    plan = build_proxy_plan(_signal(), _history())

    assert plan.trigger_price == 10.10
    assert plan.entry_ceiling == 10.26
    assert plan.invalidation_price == 9.70
    assert plan.risk_distance == pytest.approx(0.40)
    assert plan.target_price == 10.70
    assert plan.status == "READY"


def test_pullback_proxy_plan_uses_the_stop_day_high() -> None:
    plan = build_proxy_plan(
        _signal("PULLBACK", ma10=9.70),
        _history(latest_low=9.60, latest_high=10.20),
    )

    assert plan.trigger_price == 10.20
    assert plan.invalidation_price == 9.60
    assert plan.target_price == 11.10


@pytest.mark.parametrize(
    ("ma10", "atr14", "expected_ratio"),
    ((10.05, 1.0, 0.0148514851), (9.40, 3.0, 0.0970873786)),
)
def test_risk_distance_outside_one_and_a_half_to_five_percent_is_rejected(
    ma10: float, atr14: float, expected_ratio: float
) -> None:
    plan = build_proxy_plan(_signal(ma10=ma10, atr14=atr14), _history())

    assert plan.risk_ratio == pytest.approx(expected_ratio)
    assert plan.status == "RISK_DISTANCE_OUT_OF_RANGE"


def test_gap_above_entry_ceiling_is_not_filled() -> None:
    result = simulate_proxy_trade(
        _plan(),
        [_bar(1, open=10.16, high=10.50, low=10.10, close=10.30)],
    )

    assert result.status == "GAP_REJECTED"


def test_t_plus_one_high_below_trigger_is_unfilled() -> None:
    result = simulate_proxy_trade(
        _plan(),
        [_bar(1, open=9.90, high=9.99, low=9.80, close=9.95)],
    )

    assert result.status == "UNTRIGGERED"


def test_crossing_the_trigger_fills_at_trigger_plus_slippage() -> None:
    result = simulate_proxy_trade(
        _plan(target=10.80),
        [
            _bar(1, open=9.90, high=10.20, low=9.80, close=10.10),
            _bar(2, open=10.10, high=10.30, low=10.00, close=10.20),
        ],
        commission_rate=0,
        slippage_rate=0.001,
        max_hold_sessions=2,
    )

    assert result.entry_price == pytest.approx(10.01)
    assert result.exit_reason == "TIME"


def test_same_day_stop_and_target_uses_the_stop() -> None:
    result = simulate_proxy_trade(
        _plan(),
        [_bar(1, open=10.00, high=10.50, low=9.60, close=10.20)],
        commission_rate=0,
        slippage_rate=0,
    )

    assert result.exit_reason == "STOP"
    assert result.exit_price == 9.70


def test_target_is_exactly_one_and_a_half_r() -> None:
    plan = _plan(trigger=10.0, invalidation=9.6, target=10.6)
    result = simulate_proxy_trade(
        plan,
        [_bar(1, open=10.0, high=10.6, low=9.8, close=10.5)],
        commission_rate=0,
        slippage_rate=0,
    )

    assert plan.target_price == pytest.approx(
        plan.trigger_price + 1.5 * plan.risk_distance
    )
    assert result.exit_reason == "TARGET"
    assert result.exit_price == 10.6


def test_time_exit_uses_the_fifth_session_close() -> None:
    bars = [
        _bar(index, open=10.0, high=10.2, low=9.8, close=10.0 + index / 100)
        for index in range(1, 7)
    ]

    result = simulate_proxy_trade(
        _plan(invalidation=9.0, target=12.0),
        bars,
        commission_rate=0,
        slippage_rate=0,
    )

    assert result.exit_reason == "TIME"
    assert result.exit_date == bars[4].trade_date
    assert result.exit_price == bars[4].close


def _opportunity(
    code: str,
    signal_offset: int,
    bar_offsets: tuple[int, ...],
) -> ProxyOpportunity:
    plan = _plan(
        code=code,
        signal_date=SIGNAL_DATE + timedelta(days=signal_offset),
        invalidation=9.0,
        target=12.0,
    )
    bars = tuple(
        _bar(offset, open=10.0, high=10.2, low=9.8, close=10.0)
        for offset in bar_offsets
    )
    return ProxyOpportunity(plan=plan, bars=bars)


def test_portfolio_rejects_a_same_code_overlap() -> None:
    result = simulate_proxy_portfolio(
        (
            _opportunity("600001", 0, (1, 2, 3)),
            _opportunity("600001", 1, (2, 3, 4)),
        ),
        commission_rate=0,
        slippage_rate=0,
        max_hold_sessions=3,
    )

    assert [item.status for item in result.rejections] == ["OVERLAP_REJECTED"]


def test_portfolio_enforces_a_five_session_cooldown() -> None:
    result = simulate_proxy_portfolio(
        (
            _opportunity("600001", 0, (1, 2)),
            _opportunity("600001", 2, (3, 4)),
        ),
        market_dates=tuple(SIGNAL_DATE + timedelta(days=index) for index in range(1, 9)),
        commission_rate=0,
        slippage_rate=0,
        max_hold_sessions=2,
        cooldown_sessions=5,
    )

    assert [item.status for item in result.rejections] == ["COOLDOWN_REJECTED"]


def test_portfolio_allows_at_most_two_concurrent_slots() -> None:
    result = simulate_proxy_portfolio(
        tuple(_opportunity(code, 0, (1,)) for code in ("600001", "600002", "600003")),
        commission_rate=0,
        slippage_rate=0,
        max_hold_sessions=1,
        max_positions=2,
    )

    assert len(result.trades) == 2
    assert [item.status for item in result.rejections] == ["CAPACITY_REJECTED"]


def test_one_position_uses_only_half_of_initial_capital() -> None:
    result = simulate_proxy_portfolio(
        (_opportunity("600001", 0, (1,)),),
        initial_capital=100_000,
        commission_rate=0,
        slippage_rate=0,
        max_hold_sessions=1,
    )

    assert result.trades[0].capital_allocated == pytest.approx(50_000)
    assert result.trades[0].quantity == pytest.approx(5_000)


def test_daily_equity_drawdown_is_calculated_from_cash_and_marked_positions() -> None:
    opportunity = ProxyOpportunity(
        plan=_plan(invalidation=5.0, target=20.0),
        bars=(
            _bar(1, open=10.0, high=10.0, low=10.0, close=10.0),
            _bar(2, open=9.0, high=9.0, low=9.0, close=9.0),
        ),
    )

    result = simulate_proxy_portfolio(
        (opportunity,),
        initial_capital=100_000,
        commission_rate=0,
        slippage_rate=0,
        max_hold_sessions=2,
    )

    assert [point.equity for point in result.equity_curve] == pytest.approx(
        [100_000, 95_000]
    )
    assert result.max_drawdown == pytest.approx(0.05)
