from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import json

import pytest

from stock_ai.buy_point_selection import validation as validation_module
from stock_ai.buy_point_selection.execution import SimulatedTrade
from stock_ai.buy_point_selection.models import OutcomeLabel, SelectionPolicy, SetupType
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


def _observation(
    exit_date: date,
    *,
    setup_type: SetupType = SetupType.PRE_BREAKOUT,
    sector_code: str = "S1",
    net_return: str = "0.01",
    net_pnl: str = "100",
    outcome: OutcomeLabel = OutcomeLabel.TARGET_2R_FIRST,
    market_status: str = "ALLOW",
    sector_resonating: bool = True,
    mfe: str | None = "0.05",
    mae: str | None = "0.01",
) -> TradeObservation:
    return TradeObservation(
        exit_date=exit_date,
        setup_type=setup_type,
        sector_code=sector_code,
        net_return=Decimal(net_return),
        net_pnl=Decimal(net_pnl),
        outcome=outcome,
        market_status=market_status,
        sector_resonating=sector_resonating,
        mfe=Decimal(mfe) if mfe is not None else None,
        mae=Decimal(mae) if mae is not None else None,
    )


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
        _observation(date(2026, 1, 2)),
        _observation(
            date(2026, 1, 3),
            net_return="-0.005",
            net_pnl="-50",
            outcome=OutcomeLabel.STOP_FIRST,
        ),
        _observation(
            date(2026, 1, 4),
            setup_type=SetupType.TREND_PULLBACK,
            sector_code="S2",
            net_return="0.005",
            net_pnl="50",
            outcome=OutcomeLabel.EXPIRY_GAIN,
        ),
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
        _observation(sessions[0]),
        _observation(
            sessions[-1],
            sector_code="S2",
            net_return="-0.01",
            net_pnl="-100",
            outcome=OutcomeLabel.STOP_FIRST,
        ),
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


def test_calibration_excludes_untriggered_plans_from_triggered_rates() -> None:
    """Catches unfilled plans diluting 2R and stop probabilities or net expectancy."""
    sessions = _trading_dates(63)
    observations = (
        _observation(sessions[0]),
        _observation(sessions[1]),
        _observation(
            sessions[2],
            net_return="-0.01",
            net_pnl="-100",
            outcome=OutcomeLabel.STOP_FIRST,
            mfe="0.01",
            mae="0.04",
        ),
        _observation(
            sessions[3],
            net_return="0",
            net_pnl="0",
            outcome=OutcomeLabel.NOT_TRIGGERED,
            mfe=None,
            mae=None,
        ),
    )
    calibrations = validation_module.build_outcome_calibrations(
        observations,
        test_dates=(),
        trading_dates=sessions,
    )
    calibration = calibrations[
        validation_module.calibration_key(SetupType.PRE_BREAKOUT, None, None)
    ]
    assert calibration.total_plans == 4
    assert calibration.triggered_trades == 3
    assert calibration.untriggered_plans == 1
    assert calibration.target_2r_rate == Decimal("2") / Decimal("3")
    assert calibration.stop_first_rate == Decimal("1") / Decimal("3")
    assert calibration.target_2r_interval[0] < calibration.target_2r_rate
    assert calibration.target_2r_interval[1] > calibration.target_2r_rate


def test_calibration_uses_fixed_hierarchy_and_minimum_thirty_samples() -> None:
    """Catches a sparse fine-grained cohort being presented as a stable probability."""
    sessions = _trading_dates(63)
    observations = tuple(
        _observation(
            sessions[index],
            sector_resonating=index < 20,
            outcome=(
                OutcomeLabel.TARGET_2R_FIRST
                if index % 2 == 0
                else OutcomeLabel.STOP_FIRST
            ),
            net_return="0.02" if index % 2 == 0 else "-0.01",
            net_pnl="200" if index % 2 == 0 else "-100",
        )
        for index in range(35)
    )
    calibrations = validation_module.build_outcome_calibrations(
        observations,
        test_dates=(),
        trading_dates=sessions,
    )
    resolved = validation_module.resolve_outcome_calibration(
        calibrations,
        SetupType.PRE_BREAKOUT,
        "ALLOW",
        True,
    )
    assert resolved is not None
    assert resolved.key == validation_module.calibration_key(
        SetupType.PRE_BREAKOUT, "ALLOW", None
    )
    assert resolved.triggered_trades == 35


def test_simulated_trade_converts_to_complete_observation() -> None:
    """Catches excursion and path labels being dropped before chronological validation."""
    trade = SimulatedTrade(
        structure_id="structure-1",
        code="600001",
        sector_code="S1",
        status="CLOSED",
        entry_date=date(2026, 1, 2),
        entry_price=Decimal("10.10"),
        entry_fees=Decimal("5"),
        quantity=100,
        exit_legs=(),
        net_pnl=Decimal("50"),
        net_return=Decimal("0.05"),
        outcome=OutcomeLabel.TARGET_2R_FIRST,
        mfe=Decimal("0.08"),
        mae=Decimal("0.02"),
        intraday_order_ambiguous=False,
    )
    observation = validation_module.trade_observation_from_simulation(
        trade,
        setup_type=SetupType.PRE_BREAKOUT,
        market_status="ALLOW",
        sector_resonating=True,
        resolution_date=date(2026, 1, 6),
    )
    assert observation.outcome is OutcomeLabel.TARGET_2R_FIRST
    assert observation.mfe == Decimal("0.08")
    assert observation.mae == Decimal("0.02")


def test_v1_validation_artifact_fails_closed(tmp_path) -> None:
    """Catches pre-calibration artifacts retaining live eligibility after the rule upgrade."""
    artifact = tmp_path / "validation.json"
    artifact.write_text(
        '{"schema":"buy-point-selection-validation-v1","promoted":true}',
        encoding="utf-8",
    )
    release = load_historical_release(
        artifact,
        expected_rule_version=SelectionPolicy().rule_version,
        expected_policy_hash=policy_hash(SelectionPolicy()),
    )
    assert not release.live_eligible
    assert "VALIDATION_SCHEMA_MISMATCH" in release.reasons


def test_promoted_v2_artifact_without_calibrations_fails_closed(tmp_path) -> None:
    """Catches a nominally promoted artifact enabling LIVE without ranking evidence."""
    policy = SelectionPolicy()
    artifact = tmp_path / "validation.json"
    artifact.write_text(
        json.dumps(
            {
                "schema": "buy-point-selection-validation-v2",
                "rule_version": policy.rule_version,
                "policy_hash": policy_hash(policy),
                "promoted": True,
                "reasons": [],
                "calibrations": {},
            }
        ),
        encoding="utf-8",
    )
    release = load_historical_release(
        artifact,
        expected_rule_version=policy.rule_version,
        expected_policy_hash=policy_hash(policy),
    )
    assert not release.live_eligible
    assert "VALIDATION_CALIBRATIONS_MISSING" in release.reasons
