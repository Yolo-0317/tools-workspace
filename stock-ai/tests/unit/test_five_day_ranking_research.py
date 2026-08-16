from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_research import (
    build_five_day_ranking_train_review,
)
from stock_ai.buy_point_selection.five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
    FiveDayExit,
    FiveDayTrade,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    SIZING_VERSION,
    build_five_day_return_profiles,
    five_day_profile_hash,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayResearchReview,
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayObservation,
    FiveDayPortfolioMetrics,
)
from stock_ai.buy_point_selection.models import DetectedSetup, SetupType
from stock_ai.buy_point_selection.validation import ChronologicalSplit


START = date(2023, 1, 2)
PARENT_IDENTITY = "a" * 64


def _sessions(count: int) -> tuple[date, ...]:
    return tuple(START + timedelta(days=index) for index in range(count))


def _split() -> ChronologicalSplit:
    sessions = _sessions(630)
    return ChronologicalSplit(
        train=sessions[:378],
        validation=sessions[378:504],
        test=sessions[504:630],
    )


def _empty_portfolio() -> FiveDayPortfolioMetrics:
    return FiveDayPortfolioMetrics(
        accepted_trades=0,
        maximum_drawdown=Decimal("0"),
        maximum_stock_trade_share=Decimal("0"),
        maximum_stock_profit_share=Decimal("0"),
        maximum_sector_trade_share=Decimal("0"),
        maximum_sector_profit_share=Decimal("0"),
        top5_profit_share=Decimal("0"),
        qualifies=False,
        reasons=("NO_ACCEPTED_TRADES",),
    )


def _review(
    observations: tuple[FiveDayObservation, ...] = (),
) -> FiveDayResearchReview:
    return FiveDayResearchReview(
        split=_split(),
        input_fingerprint="f" * 64,
        formal_rule_version="five-day-ranking-fixture-v1",
        formal_policy_hash="b" * 64,
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
        sizing_version=SIZING_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        cost_version=COST_VERSION,
        observations=observations,
        train_calibrations={},
        validation_metrics=(),
        validation_portfolio=_empty_portfolio(),
        point_in_time_complete=True,
        test_outcomes_read=False,
    )


def _resolved_observation(
    signal_date: date,
    *,
    resolution_date: date,
) -> FiveDayObservation:
    profile = build_five_day_return_profiles()[0]
    setup = DetectedSetup(
        code="600001",
        setup_type=SetupType.PRE_BREAKOUT,
        analysis_date=signal_date,
        structure_start=signal_date - timedelta(days=10),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.50"),
        quality=Decimal("0.80"),
        reasons=("FIXTURE",),
        metrics={},
    )
    candidate = FiveDaySignalCandidate(
        code="600001",
        signal_date=signal_date,
        setup=setup,
        market_status="ALLOW",
        sector_code="801010",
        sector_resonating=True,
        anti_chase_passed=True,
        average_amount5_qian=Decimal("200000"),
        valid_through_trade_date=signal_date + timedelta(days=2),
    )
    plan = FiveDaySignalPlan(
        candidate=candidate,
        profile=profile,
        structure_id=f"600001-{signal_date.isoformat()}-{profile.profile_id}",
        signal_close=Decimal("10.00"),
        breakout_trigger=Decimal("10.01"),
        structure_stop=Decimal("9.50"),
        reference_entry=Decimal("10.01"),
        resistance_basis="NO_RELIABLE_LEVEL",
        resistance_effective_r=None,
    )
    exit_value = FiveDayExit(
        planned_exit_date=resolution_date,
        actual_exit_date=resolution_date,
        price=Decimal("10.20"),
        reason="TIME_EXIT_GAIN",
        fees=Decimal("5"),
        delayed=False,
    )
    trade = FiveDayTrade(
        profile_id=profile.profile_id,
        structure_id=plan.structure_id,
        code=candidate.code,
        signal_date=signal_date,
        status="TIME_EXIT_GAIN",
        entry_date=signal_date,
        entry_price=Decimal("10.00"),
        stop_price=Decimal("9.70"),
        evaluation_target_notional=Decimal("10000"),
        evaluation_shares=1000,
        evaluation_notional=Decimal("10000"),
        entry_fees=Decimal("5"),
        exit=exit_value,
        net_pnl=Decimal("190"),
        net_return=Decimal("0.019"),
        mfe=Decimal("0.03"),
        mae=Decimal("0.01"),
        intraday_order_ambiguous=False,
        reasons=(),
    )
    return FiveDayObservation(plan, trade, resolution_date)


