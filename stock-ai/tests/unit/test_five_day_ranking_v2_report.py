from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Callable

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v2 import (
    build_five_day_ranking_v2_train_review,
)
from stock_ai.buy_point_selection.five_day_ranking_v2_report import (
    five_day_ranking_v2_train_payload,
    load_five_day_ranking_v2_train,
    write_five_day_ranking_v2_train,
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


def _v2_train_review_fixture():
    return build_five_day_ranking_v2_train_review(
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


def test_v2_train_artifact_is_canonical_complete_and_outcome_safe(
    tmp_path,
) -> None:
    review = _v2_train_review_fixture()

    payload = five_day_ranking_v2_train_payload(review)
    path = write_five_day_ranking_v2_train(review, tmp_path)
    before = path.read_bytes()

    assert payload["schema"] == "five-day-ranking-v2-train-v1"
    assert payload["ranking_version"] == "five-day-ranking-key-v2"
    assert len(payload["policies"]) == 12
    assert len(payload["variants"]) == 108
    assert payload["validation_outcomes_read"] is False
    assert payload["test_outcomes_read"] is False
    assert payload["promotion_eligible"] is False
    assert "observations" not in _nested_keys(payload)
    assert path.name == (
        f"ranking-v2-train-{payload['artifact_identity']}.json"
    )
    assert write_five_day_ranking_v2_train(review, tmp_path) == path
    assert path.read_bytes() == before


def test_v2_train_loader_returns_verified_no_winner_lineage(tmp_path) -> None:
    path = write_five_day_ranking_v2_train(
        _v2_train_review_fixture(),
        tmp_path,
    )

    artifact = load_five_day_ranking_v2_train(
        path,
        expected_parent_research_identity=PARENT_IDENTITY,
    )

    assert artifact.artifact_identity in path.name
    assert artifact.parent_research_identity == PARENT_IDENTITY
    assert artifact.parent_input_fingerprint == "f" * 64
    assert len(artifact.policy_set_hash) == 64
    assert artifact.winner_policy_id is None
    assert artifact.winner_policy_hash is None
    assert artifact.winner_train_samples == 0
    assert artifact.validation_eligible is False


def test_v2_train_writer_rejects_conflicting_existing_identity(
    tmp_path,
) -> None:
    review = _v2_train_review_fixture()
    path = write_five_day_ranking_v2_train(review, tmp_path)
    path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="immutable ranking v2 artifact content mismatch",
    ):
        write_five_day_ranking_v2_train(review, tmp_path)

    assert path.read_text(encoding="utf-8") == "{}\n"


@pytest.mark.parametrize(
    ("mutate", "rehash"),
    (
        (
            lambda value: value["policies"][0]["weights"].update(edge=34),
            True,
        ),
        (
            lambda value: value["variants"][0]["segment"]["metrics"].update(
                net_expectancy="9"
            ),
            False,
        ),
        (
            lambda value: value.update(parent_research_identity="b" * 64),
            True,
        ),
        (lambda value: value.update(winner_policy_id="NOT-REGISTERED"), True),
        (lambda value: value.update(validation_eligible=True), True),
        (lambda value: value.update(test_outcomes_read=True), True),
    ),
)
def test_v2_train_loader_rejects_semantic_tampering(
    tmp_path: Path,
    mutate: Callable[[dict[str, object]], object],
    rehash: bool,
) -> None:
    payload = five_day_ranking_v2_train_payload(
        _v2_train_review_fixture()
    )
    mutate(payload)
    if rehash:
        payload["artifact_identity"] = _content_hash(payload)
    path = tmp_path / (
        f"ranking-v2-train-{payload['artifact_identity']}.json"
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="five-day ranking v2 train artifact is invalid",
    ):
        load_five_day_ranking_v2_train(
            path,
            expected_parent_research_identity=PARENT_IDENTITY,
        )
