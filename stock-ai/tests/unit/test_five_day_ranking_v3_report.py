from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    build_five_day_ranking_v3_train_review,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_report import (
    five_day_ranking_v3_train_payload,
    load_five_day_ranking_v3_train,
    write_five_day_ranking_v3_train,
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
