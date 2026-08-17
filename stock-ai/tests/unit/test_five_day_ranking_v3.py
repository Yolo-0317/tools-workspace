from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

import stock_ai.buy_point_selection.five_day_ranking_v3 as v3
from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    FiveDayV3PolicyFingerprint,
    V3MonotonicityAssessment,
    V3RankBandMetrics,
    V3_POLICY_IDS,
    assess_five_day_v3_policy,
    build_five_day_ranking_v3_train_review,
    build_five_day_ranking_v3_validation_review,
    build_five_day_v3_policies,
    finalize_five_day_ranking_v3_train,
    five_day_v3_policy_hash,
    five_day_v3_policy_set_hash,
    five_day_v3_selection_fingerprint,
    rank_five_day_plans_v3,
    score_five_day_plan_v3,
    v3_validation_trial_identity,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_report import (
    FiveDayRankingV3TrainArtifact,
    five_day_ranking_v3_train_payload,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_evidence import (
    V3BucketKey,
    V3BucketStats,
    V3CandidateEvidence,
    V3EvidenceWindows,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_features import (
    V3_FEATURE_NAMES,
    V3FeatureAdjustment,
    V3FeatureModel,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayPortfolioMetrics,
    FiveDayRanking,
    FiveDaySegmentMetrics,
    FiveDaySelection,
    FiveDaySelectedSegment,
    admit_five_day_ranking,
)

from five_day_ranking_v3_fixtures import (
    make_v3_observation,
    make_v3_plan,
    make_v3_research_review,
    weekday_dates,
)


START = date(2023, 1, 2)
PROFILE_IDS = (
    "BREAKOUT_TRIGGER__FIXED_3_PERCENT",
    "BREAKOUT_TRIGGER__STRUCTURE_ATR",
    "PULLBACK_RECLAIM__FIXED_3_PERCENT",
    "PULLBACK_RECLAIM__STRUCTURE_ATR",
)


def _candidate_evidence(
    *,
    edge: str = "0.004",
    full_edge: str = "0.003",
    recent_edge: str = "0.002",
    stop_rate: str = "0.50",
    mae_p75: str = "0.08",
) -> V3CandidateEvidence:
    key = V3BucketKey(
        level="PROFILE",
        profile_id="BREAKOUT_TRIGGER__STRUCTURE_ATR",
    )
    return V3CandidateEvidence(
        full_edge=Decimal(full_edge),
        recent_edge=Decimal(recent_edge),
        edge=Decimal(edge),
        stop_rate=Decimal(stop_rate),
        mae_p75=Decimal(mae_p75),
        deepest_full_key=key,
        deepest_recent_key=key,
        stable_negative=False,
        full_trace=(),
        recent_trace=(),
    )


def _feature_adjustment(*, total: str = "0.001") -> V3FeatureAdjustment:
    return V3FeatureAdjustment(effects={}, total=Decimal(total))


def _raw_edge_for_score(score: Decimal) -> Decimal:
    edge = (
        score - Decimal("0.0005")
        if score >= Decimal("0.0015")
        else score / Decimal("1.5")
    )
    return edge * Decimal("1.5")


def _bucket_stats(
    key: V3BucketKey,
    *,
    raw_edge: Decimal,
    samples: int = 60,
    stable_negative: bool = False,
) -> V3BucketStats:
    return V3BucketStats(
        key=key,
        data_end=START - timedelta(days=1),
        total_plans=samples,
        resolved_samples=samples,
        net_expectancy=raw_edge,
        profit_factor=Decimal("0.80") if stable_negative else Decimal("2"),
        profitable_interval=(
            (Decimal("0.20"), Decimal("0.49"))
            if stable_negative
            else (Decimal("0.50"), Decimal("0.80"))
        ),
        positive_window_ratio=Decimal("0.80"),
        mae_p75=Decimal("0.05"),
        stop_rate=Decimal("0.30"),
    )


def _evidence_windows_for_scores(
    plans: tuple,
    scores: tuple[str, ...],
    *,
    stable_negative: bool = False,
) -> V3EvidenceWindows:
    full: dict[V3BucketKey, V3BucketStats] = {}
    recent: dict[V3BucketKey, V3BucketStats] = {}
    for plan, score_text in zip(plans, scores, strict=True):
        root = V3BucketKey(
            level="PROFILE",
            profile_id=plan.profile.profile_id,
        )
        raw_edge = (
            Decimal("-0.01")
            if stable_negative
            else _raw_edge_for_score(Decimal(score_text))
        )
        full[root] = _bucket_stats(
            root,
            raw_edge=raw_edge,
            stable_negative=stable_negative,
        )
        recent[root] = _bucket_stats(
            root,
            raw_edge=raw_edge,
            samples=30 if stable_negative else 60,
            stable_negative=stable_negative,
        )
        if stable_negative:
            setup = V3BucketKey(
                level="SETUP",
                profile_id=plan.profile.profile_id,
                setup_type=plan.candidate.setup.setup_type,
            )
            full[setup] = _bucket_stats(
                setup,
                raw_edge=raw_edge,
                stable_negative=True,
            )
            recent[setup] = _bucket_stats(
                setup,
                raw_edge=raw_edge,
                samples=30,
                stable_negative=True,
            )
    calibration_date = START - timedelta(days=1)
    return V3EvidenceWindows(
        full_dates=(calibration_date,),
        recent_dates=(calibration_date,),
        full=full,
        recent=recent,
    )


def _empty_feature_model() -> V3FeatureModel:
    return V3FeatureModel(
        data_end=START - timedelta(days=1),
        boundaries={name: () for name in V3_FEATURE_NAMES},
        effects={},
    )


def _plans_for_scores(scores: tuple[str, ...]) -> tuple:
    return tuple(
        make_v3_plan(
            START,
            code=f"60000{index}",
            profile_id=PROFILE_IDS[index - 1],
        )
        for index in range(1, len(scores) + 1)
    )


def _rank_scores(scores: tuple[str, ...]):
    plans = _plans_for_scores(scores)
    return rank_five_day_plans_v3(
        plans,
        _evidence_windows_for_scores(plans, scores),
        _empty_feature_model(),
        policy=build_five_day_v3_policies()[0],
    )


def _selected_count(*, scores: tuple[str, ...]) -> int:
    return len(_rank_scores(scores).ranking.plans)


def _rank_with_duplicate_profiles():
    fixed = make_v3_plan(
        START,
        code="600001",
        profile_id=PROFILE_IDS[0],
    )
    structure = make_v3_plan(
        START,
        code="600001",
        profile_id=PROFILE_IDS[1],
    )
    structure = replace(
        structure,
        candidate=fixed.candidate,
        structure_id="same-structure-different-profile",
    )
    plans = (fixed, structure)
    return rank_five_day_plans_v3(
        plans,
        _evidence_windows_for_scores(plans, ("0.004", "0.006")),
        _empty_feature_model(),
        policy=build_five_day_v3_policies()[0],
    )


def _rank_one(*, stable_negative: bool):
    plans = _plans_for_scores(("0.004",))
    return rank_five_day_plans_v3(
        plans,
        _evidence_windows_for_scores(
            plans,
            ("0.004",),
            stable_negative=stable_negative,
        ),
        _empty_feature_model(),
        policy=build_five_day_v3_policies()[0],
    )


def _not_triggered_observation(plan):
    value = make_v3_observation(plan, net_return=Decimal("0"))
    return replace(
        value,
        trade=replace(
            value.trade,
            status="NOT_TRIGGERED",
            entry_date=None,
            entry_price=None,
            stop_price=None,
            evaluation_shares=0,
            evaluation_notional=Decimal("0"),
            exit=None,
            net_return=None,
            mfe=None,
            mae=None,
        ),
    )


def _selection_with_cancelled_first_and_ranked_fourth() -> tuple[
    FiveDaySelection,
    str,
]:
    result = _rank_scores(("0.006", "0.004", "0.002", "0.001"))
    ranked_plans = tuple(row.plan for row in result.ranking.ranked)
    observations = (
        _not_triggered_observation(ranked_plans[0]),
        *(make_v3_observation(plan) for plan in ranked_plans[1:]),
    )
    return (
        admit_five_day_ranking(result.ranking, observations),
        ranked_plans[3].structure_id,
    )


def _segment(
    *,
    samples: int,
    edge: str,
    profit_factor: str | None = "1.1001",
    incomplete: bool = False,
    maximum_drawdown: str = "0.05",
) -> FiveDaySelectedSegment:
    metrics = FiveDaySegmentMetrics(
        profile_id="V3",
        segment="TRAIN",
        triggered_resolved=samples,
        net_expectancy=Decimal(edge),
        profit_factor=(
            Decimal(profit_factor) if profit_factor is not None else None
        ),
        profitable_wilson_lower=Decimal("0.50"),
        stop_rate=Decimal("0.20"),
        positive_window_ratio=Decimal("0.60"),
        maximum_drawdown=Decimal(maximum_drawdown),
        qualifies=True,
        reasons=(),
    )
    return FiveDaySelectedSegment(
        metric_version="selected-portfolio-v2",
        metrics=metrics,
        portfolio=FiveDayPortfolioMetrics(
            accepted_trades=samples,
            maximum_drawdown=Decimal(maximum_drawdown),
            maximum_stock_trade_share=Decimal("0.10"),
            maximum_stock_profit_share=Decimal("0.10"),
            maximum_sector_trade_share=Decimal("0.20"),
            maximum_sector_profit_share=Decimal("0.20"),
            top5_profit_share=Decimal("0.30"),
            qualifies=True,
            reasons=(),
        ),
        selection=FiveDaySelection(
            ranking=FiveDayRanking(plans=(), rejection_counts={}),
            selected_observations=(),
            admitted=(),
            funnel_counts={},
            incomplete=incomplete,
        ),
    )


def _qualifying_monotonicity() -> V3MonotonicityAssessment:
    return V3MonotonicityAssessment(
        bands=(
            V3RankBandMetrics("RANK_1", 15, Decimal("0.006")),
            V3RankBandMetrics("RANK_2_3", 15, Decimal("0.005")),
            V3RankBandMetrics("RANK_4_5", 15, Decimal("0.004")),
            V3RankBandMetrics("RANK_6_PLUS", 15, Decimal("0.002")),
        ),
        qualifies=True,
        reasons=(),
    )


def _qualifying_assessment(policy):
    return assess_five_day_v3_policy(
        policy=policy,
        fold1=_segment(samples=20, edge="0.002"),
        fold2=_segment(samples=20, edge="0.003"),
        combined=_segment(samples=40, edge="0.003"),
        monotonicity=_qualifying_monotonicity(),
    )


def _complete_research_with_boundary_resolution():
    sessions = weekday_dates(630)
    fold1_boundary = sessions[252]
    fold2_boundary = sessions[315]
    observations = (
        make_v3_observation(
            make_v3_plan(sessions[0], code="600001"),
            resolution_date=fold1_boundary,
        ),
        make_v3_observation(
            make_v3_plan(sessions[253], code="600002"),
            resolution_date=fold2_boundary,
        ),
    )
    return make_v3_research_review(observations)


def _research_with_validation_resolved_train_signal():
    sessions = weekday_dates(630)
    calibration = tuple(
        make_v3_observation(
            make_v3_plan(sessions[index], code=f"{600000 + index:06d}"),
            net_return=Decimal("0.01"),
            resolution_date=sessions[index + 1],
        )
        for index in range(60)
    )
    late = make_v3_observation(
        make_v3_plan(sessions[377], code="699999"),
        net_return=Decimal("0.50"),
        resolution_date=sessions[378],
    )
    return make_v3_research_review((*calibration, late))


def _train_review_with_fingerprints(
    fingerprints: tuple[str, ...],
):
    policies = build_five_day_v3_policies()
    base = build_five_day_ranking_v3_train_review(
        make_v3_research_review(()),
        parent_research_identity="a" * 64,
    )
    values = tuple(
        FiveDayV3PolicyFingerprint(
            policy_id=policy.policy_id,
            selected_structure_keys=(fingerprint,),
            fingerprint=five_day_v3_selection_fingerprint((fingerprint,)),
        )
        for policy, fingerprint in zip(policies, fingerprints, strict=True)
    )
    return replace(
        base,
        assessments=tuple(
            _qualifying_assessment(policy) for policy in policies
        ),
        policy_fingerprints=values,
        fingerprint_groups=(),
        winner_policy_id=None,
        winner_policy_hash=None,
        winner_train_samples=0,
        status="NO_TRAIN_CANDIDATE",
        validation_eligible=False,
    )


def _train_artifact(*, winner: bool) -> FiveDayRankingV3TrainArtifact:
    observations = ()
    if winner:
        sessions = weekday_dates(630)
        observations = tuple(
            make_v3_observation(
                make_v3_plan(
                    sessions[index],
                    code=f"{600000 + index:06d}",
                ),
                resolution_date=sessions[index + 1],
            )
            for index in range(60)
        )
    review = build_five_day_ranking_v3_train_review(
        make_v3_research_review(observations),
        parent_research_identity="a" * 64,
    )
    if winner:
        segments = {
            "train-fold-1": _segment(samples=20, edge="0.002"),
            "train-fold-2": _segment(samples=20, edge="0.003"),
            "train-combined": _segment(samples=40, edge="0.003"),
        }
        fingerprints = ("a", "a", "b", "b", "c", "c", "d", "d")
        review = finalize_five_day_ranking_v3_train(
            replace(
                review,
                variants=tuple(
                    replace(value, segment=segments[value.fold_id])
                    if value.selection_mode == "FORMAL"
                    else value
                    for value in review.variants
                ),
                assessments=tuple(
                    _qualifying_assessment(policy)
                    for policy in review.policies
                ),
                policy_fingerprints=tuple(
                    FiveDayV3PolicyFingerprint(
                        policy_id=policy.policy_id,
                        selected_structure_keys=(fingerprint,),
                        fingerprint=five_day_v3_selection_fingerprint(
                            (fingerprint,)
                        ),
                    )
                    for policy, fingerprint in zip(
                        review.policies,
                        fingerprints,
                        strict=True,
                    )
                ),
            )
        )
    payload = five_day_ranking_v3_train_payload(review)
    return FiveDayRankingV3TrainArtifact(
        artifact_identity=str(payload["artifact_identity"]),
        parent_research_identity=review.parent_research_identity,
        parent_input_fingerprint=review.parent_input_fingerprint,
        split=review.split,
        policy_set_hash=review.policy_set_hash,
        winner_policy_id=review.winner_policy_id,
        winner_policy_hash=review.winner_policy_hash,
        winner_train_samples=review.winner_train_samples,
        validation_eligible=review.validation_eligible,
        validation_evidence_windows=review.validation_evidence_windows,
        validation_feature_model=review.validation_feature_model,
        payload=payload,
    )


def test_v3_policy_registry_is_exact_and_hashed() -> None:
    policies = build_five_day_v3_policies()

    assert tuple(value.policy_id for value in policies) == V3_POLICY_IDS
    assert tuple(
        (
            value.shrinkage_k,
            value.consistency_weight,
            value.structure_weight,
            value.downside_weight,
        )
        for value in policies
    ) == (
        (30, Decimal("0.50"), Decimal("0.50"), Decimal("0.50")),
        (60, Decimal("0.50"), Decimal("0.50"), Decimal("0.50")),
        (30, Decimal("1.00"), Decimal("0.50"), Decimal("0.50")),
        (60, Decimal("1.00"), Decimal("0.50"), Decimal("0.50")),
        (30, Decimal("0.50"), Decimal("1.00"), Decimal("0.50")),
        (60, Decimal("0.50"), Decimal("1.00"), Decimal("0.50")),
        (30, Decimal("0.50"), Decimal("0.50"), Decimal("1.00")),
        (60, Decimal("0.50"), Decimal("0.50"), Decimal("1.00")),
    )
    hashes = {five_day_v3_policy_hash(value) for value in policies}
    assert len(hashes) == 8
    assert all(len(value) == 64 for value in hashes)
    assert five_day_v3_policy_set_hash() == five_day_v3_policy_set_hash()
    assert len(five_day_v3_policy_set_hash()) == 64


def test_v3_score_uses_exact_consistency_and_downside_formula() -> None:
    policy = build_five_day_v3_policies()[0]

    result = score_five_day_plan_v3(
        make_v3_plan(START),
        evidence=_candidate_evidence(),
        features=_feature_adjustment(),
        policy=policy,
    )

    assert result.consistency == Decimal("0.001")
    assert result.downside == Decimal("0.003")
    assert result.score == Decimal("0.0035")
    assert result.rank == 0
    assert result.selected is False


def test_v3_downside_adds_uncapped_stop_and_mae_excess() -> None:
    result = score_five_day_plan_v3(
        make_v3_plan(START),
        evidence=_candidate_evidence(stop_rate="0.40", mae_p75="0.06"),
        features=_feature_adjustment(total="0"),
        policy=build_five_day_v3_policies()[0],
    )

    assert result.downside == Decimal("0.0020")


def test_v3_consistency_clips_the_weaker_negative_window() -> None:
    result = score_five_day_plan_v3(
        make_v3_plan(START),
        evidence=_candidate_evidence(
            full_edge="0.010",
            recent_edge="-0.002",
            stop_rate="0.30",
            mae_p75="0.05",
        ),
        features=_feature_adjustment(total="0"),
        policy=build_five_day_v3_policies()[0],
    )

    assert result.consistency == Decimal("-0.001")


def test_v3_score_rejects_an_unresolved_profile_stop() -> None:
    with pytest.raises(ValueError, match="profile stop"):
        score_five_day_plan_v3(
            make_v3_plan(START, structure_stop=Decimal("1")),
            evidence=_candidate_evidence(),
            features=_feature_adjustment(),
            policy=build_five_day_v3_policies()[0],
        )


def test_v3_score_rejects_a_policy_outside_the_registry() -> None:
    policy = replace(
        build_five_day_v3_policies()[0],
        policy_id="UNREGISTERED-K30",
    )

    with pytest.raises(ValueError, match="registered"):
        score_five_day_plan_v3(
            make_v3_plan(START),
            evidence=_candidate_evidence(),
            features=_feature_adjustment(),
            policy=policy,
        )


def test_v3_daily_selection_can_return_zero_one_two_or_three() -> None:
    assert _selected_count(scores=("0.0009",)) == 0
    assert _selected_count(
        scores=("0.006", "0.004", "0.0035", "0.003")
    ) == 1
    assert _selected_count(
        scores=("0.006", "0.004", "0.0029", "0.0025")
    ) == 2
    assert _selected_count(
        scores=("0.006", "0.004", "0.002", "0")
    ) == 3


def test_v3_floor_and_boundary_rejections_are_recorded() -> None:
    below_floor = _rank_scores(("0.0009",))
    reduced = _rank_scores(("0.006", "0.004", "0.0035", "0.003"))

    assert below_floor.ranking.rejection_counts == {
        "ABSOLUTE_EDGE_TOO_LOW": 1,
    }
    assert reduced.ranking.rejection_counts == {
        "BOUNDARY_MARGIN_TOO_LOW": 2,
    }
    assert tuple(
        (row.rank, row.selected) for row in reduced.ranking.ranked
    ) == ((1, True), (2, False), (3, False), (4, False))


def test_v3_duplicate_structure_collapses_before_boundary_check() -> None:
    result = _rank_with_duplicate_profiles()

    assert len(result.ranking.plans) == 1
    assert result.ranking.plans[0].profile.profile_id == PROFILE_IDS[1]
    assert result.ranking.rejection_counts == {
        "DUPLICATE_ACTIVE_STRUCTURE": 1,
    }


def test_v3_stable_negative_is_recorded_before_scoring() -> None:
    result = _rank_one(stable_negative=True)

    assert result.ranking.plans == ()
    assert result.scored == ()
    assert result.ranking.rejection_counts == {"STABLE_NEGATIVE": 1}


def test_v3_existing_active_structure_is_rejected_before_scoring() -> None:
    plan = _plans_for_scores(("0.004",))[0]

    result = rank_five_day_plans_v3(
        (plan,),
        _evidence_windows_for_scores((plan,), ("0.004",)),
        _empty_feature_model(),
        policy=build_five_day_v3_policies()[0],
        active_structure_ids=frozenset((plan.structure_id,)),
    )

    assert result.scored == ()
    assert result.ranking.rejection_counts == {
        "EXISTING_ACTIVE_STRUCTURE": 1,
    }


def test_v3_later_admission_rejection_never_backfills() -> None:
    selection, fourth_structure_id = (
        _selection_with_cancelled_first_and_ranked_fourth()
    )

    assert selection.funnel_counts["NOT_TRIGGERED"] == 1
    assert fourth_structure_id not in {
        value.plan.structure_id for value in selection.selected_observations
    }


def test_v3_train_excludes_resolution_on_evaluation_boundary() -> None:
    review = build_five_day_ranking_v3_train_review(
        _complete_research_with_boundary_resolution(),
        parent_research_identity="a" * 64,
    )

    assert [
        fold.excluded_unresolved_calibration_rows for fold in review.folds
    ] == [1, 1]
    assert [len(fold.calibration_dates) for fold in review.folds] == [252, 315]
    assert [len(fold.evaluation_dates) for fold in review.folds] == [63, 63]


def test_v3_degenerate_policy_fingerprints_block_every_winner() -> None:
    review = _train_review_with_fingerprints(("same",) * 8)

    finalized = finalize_five_day_ranking_v3_train(review)

    assert finalized.status == "POLICY_SET_DEGENERATE"
    assert finalized.winner_policy_id is None
    assert finalized.validation_eligible is False
    assert all(not value.qualifies for value in finalized.assessments)


def test_v3_policy_qualification_uses_unchanged_hard_thresholds() -> None:
    assessment = assess_five_day_v3_policy(
        policy=build_five_day_v3_policies()[0],
        fold1=_segment(samples=15, edge="0.0001"),
        fold2=_segment(samples=15, edge="0.0001"),
        combined=_segment(
            samples=40,
            edge="0.003",
            profit_factor="1.1001",
        ),
        monotonicity=_qualifying_monotonicity(),
    )

    assert assessment.qualifies is True
    assert assessment.reasons == ()


@pytest.mark.parametrize(
    ("fold1", "fold2", "combined", "reason"),
    (
        (
            _segment(samples=14, edge="0.001"),
            _segment(samples=15, edge="0.001"),
            _segment(samples=40, edge="0.003"),
            "FOLD_1_SAMPLES_TOO_LOW",
        ),
        (
            _segment(samples=15, edge="0"),
            _segment(samples=15, edge="0.001"),
            _segment(samples=40, edge="0.003"),
            "FOLD_1_NON_POSITIVE_EXPECTANCY",
        ),
        (
            _segment(samples=15, edge="0.001"),
            _segment(samples=15, edge="0.001"),
            _segment(samples=39, edge="0.003"),
            "COMBINED_SAMPLES_TOO_LOW",
        ),
        (
            _segment(samples=15, edge="0.001"),
            _segment(samples=15, edge="0.001"),
            _segment(samples=40, edge="0.0029"),
            "COMBINED_EDGE_TOO_LOW",
        ),
        (
            _segment(samples=15, edge="0.001"),
            _segment(samples=15, edge="0.001"),
            _segment(samples=40, edge="0.003", profit_factor="1.10"),
            "PROFIT_FACTOR_NOT_ABOVE_1_10",
        ),
    ),
)
def test_v3_policy_qualification_rejects_failed_hard_boundaries(
    fold1: FiveDaySelectedSegment,
    fold2: FiveDaySelectedSegment,
    combined: FiveDaySelectedSegment,
    reason: str,
) -> None:
    assessment = assess_five_day_v3_policy(
        policy=build_five_day_v3_policies()[0],
        fold1=fold1,
        fold2=fold2,
        combined=combined,
        monotonicity=_qualifying_monotonicity(),
    )

    assert assessment.qualifies is False
    assert reason in assessment.reasons


def test_v3_four_distinct_fingerprints_allow_one_registered_winner() -> None:
    review = _train_review_with_fingerprints(
        ("a", "a", "b", "b", "c", "c", "d", "d")
    )

    finalized = finalize_five_day_ranking_v3_train(review)

    assert finalized.status == "TRAIN_CANDIDATE_SELECTED"
    assert finalized.winner_policy_id == "EDGE-K30"
    assert finalized.validation_eligible is True
    assert finalized.validation_outcomes_read is False
    assert finalized.test_outcomes_read is False
    assert finalized.promotion_eligible is False
    assert finalized.trade_permission == "NO-TRADE"


def test_v3_distinct_policy_set_has_no_unqualified_winner_fallback() -> None:
    review = _train_review_with_fingerprints(
        ("a", "a", "b", "b", "c", "c", "d", "d")
    )
    unqualified = tuple(
        replace(
            value,
            qualifies=False,
            reasons=("FOLD_1_NON_POSITIVE_EXPECTANCY",),
        )
        for value in review.assessments
    )

    finalized = finalize_five_day_ranking_v3_train(
        replace(review, assessments=unqualified)
    )

    assert finalized.status == "NO_TRAIN_CANDIDATE"
    assert finalized.winner_policy_id is None
    assert finalized.validation_eligible is False


def test_v3_winner_prioritizes_worst_fold_before_combined_edge() -> None:
    review = _train_review_with_fingerprints(
        ("a", "a", "b", "b", "c", "c", "d", "d")
    )
    policies = build_five_day_v3_policies()
    high_combined = assess_five_day_v3_policy(
        policy=policies[0],
        fold1=_segment(samples=20, edge="0.001"),
        fold2=_segment(samples=20, edge="0.004"),
        combined=_segment(samples=40, edge="0.005"),
        monotonicity=_qualifying_monotonicity(),
    )
    high_worst_fold = assess_five_day_v3_policy(
        policy=policies[1],
        fold1=_segment(samples=20, edge="0.002"),
        fold2=_segment(samples=20, edge="0.003"),
        combined=_segment(samples=40, edge="0.004"),
        monotonicity=_qualifying_monotonicity(),
    )
    assessments = (
        high_combined,
        high_worst_fold,
        *(
            replace(
                value,
                qualifies=False,
                reasons=("NOT_QUALIFIED",),
            )
            for value in review.assessments[2:]
        ),
    )

    finalized = finalize_five_day_ranking_v3_train(
        replace(review, assessments=assessments)
    )

    assert finalized.winner_policy_id == "EDGE-K60"


def test_v3_train_keeps_72_variants_and_freezes_validation_inputs() -> None:
    review = build_five_day_ranking_v3_train_review(
        make_v3_research_review(()),
        parent_research_identity="a" * 64,
    )

    assert len(review.variants) == 8 * 3 * 3
    assert len(review.validation_evidence_windows.full_dates) == 378
    assert review.validation_feature_model.data_end == review.split.train[-1]
    assert review.validation_outcomes_read is False
    assert review.test_outcomes_read is False


def test_v3_train_never_admits_an_outcome_resolved_in_validation() -> None:
    review = build_five_day_ranking_v3_train_review(
        _research_with_validation_resolved_train_signal(),
        parent_research_identity="a" * 64,
    )
    formal = next(
        value
        for value in review.variants
        if value.fold_id == "train-fold-2"
        and value.policy_id == "EDGE-K30"
        and value.selection_mode == "FORMAL"
    )

    assert len(formal.segment.selection.ranking.plans) == 1
    assert formal.segment.selection.admitted == ()
    assert formal.segment.selection.incomplete is True
    assert formal.segment.metrics.net_expectancy == Decimal("0")
    assert review.validation_excluded_unresolved_train_rows == 1
    assessment = next(
        value
        for value in review.assessments
        if value.policy.policy_id == "EDGE-K30"
    )
    assert sum(
        value.triggered_completed for value in assessment.monotonicity.bands
    ) == 0


def test_v3_validation_rejects_no_winner_before_outcome_use() -> None:
    with pytest.raises(ValueError, match="unique train winner"):
        build_five_day_ranking_v3_validation_review(
            make_v3_research_review(()),
            _train_artifact(winner=False),
            parent_research_identity="a" * 64,
        )


def test_v3_validation_uses_frozen_train_evidence_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    train = _train_artifact(winner=True)
    sessions = weekday_dates(630)
    validation_observation = make_v3_observation(
        make_v3_plan(sessions[378], code="699999"),
        resolution_date=sessions[383],
    )
    monkeypatch.setattr(
        v3,
        "build_v3_evidence_windows",
        lambda *args, **kwargs: pytest.fail(
            "validation must not recalibrate hierarchy"
        ),
    )
    monkeypatch.setattr(
        v3,
        "build_v3_feature_model",
        lambda *args, **kwargs: pytest.fail(
            "validation must not recalibrate features"
        ),
    )

    review = build_five_day_ranking_v3_validation_review(
        make_v3_research_review((validation_observation,)),
        train,
        parent_research_identity="a" * 64,
    )

    assert review.trial_identity == v3_validation_trial_identity(
        train.artifact_identity,
        train.winner_policy_hash,
    )
    assert review.winner_policy_hash == train.winner_policy_hash
    assert review.segment.metrics.triggered_resolved == 1
    assert review.segment.selection.ranking.plans == (
        validation_observation.plan,
    )
    assert "SEGMENT_SAMPLES_TOO_LOW" in review.reasons
    assert "TRAIN_VALIDATION_SAMPLES_TOO_LOW" in review.reasons
    assert review.validation_outcomes_read is True
    assert review.test_outcomes_read is False
    assert review.promotion_eligible is False
    assert review.trade_permission == "NO-TRADE"


def test_v3_validation_rejects_train_lineage_mismatch() -> None:
    train = replace(
        _train_artifact(winner=True),
        parent_input_fingerprint="e" * 64,
    )

    with pytest.raises(ValueError, match="lineage mismatch"):
        build_five_day_ranking_v3_validation_review(
            make_v3_research_review(()),
            train,
            parent_research_identity="a" * 64,
        )


def test_v3_validation_rejects_tampered_train_payload_identity() -> None:
    train = _train_artifact(winner=True)
    payload = dict(train.payload)
    payload["validation_excluded_unresolved_train_rows"] = 999
    tampered = replace(train, payload=payload)

    with pytest.raises(ValueError, match="lineage mismatch"):
        build_five_day_ranking_v3_validation_review(
            make_v3_research_review(()),
            tampered,
            parent_research_identity="a" * 64,
        )
