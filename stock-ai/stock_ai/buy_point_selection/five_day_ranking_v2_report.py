"""Immutable evidence artifacts for the five-day V2 train review."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Mapping

from stock_ai.market_codes import normalize_code6

from .five_day_ranking_v2 import (
    V2_POLICY_IDS,
    V2_RANKING_VERSION,
    V2_TRAIN_SCHEMA,
    FiveDayRankingV2TrainReview,
    FiveDayRankingV2ValidationReview,
    build_five_day_v2_policies,
    five_day_v2_policy_hash,
    five_day_v2_policy_set_hash,
    v2_validation_trial_identity,
)


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _primitive(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {
            field.name: _primitive(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _primitive(item)
            for key, item in sorted(
                value.items(), key=lambda pair: str(pair[0])
            )
        }
    if isinstance(value, (tuple, list)):
        return [_primitive(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, Decimal)):
        return str(value)
    return value


def _plan_key(plan) -> dict[str, object]:
    return {
        "signal_date": plan.candidate.signal_date.isoformat(),
        "code": normalize_code6(plan.candidate.code),
        "structure_id": plan.structure_id,
        "profile_id": plan.profile.profile_id,
    }


def _segment_content(segment) -> dict[str, object]:
    selection = segment.selection
    return {
        "metric_version": segment.metric_version,
        "metrics": _primitive(segment.metrics),
        "portfolio": _primitive(segment.portfolio),
        "ranked_plan_keys": [
            {
                **_plan_key(row.plan),
                "rank": row.rank,
                "selected": row.selected,
            }
            for row in selection.ranking.ranked
        ],
        "selected_plan_keys": [
            _plan_key(plan) for plan in selection.ranking.plans
        ],
        "admitted_trade_keys": [
            _plan_key(value.plan) for value in selection.admitted
        ],
        "rejection_counts": dict(
            sorted(selection.ranking.rejection_counts.items())
        ),
        "funnel_counts": dict(sorted(selection.funnel_counts.items())),
        "incomplete": selection.incomplete,
    }


def _scored_content(value) -> dict[str, object]:
    return {
        "plan_key": _plan_key(value.plan),
        "calibration": _primitive(value.calibration),
        "shrunk_edge": str(value.shrunk_edge),
        "components": _primitive(value.components),
        "score": str(value.score),
        "rank": value.rank,
        "selected": value.selected,
    }


def _variant_content(value) -> dict[str, object]:
    return {
        "fold_id": value.fold_id,
        "policy_id": value.policy_id,
        "daily_limit": value.daily_limit,
        "scored": [_scored_content(row) for row in value.scored],
        "segment": _segment_content(value.segment),
    }


def _assessment_content(value) -> dict[str, object]:
    return {
        "policy_id": value.policy.policy_id,
        "fold1": _segment_content(value.fold1),
        "fold2": _segment_content(value.fold2),
        "combined": _segment_content(value.combined),
        "monotonicity": _primitive(value.monotonicity),
        "worst_fold_expectancy": str(value.worst_fold_expectancy),
        "qualifies": value.qualifies,
        "reasons": list(value.reasons),
    }


def _v2_train_content(
    review: FiveDayRankingV2TrainReview,
) -> dict[str, object]:
    fold_order = {
        "train-fold-1": 0,
        "train-fold-2": 1,
        "train-combined": 2,
    }
    variants = tuple(
        sorted(
            review.variants,
            key=lambda value: (
                V2_POLICY_IDS.index(value.policy_id),
                value.daily_limit,
                fold_order[value.fold_id],
            ),
        )
    )
    assessments = tuple(
        sorted(
            review.assessments,
            key=lambda value: V2_POLICY_IDS.index(value.policy.policy_id),
        )
    )
    return {
        "schema": review.schema,
        "ranking_version": review.ranking_version,
        "parent_research_identity": review.parent_research_identity,
        "parent_input_fingerprint": review.parent_input_fingerprint,
        "split": _primitive(review.split),
        "formal_rule_version": review.formal_rule_version,
        "formal_policy_hash": review.formal_policy_hash,
        "profile_matrix_hash": review.profile_matrix_hash,
        "sizing_version": review.sizing_version,
        "evaluator_version": review.evaluator_version,
        "cost_version": review.cost_version,
        "policy_set_hash": review.policy_set_hash,
        "policies": _primitive(review.policies),
        "folds": _primitive(review.folds),
        "variants": [_variant_content(value) for value in variants],
        "assessments": [
            _assessment_content(value) for value in assessments
        ],
        "winner_policy_id": review.winner_policy_id,
        "winner_policy_hash": review.winner_policy_hash,
        "winner_train_samples": review.winner_train_samples,
        "status": review.status,
        "validation_eligible": review.validation_eligible,
        "validation_outcomes_read": review.validation_outcomes_read,
        "test_outcomes_read": review.test_outcomes_read,
        "promotion_eligible": review.promotion_eligible,
        "trade_permission": review.trade_permission,
    }


def five_day_ranking_v2_train_payload(
    review: FiveDayRankingV2TrainReview,
) -> dict[str, object]:
    """Return the canonical aggregate train-evidence payload."""
    content = _v2_train_content(review)
    registered = _primitive(build_five_day_v2_policies())
    if (
        content["schema"] != V2_TRAIN_SCHEMA
        or content["ranking_version"] != V2_RANKING_VERSION
        or content["validation_outcomes_read"] is not False
        or content["test_outcomes_read"] is not False
        or content["promotion_eligible"] is not False
        or content["trade_permission"] != "NO-TRADE"
        or content["policy_set_hash"] != five_day_v2_policy_set_hash()
        or content["policies"] != registered
        or len(content["policies"]) != 12
        or len(content["variants"]) != 108
    ):
        raise ValueError("ranking v2 train artifact safety mismatch")
    winner_id = content["winner_policy_id"]
    winner = next(
        (
            policy
            for policy in build_five_day_v2_policies()
            if policy.policy_id == winner_id
        ),
        None,
    )
    if (
        content["winner_policy_hash"]
        != (five_day_v2_policy_hash(winner) if winner else None)
        or content["validation_eligible"] is (winner is None)
        or content["status"]
        != (
            "TRAIN_CANDIDATE_SELECTED"
            if winner
            else "NO_TRAIN_CANDIDATE"
        )
    ):
        raise ValueError("ranking v2 train artifact winner mismatch")
    return {**content, "artifact_identity": _sha256(content)}


def _write_exclusive_or_verify(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(
                "immutable ranking v2 artifact content mismatch"
            ) from None


def write_five_day_ranking_v2_train(
    review: FiveDayRankingV2TrainReview,
    output_dir: str | Path,
) -> Path:
    """Write once by content identity, or verify identical prior bytes."""
    payload = five_day_ranking_v2_train_payload(review)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (
        f"ranking-v2-train-{payload['artifact_identity']}.json"
    )
    content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    _write_exclusive_or_verify(path, content)
    return path


@dataclass(frozen=True)
class FiveDayRankingV2TrainArtifact:
    artifact_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    policy_set_hash: str
    winner_policy_id: str | None
    winner_policy_hash: str | None
    winner_train_samples: int
    validation_eligible: bool
    payload: Mapping[str, object]


def _nested_keys(value: object) -> set[str]:
    found: set[str] = set()
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            found.update(str(key) for key in item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def _valid_variant_registry(variants: object) -> bool:
    if not isinstance(variants, list):
        return False
    expected = {
        (fold_id, policy_id, daily_limit)
        for fold_id in (
            "train-fold-1",
            "train-fold-2",
            "train-combined",
        )
        for policy_id in V2_POLICY_IDS
        for daily_limit in (1, 3, 5)
    }
    try:
        actual = {
            (
                str(value["fold_id"]),
                str(value["policy_id"]),
                int(value["daily_limit"]),
            )
            for value in variants
        }
    except (KeyError, TypeError, ValueError):
        return False
    return len(variants) == 108 and actual == expected


def _winner_semantics_are_valid(payload: Mapping[str, object]) -> bool:
    winner_id = payload["winner_policy_id"]
    policies = build_five_day_v2_policies()
    winner = next(
        (value for value in policies if value.policy_id == winner_id),
        None,
    )
    assessments = payload["assessments"]
    if not isinstance(assessments, list) or len(assessments) != 12:
        return False
    by_policy = {
        str(value["policy_id"]): value
        for value in assessments
    }
    if set(by_policy) != set(V2_POLICY_IDS):
        return False
    qualified = {
        policy_id
        for policy_id, value in by_policy.items()
        if value["qualifies"] is True
    }
    if winner is None:
        return (
            winner_id is None
            and payload["winner_policy_hash"] is None
            and int(payload["winner_train_samples"]) == 0
            and payload["validation_eligible"] is False
            and payload["status"] == "NO_TRAIN_CANDIDATE"
            and not qualified
        )
    assessment = by_policy.get(winner.policy_id)
    if assessment is None:
        return False
    return (
        winner.policy_id in qualified
        and payload["winner_policy_hash"]
        == five_day_v2_policy_hash(winner)
        and int(payload["winner_train_samples"])
        == int(
            assessment["combined"]["metrics"]["triggered_resolved"]
        )
        and payload["validation_eligible"] is True
        and payload["status"] == "TRAIN_CANDIDATE_SELECTED"
    )


def load_five_day_ranking_v2_train(
    path: str | Path,
    *,
    expected_parent_research_identity: str | None = None,
) -> FiveDayRankingV2TrainArtifact:
    """Load only canonical, current-registry, train-only V2 evidence."""
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError
        identity = str(payload["artifact_identity"])
        content = {
            key: value
            for key, value in payload.items()
            if key != "artifact_identity"
        }
        registered = _primitive(build_five_day_v2_policies())
        forbidden = {"observations", "selected_observations"}
        parent_identity = str(payload["parent_research_identity"])
        if (
            len(identity) != 64
            or any(value not in "0123456789abcdef" for value in identity)
            or identity != _sha256(content)
            or target.name != f"ranking-v2-train-{identity}.json"
            or payload["schema"] != V2_TRAIN_SCHEMA
            or payload["ranking_version"] != V2_RANKING_VERSION
            or payload["policy_set_hash"] != five_day_v2_policy_set_hash()
            or payload["policies"] != registered
            or not _valid_variant_registry(payload["variants"])
            or payload["validation_outcomes_read"] is not False
            or payload["test_outcomes_read"] is not False
            or payload["promotion_eligible"] is not False
            or payload["trade_permission"] != "NO-TRADE"
            or forbidden.intersection(_nested_keys(payload))
            or len(parent_identity) != 64
            or any(
                value not in "0123456789abcdef"
                for value in parent_identity
            )
            or (
                expected_parent_research_identity is not None
                and parent_identity != expected_parent_research_identity
            )
            or not _winner_semantics_are_valid(payload)
        ):
            raise ValueError
    except (
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        raise ValueError(
            "five-day ranking v2 train artifact is invalid"
        ) from None
    return FiveDayRankingV2TrainArtifact(
        artifact_identity=identity,
        parent_research_identity=parent_identity,
        parent_input_fingerprint=str(payload["parent_input_fingerprint"]),
        policy_set_hash=str(payload["policy_set_hash"]),
        winner_policy_id=(
            str(payload["winner_policy_id"])
            if payload["winner_policy_id"] is not None
            else None
        ),
        winner_policy_hash=(
            str(payload["winner_policy_hash"])
            if payload["winner_policy_hash"] is not None
            else None
        ),
        winner_train_samples=int(payload["winner_train_samples"]),
        validation_eligible=bool(payload["validation_eligible"]),
        payload=payload,
    )


def _v2_validation_content(
    review: FiveDayRankingV2ValidationReview,
) -> dict[str, object]:
    return {
        "schema": review.schema,
        "trial_identity": review.trial_identity,
        "parent_train_identity": review.parent_train_identity,
        "parent_research_identity": review.parent_research_identity,
        "parent_input_fingerprint": review.parent_input_fingerprint,
        "winner_policy_id": review.winner_policy_id,
        "winner_policy_hash": review.winner_policy_hash,
        "validation_dates": [
            value.isoformat() for value in review.validation_dates
        ],
        "segment": _segment_content(review.segment),
        "qualifies_for_test_design": review.qualifies_for_test_design,
        "reasons": list(review.reasons),
        "validation_outcomes_read": review.validation_outcomes_read,
        "test_outcomes_read": review.test_outcomes_read,
        "promotion_eligible": review.promotion_eligible,
        "trade_permission": review.trade_permission,
    }


def _validation_content_is_safe(content: Mapping[str, object]) -> bool:
    policy = next(
        (
            value
            for value in build_five_day_v2_policies()
            if value.policy_id == content["winner_policy_id"]
        ),
        None,
    )
    return (
        content["schema"] == "five-day-ranking-v2-validation-v1"
        and policy is not None
        and content["winner_policy_hash"] == five_day_v2_policy_hash(policy)
        and content["trial_identity"]
        == v2_validation_trial_identity(
            str(content["parent_train_identity"]),
            str(content["winner_policy_hash"]),
        )
        and content["qualifies_for_test_design"]
        is (not content["reasons"])
        and content["validation_outcomes_read"] is True
        and content["test_outcomes_read"] is False
        and content["promotion_eligible"] is False
        and content["trade_permission"] == "NO-TRADE"
        and not {"observations", "selected_observations"}.intersection(
            _nested_keys(content)
        )
    )


def write_five_day_ranking_v2_validation(
    review: FiveDayRankingV2ValidationReview,
    output_dir: str | Path,
) -> Path:
    """Write the unique validation trial without permitting replacement."""
    content = _v2_validation_content(review)
    if not _validation_content_is_safe(content):
        raise ValueError("ranking v2 validation artifact safety mismatch")
    payload = {**content, "artifact_identity": _sha256(content)}
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (
        f"ranking-v2-validation-{review.trial_identity}.json"
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    _write_exclusive_or_verify(path, serialized)
    return path


def load_five_day_ranking_v2_validation(
    path: str | Path,
    *,
    expected_train_identity: str,
    expected_policy_hash: str,
) -> Mapping[str, object]:
    """Load one validation trial only under its frozen train identity."""
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError
        artifact_identity = str(payload["artifact_identity"])
        content = {
            key: value
            for key, value in payload.items()
            if key != "artifact_identity"
        }
        expected_trial = v2_validation_trial_identity(
            expected_train_identity,
            expected_policy_hash,
        )
        if (
            artifact_identity != _sha256(content)
            or payload["trial_identity"] != expected_trial
            or target.name
            != f"ranking-v2-validation-{expected_trial}.json"
            or payload["parent_train_identity"]
            != expected_train_identity
            or payload["winner_policy_hash"] != expected_policy_hash
            or not _validation_content_is_safe(content)
        ):
            raise ValueError
    except (
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        raise ValueError(
            "five-day ranking v2 validation artifact is invalid"
        ) from None
    return payload
