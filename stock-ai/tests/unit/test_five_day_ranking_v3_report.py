from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    FiveDayRankingV3ValidationReview,
    build_five_day_ranking_v3_train_review,
    build_five_day_v3_policies,
    five_day_v3_policy_hash,
    v3_validation_trial_identity,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_report import (
    five_day_ranking_v3_train_payload,
    load_five_day_ranking_v3_train,
    load_five_day_ranking_v3_validation,
    write_five_day_ranking_v3_train,
    write_five_day_ranking_v3_validation,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayPortfolioMetrics,
    FiveDayRanking,
    FiveDaySegmentMetrics,
    FiveDaySelectedSegment,
    FiveDaySelection,
)

from five_day_ranking_v3_fixtures import (
    make_v3_observation,
    make_v3_plan,
    make_v3_research_review,
    weekday_dates,
)


PARENT_IDENTITY = "a" * 64


def _complete_v3_train_review():
    sessions = weekday_dates(630)
    observation = make_v3_observation(
        make_v3_plan(sessions[0]),
        resolution_date=sessions[1],
    )
    return build_five_day_ranking_v3_train_review(
        make_v3_research_review((observation,)),
        parent_research_identity=PARENT_IDENTITY,
    )


def _complete_v3_validation_review() -> FiveDayRankingV3ValidationReview:
    train_identity = "1" * 64
    policy = build_five_day_v3_policies()[0]
    metrics_reasons = (
        "SEGMENT_SAMPLES_TOO_LOW",
        "TRAIN_VALIDATION_SAMPLES_TOO_LOW",
        "NON_POSITIVE_EXPECTANCY",
        "PROFIT_FACTOR_TOO_LOW",
        "WILSON_LOWER_TOO_LOW",
        "POSITIVE_WINDOW_RATIO_TOO_LOW",
    )
    portfolio_reasons = (
        "NO_ACCEPTED_TRADES",
        "GROSS_PROFIT_UNAVAILABLE",
    )
    segment = FiveDaySelectedSegment(
        metric_version="selected-portfolio-v2",
        metrics=FiveDaySegmentMetrics(
            profile_id="GLOBAL",
            segment="validation",
            triggered_resolved=0,
            net_expectancy=Decimal("0"),
            profit_factor=None,
            profitable_wilson_lower=Decimal("0"),
            stop_rate=Decimal("0"),
            positive_window_ratio=Decimal("0"),
            maximum_drawdown=Decimal("0"),
            qualifies=False,
            reasons=metrics_reasons,
        ),
        portfolio=FiveDayPortfolioMetrics(
            accepted_trades=0,
            maximum_drawdown=Decimal("0"),
            maximum_stock_trade_share=Decimal("0"),
            maximum_stock_profit_share=Decimal("0"),
            maximum_sector_trade_share=Decimal("0"),
            maximum_sector_profit_share=Decimal("0"),
            top5_profit_share=Decimal("0"),
            qualifies=False,
            reasons=portfolio_reasons,
        ),
        selection=FiveDaySelection(
            ranking=FiveDayRanking(plans=(), rejection_counts={}),
            selected_observations=(),
            admitted=(),
            funnel_counts={
                "SELECTED_PLANS": 0,
                "ADMITTED_TRADES": 0,
            },
            incomplete=False,
        ),
    )
    winner_hash = five_day_v3_policy_hash(policy)
    return FiveDayRankingV3ValidationReview(
        schema="five-day-ranking-v3-validation-v1",
        trial_identity=v3_validation_trial_identity(
            train_identity,
            winner_hash,
        ),
        parent_train_identity=train_identity,
        parent_research_identity=PARENT_IDENTITY,
        parent_input_fingerprint="f" * 64,
        winner_policy_id=policy.policy_id,
        winner_policy_hash=winner_hash,
        validation_dates=weekday_dates(630)[378:504],
        segment=segment,
        qualifies_for_test_design=False,
        reasons=(*metrics_reasons, *portfolio_reasons),
        validation_outcomes_read=True,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )


def _nested_keys(value: object) -> set[str]:
    found: set[str] = set()
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            found.update(str(key) for key in item)
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
    return found


def _content_hash(payload: dict[str, object]) -> str:
    content = {
        key: value
        for key, value in payload.items()
        if key != "artifact_identity"
    }
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_v3_train_writer_is_byte_idempotent_and_aggregate_only(
    tmp_path: Path,
) -> None:
    review = _complete_v3_train_review()

    first = write_five_day_ranking_v3_train(review, tmp_path)
    before = first.read_bytes()
    second = write_five_day_ranking_v3_train(review, tmp_path)
    loaded = load_five_day_ranking_v3_train(first)
    payload = json.loads(before)

    assert first == second
    assert first.read_bytes() == before
    assert loaded.artifact_identity in first.name
    assert len(payload["policies"]) == 8
    assert len(payload["variants"]) == 72
    assert not {"observations", "selected_observations"}.intersection(
        _nested_keys(payload)
    )
    assert len(loaded.validation_evidence_windows.full_dates) == 378
    assert loaded.validation_feature_model.data_end == review.split.train[-1]
    assert loaded.validation_evidence_windows.full
    assert loaded.validation_feature_model.effects


def test_v3_train_payload_contains_frozen_models_and_safety_flags() -> None:
    payload = five_day_ranking_v3_train_payload(
        _complete_v3_train_review()
    )

    assert payload["schema"] == "five-day-ranking-v3-train-v1"
    assert payload["ranking_version"] == "five-day-ranking-key-v3"
    assert payload["status"] == "POLICY_SET_DEGENERATE"
    assert payload["validation_outcomes_read"] is False
    assert payload["test_outcomes_read"] is False
    assert payload["promotion_eligible"] is False
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["validation_evidence_windows"]["full_dates"]
    assert payload["validation_feature_model"]["boundaries"]


