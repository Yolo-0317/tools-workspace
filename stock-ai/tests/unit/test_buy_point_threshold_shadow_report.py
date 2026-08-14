from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.models import DetectedSetup, SetupType
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ExactRecallComparison,
    aggregate_profile_metrics,
    freeze_threshold_profiles,
)
from stock_ai.buy_point_selection.threshold_shadow_report import (
    ThresholdWindowReview,
    freeze_payload,
    load_threshold_freeze_artifact,
    load_threshold_research_artifact,
    load_threshold_test_artifact,
    render_threshold_shadow_markdown,
    threshold_shadow_identity,
    threshold_shadow_payload,
    write_threshold_freeze,
    write_threshold_shadow_revision,
)
from stock_ai.buy_point_selection.threshold_shadow_research import (
    ThresholdShadowCandidate,
    ThresholdShadowReplay,
    ThresholdShadowSetup,
    build_threshold_profiles,
    profile_matrix_hash,
)


SIGNAL = date(2026, 7, 20)


def _candidate() -> ThresholdShadowCandidate:
    profile = build_threshold_profiles()[0]
    setup = DetectedSetup(
        "600001",
        SetupType.PRE_BREAKOUT,
        SIGNAL,
        SIGNAL - timedelta(days=20),
        Decimal("10.10"),
        Decimal("9.90"),
        Decimal("0.80"),
        ("SHADOW",),
        {"platform_width": Decimal("0.13")},
    )
    shadow = ThresholdShadowSetup(
        "600001", SIGNAL, profile, setup, Decimal("0.0833333333")
    )
    plan = PricePlan(
        "structure-1",
        "600001",
        SetupType.PRE_BREAKOUT,
        SIGNAL,
        Decimal("10"),
        Decimal("10.11"),
        Decimal("9.86"),
        Decimal("10.61"),
        Decimal("0.25"),
        Decimal("2"),
        100,
        SIGNAL + timedelta(days=2),
    )
    return ThresholdShadowCandidate(
        "600001",
        SIGNAL,
        profile.profile_id,
        shadow,
        plan,
        Decimal("200000"),
        Decimal("1.00"),
    )


def _review() -> ThresholdWindowReview:
    profiles = build_threshold_profiles()
    candidate = _candidate()
    replay = ThresholdShadowReplay(
        (SIGNAL,), (), (candidate.shadow_setup,), (candidate,), ()
    )
    return ThresholdWindowReview(
        stage="research",
        signal_dates=(SIGNAL,),
        outcome_cutoff=SIGNAL + timedelta(days=5),
        v5_case_identity="v5-case",
        input_fingerprint="input-hash",
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=profile_matrix_hash(profiles),
        freeze_hash=None,
        profiles=profiles,
        replay=replay,
        shadow_outcomes=(),
        profile_metrics=aggregate_profile_metrics((candidate.profile_id,), ()),
        formal_candidates=(),
        formal_outcomes=(),
        selected_candidates=(),
        selected_outcomes=(),
        exact_recall=ExactRecallComparison(0, 0, 0, 0, 1),
        risk_coverage_complete=False,
        test_consumed=False,
    )


def test_research_payload_reconciles_rows_and_is_explicitly_non_trading() -> None:
    """Catches raw evidence disappearing or receiving trade permission."""
    payload = threshold_shadow_payload(_review())

    assert payload["schema"] == "buy-point-threshold-shadow-v1"
    assert payload["stage"] == "research"
    assert payload["status"] == "CASE_ANALYSIS_ONLY"
    assert payload["trade_permission"] == "NO-TRADE"
    assert len(payload["raw_setups"]) == payload["metrics"]["raw_setups"] == 1
    assert len(payload["candidates"]) == payload["metrics"]["candidates"] == 1
    assert payload["candidates"][0]["executable_shares"] == 0
    assert payload["formal_candidates"] == []
    assert payload["formal_outcomes"] == []
    assert not payload["promotion_eligible"]


def test_identity_write_and_markdown_are_immutable_and_explicit(
    tmp_path: Path,
) -> None:
    """Catches lineage collisions, silent overwrite, or missing safety copy."""
    review = _review()
    changed_lineage = replace(review, input_fingerprint="different-input")

    assert threshold_shadow_identity(review) != threshold_shadow_identity(
        changed_lineage
    )
    first_paths = write_threshold_shadow_revision(review, tmp_path)
    assert write_threshold_shadow_revision(review, tmp_path) == first_paths
    with pytest.raises(ValueError, match="immutable artifact content mismatch"):
        write_threshold_shadow_revision(
            replace(
                review,
                exact_recall=ExactRecallComparison(1, 0, 0, 0, 1),
            ),
            tmp_path,
        )

    markdown = render_threshold_shadow_markdown(review)
    assert "股票-日期样本存在重叠，不能视为相互独立" in markdown
    assert "可执行仓位为 0" in markdown
    assert "不能晋级正式规则" in markdown


def test_test_stage_requires_a_consumed_frozen_hash() -> None:
    """Catches an unfrozen or reusable holdout being labeled as test evidence."""
    with pytest.raises(ValueError, match="test stage requires consumed freeze"):
        threshold_shadow_payload(
            replace(_review(), stage="test", freeze_hash=None, test_consumed=False)
        )


def test_freeze_and_stage_loaders_validate_immutable_artifacts(
    tmp_path: Path,
) -> None:
    """Catches a malformed freeze or wrong-stage artifact entering holdout."""
    profiles = build_threshold_profiles()
    freeze = freeze_threshold_profiles(
        profiles=profiles,
        training_identities=("research-a", "research-b"),
        metrics=(),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=profile_matrix_hash(profiles),
        risk_coverage_complete=False,
    )

    payload = freeze_payload(freeze)
    assert payload["schema"] == "buy-point-threshold-shadow-v1"
    assert payload["stage"] == "freeze"
    assert payload["empty"]
    assert not payload["promotion_eligible"]
    freeze_json, freeze_markdown = write_threshold_freeze(freeze, tmp_path)
    assert freeze_markdown.exists()
    assert load_threshold_freeze_artifact(freeze_json) == freeze
    with pytest.raises(ValueError, match="freeze model mismatch"):
        freeze_payload(replace(freeze, promotion_eligible=True))

    research_json, _ = write_threshold_shadow_revision(_review(), tmp_path)
    assert load_threshold_research_artifact(research_json)["stage"] == "research"
    with pytest.raises(ValueError, match="expected test artifact"):
        load_threshold_test_artifact(research_json)
