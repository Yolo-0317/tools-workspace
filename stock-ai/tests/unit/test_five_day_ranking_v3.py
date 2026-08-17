from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    V3_POLICY_IDS,
    build_five_day_v3_policies,
    five_day_v3_policy_hash,
    five_day_v3_policy_set_hash,
    rank_five_day_plans_v3,
    score_five_day_plan_v3,
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
    FiveDaySelection,
    admit_five_day_ranking,
)

from five_day_ranking_v3_fixtures import (
    make_v3_observation,
    make_v3_plan,
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
