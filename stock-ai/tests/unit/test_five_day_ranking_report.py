from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json

import pytest

from stock_ai.buy_point_selection.five_day_ranking_report import (
    build_five_day_ranking_validation_review,
    five_day_ranking_train_payload,
    five_day_ranking_validation_payload,
    load_five_day_ranking_train,
    load_five_day_ranking_validation,
    validation_trial_identity,
    write_five_day_ranking_validation,
    write_five_day_ranking_train,
)
from stock_ai.buy_point_selection.five_day_ranking_research import (
    build_five_day_ranking_train_review,
)
from stock_ai.buy_point_selection.five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    SIZING_VERSION,
    build_five_day_return_profiles,
    five_day_profile_hash,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayResearchReview,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayPortfolioMetrics,
)
from stock_ai.buy_point_selection.validation import ChronologicalSplit


PARENT_IDENTITY = "a" * 64


def _base_review() -> FiveDayResearchReview:
    sessions = tuple(
        date(2023, 1, 2) + timedelta(days=index) for index in range(630)
    )
    split = ChronologicalSplit(
        train=sessions[:378],
        validation=sessions[378:504],
        test=sessions[504:630],
    )
    portfolio = FiveDayPortfolioMetrics(
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
    return FiveDayResearchReview(
        split=split,
        input_fingerprint="f" * 64,
        formal_rule_version="five-day-ranking-fixture-v1",
        formal_policy_hash="b" * 64,
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
        sizing_version=SIZING_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        cost_version=COST_VERSION,
        observations=(),
        train_calibrations={},
        validation_metrics=(),
        validation_portfolio=portfolio,
        point_in_time_complete=True,
        test_outcomes_read=False,
    )


def _train_review():
    return build_five_day_ranking_train_review(
        _base_review(),
        parent_research_identity=PARENT_IDENTITY,
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
        key: value for key, value in payload.items() if key != "artifact_identity"
    }
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validation_content_hash(payload: dict[str, object]) -> str:
    content = {
        key: value
        for key, value in payload.items()
        if key not in {"artifact_identity", "content_revision"}
    }
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_train_artifact_is_canonical_safe_and_contains_no_raw_outcomes(
    tmp_path,
) -> None:
    review = _train_review()

    payload = five_day_ranking_train_payload(review)
    path = write_five_day_ranking_train(review, tmp_path)
    before = path.read_bytes()
    repeated = write_five_day_ranking_train(review, tmp_path)
    loaded = load_five_day_ranking_train(path)

    assert payload["schema"] == "five-day-ranking-train-v1"
    assert payload["stage"] == "diagnose-train"
    assert payload["metric_version"] == "selected-portfolio-v2"
    assert payload["validation_outcomes_read"] is False
    assert payload["test_outcomes_read"] is False
    assert payload["registered_validation_policy"]["daily_limit"] == 3
    assert payload["promotion_eligible"] is False
    assert "observations" not in _nested_keys(payload)
    assert "validation_metrics" not in _nested_keys(payload)
    assert repeated == path
    assert path.read_bytes() == before
    assert loaded.artifact_identity == payload["artifact_identity"]
    assert loaded.parent_research_identity == PARENT_IDENTITY
    assert loaded.parent_input_fingerprint == "f" * 64


def test_validation_rejects_a_changed_preregistered_policy_before_evaluation(
    tmp_path,
) -> None:
    train_path = write_five_day_ranking_train(_train_review(), tmp_path)
    train = load_five_day_ranking_train(train_path)
    changed = replace(
        train,
        registered_validation_policy=replace(
            train.registered_validation_policy,
            daily_limit=5,
        ),
    )

    with pytest.raises(ValueError, match="registered validation policy"):
        build_five_day_ranking_validation_review(_base_review(), changed)


def test_validation_rejects_a_different_parent_input_before_evaluation(
    tmp_path,
) -> None:
    train = load_five_day_ranking_train(
        write_five_day_ranking_train(_train_review(), tmp_path)
    )
    different_parent = replace(
        _base_review(),
        input_fingerprint="e" * 64,
    )

    with pytest.raises(ValueError, match="parent or lineage"):
        build_five_day_ranking_validation_review(different_parent, train)


def test_validation_rejects_a_replaced_parent_identity_before_evaluation(
    tmp_path,
) -> None:
    train = load_five_day_ranking_train(
        write_five_day_ranking_train(_train_review(), tmp_path)
    )
    changed = replace(train, parent_research_identity="c" * 64)

    with pytest.raises(ValueError, match="parent or lineage"):
        build_five_day_ranking_validation_review(_base_review(), changed)


def test_validation_rejects_test_outcome_leak_before_evaluation(
    tmp_path,
) -> None:
    train = load_five_day_ranking_train(
        write_five_day_ranking_train(_train_review(), tmp_path)
    )
    leaked = replace(_base_review(), test_outcomes_read=True)

    with pytest.raises(ValueError, match="parent or lineage"):
        build_five_day_ranking_validation_review(leaked, train)


def test_validation_artifact_is_one_write_and_never_reads_test(
    tmp_path,
) -> None:
    train_path = write_five_day_ranking_train(_train_review(), tmp_path)
    train = load_five_day_ranking_train(train_path)
    review = build_five_day_ranking_validation_review(_base_review(), train)
    payload = five_day_ranking_validation_payload(review)

    path = write_five_day_ranking_validation(review, tmp_path)
    before = path.read_bytes()
    repeated = write_five_day_ranking_validation(review, tmp_path)
    loaded = load_five_day_ranking_validation(path)

    assert review.validation_outcomes_read is True
    assert review.test_outcomes_read is False
    assert payload["promotion_eligible"] is False
    assert "observations" not in _nested_keys(payload)
    assert "test_metrics" not in _nested_keys(payload)
    assert "freeze_eligible" not in _nested_keys(payload)
    assert len(review.profile_segments) == 4
    assert review.registered_validation_policy.daily_limit == 3
    assert repeated == path
    assert path.read_bytes() == before
    assert loaded.parent_train_identity == train.artifact_identity
    assert loaded.parent_research_identity == PARENT_IDENTITY
    assert loaded.test_outcomes_read is False
    expected_identity = validation_trial_identity(
        train.artifact_identity,
        train.registered_validation_policy_hash,
    )
    assert path.name == f"ranking-validation-{expected_identity}.json"


def test_validation_writer_rejects_conflicting_existing_trial(tmp_path) -> None:
    train = load_five_day_ranking_train(
        write_five_day_ranking_train(_train_review(), tmp_path)
    )
    review = build_five_day_ranking_validation_review(_base_review(), train)
    path = write_five_day_ranking_validation(review, tmp_path)
    before = path.read_bytes()
    conflicting = replace(review, parent_research_identity="c" * 64)

    with pytest.raises(ValueError, match="immutable ranking artifact"):
        write_five_day_ranking_validation(conflicting, tmp_path)

    assert path.read_bytes() == before


def test_train_loader_rejects_a_tampered_metric(tmp_path) -> None:
    path = write_five_day_ranking_train(_train_review(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["variants"][0]["metrics"]["net_expectancy"] = "999"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="train artifact is invalid"):
        load_five_day_ranking_train(path)


def test_train_loader_rejects_rehashed_qualified_diagnostic(tmp_path) -> None:
    path = write_five_day_ranking_train(_train_review(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["variants"][0]["metrics"]["qualifies"] = True
    payload["artifact_identity"] = _content_hash(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="train artifact is invalid"):
        load_five_day_ranking_train(path)


def test_train_loader_rejects_rehashed_test_outcome_leak(tmp_path) -> None:
    path = write_five_day_ranking_train(_train_review(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["test_outcomes_read"] = True
    payload["artifact_identity"] = _content_hash(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="train artifact is invalid"):
        load_five_day_ranking_train(path)


def test_validation_loader_rejects_a_tampered_metric(tmp_path) -> None:
    train = load_five_day_ranking_train(
        write_five_day_ranking_train(_train_review(), tmp_path)
    )
    review = build_five_day_ranking_validation_review(_base_review(), train)
    path = write_five_day_ranking_validation(review, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["global_segment"]["metrics"]["net_expectancy"] = "999"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="validation artifact is invalid"):
        load_five_day_ranking_validation(path)


def test_validation_loader_rejects_rehashed_wrong_metric_version(
    tmp_path,
) -> None:
    train = load_five_day_ranking_train(
        write_five_day_ranking_train(_train_review(), tmp_path)
    )
    review = build_five_day_ranking_validation_review(_base_review(), train)
    path = write_five_day_ranking_validation(review, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metric_version"] = "legacy-triggered-v1"
    payload["content_revision"] = _validation_content_hash(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="validation artifact is invalid"):
        load_five_day_ranking_validation(path)


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("parent_train_identity", "d" * 64),
        ("registered_validation_policy_hash", "e" * 64),
        ("test_outcomes_read", True),
    ),
)
def test_validation_loader_rejects_rehashed_safety_mutation(
    tmp_path,
    key: str,
    value: object,
) -> None:
    train = load_five_day_ranking_train(
        write_five_day_ranking_train(_train_review(), tmp_path)
    )
    review = build_five_day_ranking_validation_review(_base_review(), train)
    path = write_five_day_ranking_validation(review, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[key] = value
    payload["content_revision"] = _validation_content_hash(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="validation artifact is invalid"):
        load_five_day_ranking_validation(path)