def test_v3_train_writer_never_overwrites_an_identity_conflict(
    tmp_path: Path,
) -> None:
    review = _complete_v3_train_review()
    path = write_five_day_ranking_v3_train(review, tmp_path)
    path.write_text("{}\n", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ValueError, match="artifact conflict"):
        write_five_day_ranking_v3_train(review, tmp_path)

    assert path.read_bytes() == before


def test_v3_train_loader_rejects_registry_or_lineage_tamper(
    tmp_path: Path,
) -> None:
    path = write_five_day_ranking_v3_train(
        _complete_v3_train_review(),
        tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["policy_set_hash"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid ranking v3 train artifact"):
        load_five_day_ranking_v3_train(path)


def test_v3_train_loader_rejects_rehashed_policy_tamper(
    tmp_path: Path,
) -> None:
    path = write_five_day_ranking_v3_train(
        _complete_v3_train_review(),
        tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["policies"][0]["definition"]["shrinkage_k"] = 31
    payload["artifact_identity"] = _content_hash(payload)
    tampered = tmp_path / (
        f"ranking-v3-train-{payload['artifact_identity']}.json"
    )
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid ranking v3 train artifact"):
        load_five_day_ranking_v3_train(tampered)


def test_v3_train_loader_rejects_rehashed_frozen_model_tamper(
    tmp_path: Path,
) -> None:
    path = write_five_day_ranking_v3_train(
        _complete_v3_train_review(),
        tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["validation_feature_model"]["effects"][0][
        "full_samples"
    ] = -1
    payload["artifact_identity"] = _content_hash(payload)
    tampered = tmp_path / (
        f"ranking-v3-train-{payload['artifact_identity']}.json"
    )
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid ranking v3 train artifact"):
        load_five_day_ranking_v3_train(tampered)


def test_v3_train_loader_enforces_expected_parent_identity(
    tmp_path: Path,
) -> None:
    path = write_five_day_ranking_v3_train(
        _complete_v3_train_review(),
        tmp_path,
    )

    with pytest.raises(ValueError, match="invalid ranking v3 train artifact"):
        load_five_day_ranking_v3_train(
            path,
            expected_parent_research_identity="b" * 64,
        )


def test_v3_validation_writer_is_byte_idempotent_and_strictly_loaded(
    tmp_path: Path,
) -> None:
    review = _complete_v3_validation_review()

    first = write_five_day_ranking_v3_validation(review, tmp_path)
    before = first.read_bytes()
    second = write_five_day_ranking_v3_validation(review, tmp_path)
    loaded = load_five_day_ranking_v3_validation(
        first,
        expected_train_identity=review.parent_train_identity,
        expected_policy_hash=review.winner_policy_hash,
    )

    assert first == second
    assert first.read_bytes() == before
    assert loaded["trial_identity"] == review.trial_identity
    assert loaded["validation_outcomes_read"] is True
    assert loaded["test_outcomes_read"] is False
    assert not {"observations", "selected_observations"}.intersection(
        _nested_keys(loaded)
    )


def test_v3_validation_writer_never_overwrites_conflict(
    tmp_path: Path,
) -> None:
    review = _complete_v3_validation_review()
    path = write_five_day_ranking_v3_validation(review, tmp_path)
    path.write_text("{}\n", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ValueError, match="artifact conflict"):
        write_five_day_ranking_v3_validation(review, tmp_path)

    assert path.read_bytes() == before


def test_v3_validation_loader_requires_frozen_train_and_policy(
    tmp_path: Path,
) -> None:
    review = _complete_v3_validation_review()
    path = write_five_day_ranking_v3_validation(review, tmp_path)

    with pytest.raises(ValueError, match="invalid ranking v3 validation"):
        load_five_day_ranking_v3_validation(
            path,
            expected_train_identity="2" * 64,
            expected_policy_hash=review.winner_policy_hash,
        )


def test_v3_validation_loader_rejects_rehashed_safety_tamper(
    tmp_path: Path,
) -> None:
    review = _complete_v3_validation_review()
    path = write_five_day_ranking_v3_validation(review, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["promotion_eligible"] = True
    payload["artifact_identity"] = _content_hash(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid ranking v3 validation"):
        load_five_day_ranking_v3_validation(
            path,
            expected_train_identity=review.parent_train_identity,
            expected_policy_hash=review.winner_policy_hash,
        )


def test_v3_validation_writer_records_incomplete_selection_fail_closed(
    tmp_path: Path,
) -> None:
    review = _complete_v3_validation_review()
    segment = replace(
        review.segment,
        metrics=replace(
            review.segment.metrics,
            reasons=(
                *review.segment.metrics.reasons,
                "SELECTION_INCOMPLETE",
            ),
        ),
        selection=replace(review.segment.selection, incomplete=True),
    )
    incomplete = replace(
        review,
        segment=segment,
        reasons=(
            *review.segment.metrics.reasons,
            "SELECTION_INCOMPLETE",
            *review.segment.portfolio.reasons,
        ),
    )

    path = write_five_day_ranking_v3_validation(incomplete, tmp_path)
    loaded = load_five_day_ranking_v3_validation(
        path,
        expected_train_identity=incomplete.parent_train_identity,
        expected_policy_hash=incomplete.winner_policy_hash,
    )

    assert loaded["segment"]["incomplete"] is True
    assert loaded["qualifies_for_test_design"] is False
    assert "SELECTION_INCOMPLETE" in loaded["reasons"]
