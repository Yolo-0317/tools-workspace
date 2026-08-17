from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    V3_POLICY_IDS,
    build_five_day_v3_policies,
    five_day_v3_policy_hash,
    five_day_v3_policy_set_hash,
    score_five_day_plan_v3,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_evidence import (
    V3BucketKey,
    V3CandidateEvidence,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_features import (
    V3FeatureAdjustment,
)

from five_day_ranking_v3_fixtures import make_v3_plan


START = date(2023, 1, 2)


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