def _ranked_observation(
    signal_date: date,
    *,
    code: str,
    net_return: str,
    status: str | None = None,
    resolution_date: date | None = None,
) -> FiveDayObservation:
    value = _resolved_observation(
        signal_date,
        resolution_date=resolution_date or signal_date + timedelta(days=6),
    )
    structure_id = f"{code}-{signal_date.isoformat()}-{value.plan.profile.profile_id}"
    plan = replace(
        value.plan,
        structure_id=structure_id,
        candidate=replace(
            value.plan.candidate,
            code=code,
            setup=replace(value.plan.candidate.setup, code=code),
        ),
    )
    resolved_status = status or (
        "TIME_EXIT_GAIN" if Decimal(net_return) > 0 else "TIME_EXIT_LOSS"
    )
    trade = replace(
        value.trade,
        profile_id=plan.profile.profile_id,
        structure_id=structure_id,
        code=code,
        status=resolved_status,
        net_pnl=Decimal(net_return) * Decimal("10000"),
        net_return=Decimal(net_return),
        exit=replace(
            value.trade.exit,
            reason=resolved_status,
        ),
    )
    return FiveDayObservation(plan, trade, value.resolution_date)


def _diagnostic_review() -> FiveDayResearchReview:
    split = _split()
    calibration = tuple(
        _ranked_observation(
            split.train[index],
            code=f"6100{index:02d}",
            net_return="0.02",
            resolution_date=split.train[index] + timedelta(days=1),
        )
        for index in range(30)
    )
    returns = ("0.03", "-0.01", "0.02", "0.01", "-0.005", "0.015", "0.01")
    fold_one = tuple(
        _ranked_observation(
            split.train[252],
            code=f"6200{index:02d}",
            net_return=net_return,
            status="STOPPED" if index == 2 else None,
        )
        for index, net_return in enumerate(returns, start=1)
    )
    fold_two = tuple(
        _ranked_observation(
            split.train[315],
            code=f"6300{index:02d}",
            net_return=net_return,
        )
        for index, net_return in enumerate(returns, start=1)
    )
    return _review((*calibration, *fold_one, *fold_two))


def test_train_review_uses_exact_expanding_folds_and_no_later_dates() -> None:
    review = _review()

    result = build_five_day_ranking_train_review(
        review,
        parent_research_identity=PARENT_IDENTITY,
    )

    assert tuple(
        (row.calibration_dates, row.evaluation_dates) for row in result.folds
    ) == (
        (review.split.train[:252], review.split.train[252:315]),
        (review.split.train[:315], review.split.train[315:378]),
    )
    assert result.validation_outcomes_read is False
    assert result.test_outcomes_read is False
    assert result.daily_limits == (1, 3, 5)
    assert result.registered_validation_policy.daily_limit == 3
    assert result.registered_validation_policy.capacity == 3


def test_fold_calibration_excludes_outcome_resolved_at_fold_start() -> None:
    split = _split()
    boundary = _resolved_observation(
        split.train[251],
        resolution_date=split.train[252],
    )

    result = build_five_day_ranking_train_review(
        _review((boundary,)),
        parent_research_identity=PARENT_IDENTITY,
    )

    assert result.folds[0].excluded_unresolved_calibration_rows == 1
    assert (
        result.folds[0].calibration_data_end
        < result.folds[0].evaluation_dates[0]
    )


def test_train_review_materializes_every_preregistered_diagnostic_variant() -> None:
    result = build_five_day_ranking_train_review(
        _review(),
        parent_research_identity=PARENT_IDENTITY,
    )
    profile_scopes = {
        f"profile:{profile.profile_id}"
        for profile in build_five_day_return_profiles()
    }
    expected = {
        (fold_id, scope, daily_limit)
        for fold_id in ("train-fold-1", "train-fold-2", "train-combined")
        for scope in (*profile_scopes, "global")
        for daily_limit in (1, 3, 5)
    }

    assert {
        (value.fold_id, value.scope, value.daily_limit)
        for value in result.variants
    } == expected
    assert len(result.variants) == 45
    assert all(
        value.segment.metric_version == "selected-portfolio-v2"
        for value in result.variants
    )


