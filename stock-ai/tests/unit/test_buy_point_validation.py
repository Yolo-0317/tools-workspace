from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.models import SelectionPolicy, SetupType
from stock_ai.buy_point_selection.validation import (
    SetupMetrics,
    StrategyMetrics,
    TradeObservation,
    ValidationError,
    chronological_split,
    compute_metrics,
    evaluate_promotion,
    load_historical_release,
    policy_hash,
)


def _trading_dates(count: int) -> tuple[date, ...]:
    start = date(2024, 1, 2)
    return tuple(start + timedelta(days=index) for index in range(count))


def _good_setup() -> SetupMetrics:
    return SetupMetrics(
        triggered_trades=40,
        net_expectancy=Decimal("0.01"),
        positive_rolling_window_ratio=Decimal("0.80"),
        frozen_test_expectancy=Decimal("0.005"),
        average_profit_loss_ratio=Decimal("2.0"),
        profit_factor=Decimal("1.6"),
    )


def _good_metrics() -> StrategyMetrics:
    setup = _good_setup()
    return StrategyMetrics(
        aggregate=replace(setup, triggered_trades=120),
        by_setup={value.value: setup for value in SetupType},
        maximum_drawdown=Decimal("0.05"),
        top5_profit_share=Decimal("0.30"),
        maximum_sector_trade_share=Decimal("0.30"),
        maximum_sector_profit_share=Decimal("0.35"),
        point_in_time_complete=True,
    )


def test_split_requires_252_126_126_sessions() -> None:
    """Catches short or randomly sized histories being presented as frozen validation."""
    with pytest.raises(ValidationError, match="630"):
        chronological_split(_trading_dates(629))
    split = chronological_split(_trading_dates(630))
    assert len(split.train) == 378
    assert len(split.validation) == 126
    assert len(split.test) == 126
    assert max(split.train) < min(split.validation) < min(split.test)


def test_duplicate_or_unsorted_dates_are_rejected() -> None:
    """Catches ambiguous chronology before any performance number is computed."""
    dates = list(_trading_dates(630))
    dates[10] = dates[9]
    with pytest.raises(ValidationError, match="strictly increasing"):
        chronological_split(dates)


def test_negative_single_setup_blocks_only_that_setup() -> None:
    """Catches one weak pattern being hidden by stronger patterns or disabling all of them."""
    metrics = _good_metrics()
    by_setup = dict(metrics.by_setup)
    by_setup[SetupType.FIRST_LAUNCH_PULLBACK.value] = replace(
        _good_setup(), net_expectancy=Decimal("-0.002")
    )
    decision = evaluate_promotion(replace(metrics, by_setup=by_setup))
    weak = decision.setup_decisions[SetupType.FIRST_LAUNCH_PULLBACK.value]
    strong = decision.setup_decisions[SetupType.PRE_BREAKOUT.value]
    assert not weak.promoted
    assert "NEGATIVE_EXPECTANCY" in weak.reasons
    assert strong.promoted
    assert decision.promoted


def test_global_risk_concentration_and_coverage_fail_closed() -> None:
    """Catches a fragile or point-in-time-invalid backtest being promoted."""
    concentrated = evaluate_promotion(
        replace(_good_metrics(), top5_profit_share=Decimal("0.36"))
    )
    uncovered = evaluate_promotion(
        replace(_good_metrics(), point_in_time_complete=False)
    )
    assert not concentrated.promoted
    assert "TOP5_PROFIT_CONCENTRATION" in concentrated.reasons
    assert not uncovered.promoted
    assert "POINT_IN_TIME_COVERAGE_INCOMPLETE" in uncovered.reasons


def test_compute_metrics_uses_net_results_and_conservative_drawdown() -> None:
    """Catches gross winners or trade order replacing net chronological outcomes."""
    observations = (
        TradeObservation(date(2026, 1, 2), SetupType.PRE_BREAKOUT, "S1", Decimal("0.01"), Decimal("100")),
        TradeObservation(date(2026, 1, 3), SetupType.PRE_BREAKOUT, "S1", Decimal("-0.005"), Decimal("-50")),
        TradeObservation(date(2026, 1, 4), SetupType.TREND_PULLBACK, "S2", Decimal("0.005"), Decimal("50")),
    )
    metrics = compute_metrics(
        observations,
        test_dates=(date(2026, 1, 4),),
        point_in_time_complete=True,
    )
    assert metrics.aggregate.triggered_trades == 3
    assert metrics.aggregate.net_expectancy == Decimal("0.003333333333333333333333333333")
    assert metrics.aggregate.average_profit_loss_ratio == Decimal("1.5")
    assert metrics.aggregate.profit_factor == Decimal("3")
    assert metrics.maximum_drawdown == Decimal("50") / Decimal("40100")
    assert metrics.maximum_sector_trade_share == Decimal("2") / Decimal("3")


def test_rolling_stability_uses_trading_sessions_not_only_trade_dates() -> None:
    """Catches inactive sessions disappearing and changing 63-session stability."""
    sessions = _trading_dates(64)
    observations = (
        TradeObservation(sessions[0], SetupType.PRE_BREAKOUT, "S1", Decimal("0.01"), Decimal("100")),
        TradeObservation(sessions[-1], SetupType.PRE_BREAKOUT, "S2", Decimal("-0.01"), Decimal("-100")),
    )
    metrics = compute_metrics(
        observations,
        test_dates=(),
        trading_dates=sessions,
        point_in_time_complete=True,
    )
    assert metrics.aggregate.positive_rolling_window_ratio == Decimal("0.5")


def test_policy_hash_is_stable_and_missing_release_fails_closed(tmp_path) -> None:
    """Catches mutable profile identity or a missing artifact defaulting to live."""
    assert policy_hash(SelectionPolicy()) == policy_hash(SelectionPolicy())
    release = load_historical_release(
        tmp_path / "missing.json",
        expected_rule_version=SelectionPolicy().rule_version,
        expected_policy_hash=policy_hash(SelectionPolicy()),
    )
    assert not release.live_eligible
    assert release.reasons == ("VALIDATION_ARTIFACT_MISSING",)