def test_train_review_emits_deterministic_rank_and_loss_attribution() -> None:
    result = build_five_day_ranking_train_review(
        _diagnostic_review(),
        parent_research_identity=PARENT_IDENTITY,
    )
    fold_rows = tuple(
        value
        for value in result.attribution
        if value.fold_id == "train-fold-1" and value.scope == "global"
    )
    rank_rows = {
        value.bucket: value
        for value in fold_rows
        if value.dimension == "rank_band"
    }

    assert tuple(sorted(rank_rows)) == (
        "RANK_1",
        "RANK_2_3",
        "RANK_4_5",
        "RANK_6_PLUS",
    )
    assert rank_rows["RANK_1"].selected_plans == 1
    assert rank_rows["RANK_2_3"].admitted_trades == 2
    assert rank_rows["RANK_4_5"].admitted_trades == 0
    assert rank_rows["RANK_6_PLUS"].resolved_observations == 2
    assert {
        value.dimension for value in fold_rows
    } == {
        "rank_band",
        "setup_type",
        "market_status",
        "sector_resonance",
        "resistance_basis",
        "setup_quality_quintile",
        "calibration_expectancy_quintile",
        "profile",
        "trade_status",
        "gross_to_net_cost_drag",
    }
    assert len(result.quintile_boundaries["train-fold-1"]["setup_quality"]) == 4
    assert len(
        result.quintile_boundaries["train-fold-1"]["calibration_expectancy"]
    ) == 4


def test_train_review_is_deterministic_descriptive_and_train_only() -> None:
    review = _diagnostic_review()

    first = build_five_day_ranking_train_review(
        review,
        parent_research_identity=PARENT_IDENTITY,
    )
    second = build_five_day_ranking_train_review(
        review,
        parent_research_identity=PARENT_IDENTITY,
    )
    payload = asdict(first)
    keys: set[str] = set()
    stack: list[object] = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            keys.update(str(key) for key in value)
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)

    assert first == second
    assert "validation_metrics" not in keys
    assert "promotion_eligible" not in keys
    assert first.validation_outcomes_read is False
    assert first.test_outcomes_read is False
    assert first.fold_stability["global|top:3"] == "STABLE"


def test_train_review_rejects_a_changed_validation_split() -> None:
    review = _review()
    changed = replace(
        review,
        split=replace(
            review.split,
            validation=review.split.validation[:-1],
        ),
    )

    with pytest.raises(ValueError, match="378/126/126"):
        build_five_day_ranking_train_review(
            changed,
            parent_research_identity=PARENT_IDENTITY,
        )


def test_train_diagnostic_variants_never_gain_promotion_authority() -> None:
    result = build_five_day_ranking_train_review(
        _diagnostic_review(),
        parent_research_identity=PARENT_IDENTITY,
    )

    assert all(not value.segment.metrics.qualifies for value in result.variants)
    assert all(
        "TRAIN_DIAGNOSTIC_ONLY" in value.segment.metrics.reasons
        for value in result.variants
    )
    assert all(not value.segment.portfolio.qualifies for value in result.variants)


def test_train_review_preserves_complete_parent_lineage() -> None:
    review = _review()

    result = build_five_day_ranking_train_review(
        review,
        parent_research_identity=PARENT_IDENTITY,
    )

    assert result.split == review.split
    assert result.formal_rule_version == review.formal_rule_version
    assert result.formal_policy_hash == review.formal_policy_hash
    assert result.profile_matrix_hash == review.profile_matrix_hash
    assert result.sizing_version == review.sizing_version
    assert result.evaluator_version == review.evaluator_version
    assert result.cost_version == review.cost_version


def test_train_review_rejects_a_non_hex_parent_identity() -> None:
    with pytest.raises(ValueError, match="sha256"):
        build_five_day_ranking_train_review(
            _review(),
            parent_research_identity="z" * 64,
        )
