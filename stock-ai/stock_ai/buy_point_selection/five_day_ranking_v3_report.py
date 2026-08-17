"""Strict immutable train evidence for five-day ranking V3."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Mapping

from stock_ai.market_codes import normalize_code6

from .five_day_ranking_v3 import (
    V3_POLICY_IDS,
    V3_RANKING_VERSION,
    V3_SELECTION_MODES,
    V3_TRAIN_SCHEMA,
    V3_VALIDATION_SCHEMA,
    FiveDayRankingV3TrainReview,
    FiveDayRankingV3ValidationReview,
    build_five_day_v3_policies,
    five_day_v3_policy_hash,
    five_day_v3_policy_set_hash,
    five_day_v3_selection_fingerprint,
    v3_validation_trial_identity,
)
from .five_day_ranking_v3_evidence import (
    V3BucketKey,
    V3BucketStats,
    V3EvidenceWindows,
)
from .five_day_ranking_v3_features import (
    V3_FEATURE_NAMES,
    V3FeatureEffect,
    V3FeatureModel,
)
from .models import SetupType
from .validation import ChronologicalSplit


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
                value.items(),
                key=lambda pair: str(pair[0]),
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


def _bucket_key_content(value: V3BucketKey) -> dict[str, object]:
    return {
        "level": value.level,
        "profile_id": value.profile_id,
        "setup_type": value.setup_type.value if value.setup_type else None,
        "market_status": value.market_status,
        "sector_resonating": value.sector_resonating,
    }


def _bucket_stats_content(value: V3BucketStats) -> dict[str, object]:
    return {
        "key": _bucket_key_content(value.key),
        "data_end": value.data_end.isoformat(),
        "total_plans": value.total_plans,
        "resolved_samples": value.resolved_samples,
        "net_expectancy": str(value.net_expectancy),
        "profit_factor": (
            str(value.profit_factor)
            if value.profit_factor is not None
            else None
        ),
        "profitable_interval": [
            str(item) for item in value.profitable_interval
        ],
        "positive_window_ratio": str(value.positive_window_ratio),
        "mae_p75": str(value.mae_p75),
        "stop_rate": str(value.stop_rate),
    }


def _evidence_windows_content(
    value: V3EvidenceWindows,
) -> dict[str, object]:
    return {
        "full_dates": [item.isoformat() for item in value.full_dates],
        "recent_dates": [item.isoformat() for item in value.recent_dates],
        "full": [
            _bucket_stats_content(item)
            for _, item in sorted(
                value.full.items(),
                key=lambda pair: str(pair[0]),
            )
        ],
        "recent": [
            _bucket_stats_content(item)
            for _, item in sorted(
                value.recent.items(),
                key=lambda pair: str(pair[0]),
            )
        ],
    }


def _feature_model_content(value: V3FeatureModel) -> dict[str, object]:
    return {
        "data_end": value.data_end.isoformat(),
        "boundaries": {
            name: [str(item) for item in value.boundaries[name]]
            for name in V3_FEATURE_NAMES
        },
        "effects": [
            {
                "profile_id": key[0],
                "setup_type": key[1],
                "feature_name": key[2],
                "bin_name": key[3],
                "full_samples": effect.full_samples,
                "recent_samples": effect.recent_samples,
                "full_delta": str(effect.full_delta),
                "recent_delta": str(effect.recent_delta),
            }
            for key, effect in sorted(value.effects.items())
        ],
    }


def _candidate_evidence_content(value) -> dict[str, object]:
    return {
        "full_edge": str(value.full_edge),
        "recent_edge": str(value.recent_edge),
        "edge": str(value.edge),
        "stop_rate": str(value.stop_rate),
        "mae_p75": str(value.mae_p75),
        "deepest_full_key": _bucket_key_content(value.deepest_full_key),
        "deepest_recent_key": _bucket_key_content(value.deepest_recent_key),
        "stable_negative": value.stable_negative,
        "full_trace": [
            _bucket_stats_content(item) for item in value.full_trace
        ],
        "recent_trace": [
            _bucket_stats_content(item) for item in value.recent_trace
        ],
    }


def _scored_content(value) -> dict[str, object]:
    return {
        "plan_key": _plan_key(value.plan),
        "evidence": _candidate_evidence_content(value.evidence),
        "feature_adjustment": {
            "effects": {
                key: str(item)
                for key, item in sorted(
                    value.feature_adjustment.effects.items()
                )
            },
            "total": str(value.feature_adjustment.total),
        },
        "consistency": str(value.consistency),
        "downside": str(value.downside),
        "score": str(value.score),
        "rank": value.rank,
        "selected": value.selected,
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
            _plan_key(item.plan) for item in selection.admitted
        ],
        "rejection_counts": dict(
            sorted(selection.ranking.rejection_counts.items())
        ),
        "funnel_counts": dict(sorted(selection.funnel_counts.items())),
        "incomplete": selection.incomplete,
    }


def _variant_content(value) -> dict[str, object]:
    return {
        "fold_id": value.fold_id,
        "policy_id": value.policy_id,
        "selection_mode": value.selection_mode,
        "scored": [_scored_content(item) for item in value.scored],
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


def _train_content(
    review: FiveDayRankingV3TrainReview,
) -> dict[str, object]:
    fold_order = {
        "train-fold-1": 0,
        "train-fold-2": 1,
        "train-combined": 2,
    }
    variants = sorted(
        review.variants,
        key=lambda value: (
            V3_POLICY_IDS.index(value.policy_id),
            V3_SELECTION_MODES.index(value.selection_mode),
            fold_order[value.fold_id],
        ),
    )
    assessments = sorted(
        review.assessments,
        key=lambda value: V3_POLICY_IDS.index(value.policy.policy_id),
    )
    fingerprints = sorted(
        review.policy_fingerprints,
        key=lambda value: V3_POLICY_IDS.index(value.policy_id),
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
        "policies": [
            {
                "definition": _primitive(policy),
                "policy_hash": five_day_v3_policy_hash(policy),
            }
            for policy in review.policies
        ],
        "folds": _primitive(review.folds),
        "variants": [_variant_content(value) for value in variants],
        "assessments": [
            _assessment_content(value) for value in assessments
        ],
        "policy_fingerprints": [
            {
                "policy_id": value.policy_id,
                "selected_structure_keys": list(
                    value.selected_structure_keys
                ),
                "fingerprint": value.fingerprint,
            }
            for value in fingerprints
        ],
        "fingerprint_groups": _primitive(review.fingerprint_groups),
        "validation_evidence_windows": _evidence_windows_content(
            review.validation_evidence_windows
        ),
        "validation_feature_model": _feature_model_content(
            review.validation_feature_model
        ),
        "validation_excluded_unresolved_train_rows": (
            review.validation_excluded_unresolved_train_rows
        ),
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


def _registered_policies_content() -> list[dict[str, object]]:
    return [
        {
            "definition": _primitive(policy),
            "policy_hash": five_day_v3_policy_hash(policy),
        }
        for policy in build_five_day_v3_policies()
    ]


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


def _variant_registry_is_valid(variants: object) -> bool:
    if not isinstance(variants, list):
        return False
    expected = [
        (fold_id, policy_id, mode)
        for policy_id in V3_POLICY_IDS
        for mode in V3_SELECTION_MODES
        for fold_id in (
            "train-fold-1",
            "train-fold-2",
            "train-combined",
        )
    ]
    try:
        actual = [
            (
                str(value["fold_id"]),
                str(value["policy_id"]),
                str(value["selection_mode"]),
            )
            for value in variants
        ]
    except (KeyError, TypeError):
        return False
    return actual == expected


def _fingerprints_are_valid(content: Mapping[str, object]) -> bool:
    values = content["policy_fingerprints"]
    groups = content["fingerprint_groups"]
    if not isinstance(values, list) or len(values) != 8:
        return False
    try:
        if tuple(str(value["policy_id"]) for value in values) != V3_POLICY_IDS:
            return False
        if any(
            str(value["fingerprint"])
            != five_day_v3_selection_fingerprint(
                tuple(str(item) for item in value["selected_structure_keys"])
            )
            for value in values
        ):
            return False
        grouped: dict[str, list[str]] = {}
        for value in values:
            grouped.setdefault(str(value["fingerprint"]), []).append(
                str(value["policy_id"])
            )
        expected_groups = [
            {
                "fingerprint": fingerprint,
                "policy_ids": policy_ids,
            }
            for fingerprint, policy_ids in sorted(grouped.items())
            if len(policy_ids) > 1
        ]
        return groups == expected_groups
    except (KeyError, TypeError):
        return False


def _assessments_are_consistent(content: Mapping[str, object]) -> bool:
    assessments = content["assessments"]
    variants = content["variants"]
    if not isinstance(assessments, list) or len(assessments) != 8:
        return False
    try:
        if tuple(
            str(value["policy_id"]) for value in assessments
        ) != V3_POLICY_IDS:
            return False
        formal = {
            (str(value["policy_id"]), str(value["fold_id"])): value["segment"]
            for value in variants
            if value["selection_mode"] == "FORMAL"
        }
        return all(
            assessment[segment_name] == formal[(policy_id, fold_id)]
            for assessment in assessments
            for policy_id in (str(assessment["policy_id"]),)
            for segment_name, fold_id in (
                ("fold1", "train-fold-1"),
                ("fold2", "train-fold-2"),
                ("combined", "train-combined"),
            )
        )
    except (KeyError, TypeError):
        return False


def _winner_semantics_are_valid(content: Mapping[str, object]) -> bool:
    assessments = content["assessments"]
    fingerprints = content["policy_fingerprints"]
    if not isinstance(assessments, list) or not isinstance(fingerprints, list):
        return False
    try:
        distinct = len(
            {str(value["fingerprint"]) for value in fingerprints}
        )
        qualified = [
            value for value in assessments if value["qualifies"] is True
        ]
        winner_id = content["winner_policy_id"]
        if content["status"] == "POLICY_SET_DEGENERATE":
            return (
                distinct < 4
                and winner_id is None
                and content["winner_policy_hash"] is None
                and int(content["winner_train_samples"]) == 0
                and content["validation_eligible"] is False
                and not qualified
                and all(
                    "POLICY_SET_DEGENERATE" in value["reasons"]
                    for value in assessments
                )
            )
        if distinct < 4:
            return False
        if not qualified:
            return (
                content["status"] == "NO_TRAIN_CANDIDATE"
                and winner_id is None
                and content["winner_policy_hash"] is None
                and int(content["winner_train_samples"]) == 0
                and content["validation_eligible"] is False
            )
        winner = min(
            qualified,
            key=lambda value: (
                -Decimal(str(value["worst_fold_expectancy"])),
                -Decimal(
                    str(value["combined"]["metrics"]["net_expectancy"])
                ),
                -int(
                    value["combined"]["metrics"]["triggered_resolved"]
                ),
                Decimal(
                    str(value["combined"]["metrics"]["maximum_drawdown"])
                ),
                V3_POLICY_IDS.index(str(value["policy_id"])),
            ),
        )
        policy = build_five_day_v3_policies()[
            V3_POLICY_IDS.index(str(winner["policy_id"]))
        ]
        return (
            content["status"] == "TRAIN_CANDIDATE_SELECTED"
            and winner_id == policy.policy_id
            and content["winner_policy_hash"]
            == five_day_v3_policy_hash(policy)
            and int(content["winner_train_samples"])
            == int(winner["combined"]["metrics"]["triggered_resolved"])
            and content["validation_eligible"] is True
        )
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return False


def _frozen_models_are_valid(content: Mapping[str, object]) -> bool:
    try:
        split = content["split"]
        train_dates = list(split["train"])
        windows = content["validation_evidence_windows"]
        model = content["validation_feature_model"]
        return (
            len(train_dates) == 378
            and windows["full_dates"] == train_dates
            and windows["recent_dates"] == train_dates[-126:]
            and _bucket_stats_values_are_valid(
                windows["full"],
                data_end=str(train_dates[-1]),
            )
            and _bucket_stats_values_are_valid(
                windows["recent"],
                data_end=str(train_dates[-1]),
            )
            and model["data_end"] == train_dates[-1]
            and set(model["boundaries"]) == set(V3_FEATURE_NAMES)
            and len(model["boundaries"]) == len(V3_FEATURE_NAMES)
            and _feature_boundaries_are_valid(model["boundaries"])
            and _feature_effects_are_valid(model["effects"])
        )
    except (KeyError, TypeError, ValueError, InvalidOperation, IndexError):
        return False


def _finite_decimal(value: object) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError
    return result


def _bucket_stats_values_are_valid(
    values: object,
    *,
    data_end: str,
) -> bool:
    if not isinstance(values, list):
        return False
    keys: set[tuple[object, ...]] = set()
    levels = {"PROFILE", "SETUP", "MARKET", "SECTOR"}
    setup_types = {value.value for value in SetupType}
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get("key"), dict):
            return False
        key = value["key"]
        identity = (
            key.get("level"),
            key.get("profile_id"),
            key.get("setup_type"),
            key.get("market_status"),
            key.get("sector_resonating"),
        )
        if identity in keys:
            return False
        keys.add(identity)
        level = key.get("level")
        setup_type = key.get("setup_type")
        total = value.get("total_plans")
        resolved = value.get("resolved_samples")
        interval = value.get("profitable_interval")
        if (
            level not in levels
            or not key.get("profile_id")
            or (setup_type is not None and setup_type not in setup_types)
            or type(total) is not int
            or type(resolved) is not int
            or resolved < 0
            or total < resolved
            or value.get("data_end") != data_end
            or not isinstance(interval, list)
            or len(interval) != 2
        ):
            return False
        net = _finite_decimal(value.get("net_expectancy"))
        lower = _finite_decimal(interval[0])
        upper = _finite_decimal(interval[1])
        positive_windows = _finite_decimal(value.get("positive_window_ratio"))
        mae = _finite_decimal(value.get("mae_p75"))
        stop_rate = _finite_decimal(value.get("stop_rate"))
        profit_factor = value.get("profit_factor")
        if profit_factor is not None and _finite_decimal(profit_factor) < 0:
            return False
        if (
            not net.is_finite()
            or not Decimal("0") <= lower <= upper <= Decimal("1")
            or not Decimal("0") <= positive_windows <= Decimal("1")
            or mae < 0
            or not Decimal("0") <= stop_rate <= Decimal("1")
        ):
            return False
    return True


def _feature_boundaries_are_valid(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    for boundaries in value.values():
        if not isinstance(boundaries, list) or len(boundaries) not in (0, 4):
            return False
        decimals = tuple(_finite_decimal(item) for item in boundaries)
        if any(left > right for left, right in zip(decimals, decimals[1:])):
            return False
    return True


def _feature_effects_are_valid(value: object) -> bool:
    if not isinstance(value, list):
        return False
    identities: set[tuple[str, str, str, str]] = set()
    setup_types = {item.value for item in SetupType}
    for effect in value:
        if not isinstance(effect, dict):
            return False
        identity = (
            str(effect.get("profile_id")),
            str(effect.get("setup_type")),
            str(effect.get("feature_name")),
            str(effect.get("bin_name")),
        )
        full_samples = effect.get("full_samples")
        recent_samples = effect.get("recent_samples")
        if (
            identity in identities
            or not identity[0]
            or identity[1] not in setup_types
            or identity[2] not in V3_FEATURE_NAMES
            or not (identity[3].startswith("Q") or identity[3] == "MISSING")
            or type(full_samples) is not int
            or type(recent_samples) is not int
            or recent_samples < 0
            or full_samples < recent_samples
        ):
            return False
        identities.add(identity)
        _finite_decimal(effect.get("full_delta"))
        _finite_decimal(effect.get("recent_delta"))
    return True


def _train_content_is_valid(content: Mapping[str, object]) -> bool:
    forbidden = {"observations", "selected_observations"}
    parent_identity = str(content.get("parent_research_identity", ""))
    return (
        content.get("schema") == V3_TRAIN_SCHEMA
        and content.get("ranking_version") == V3_RANKING_VERSION
        and content.get("policy_set_hash") == five_day_v3_policy_set_hash()
        and content.get("policies") == _registered_policies_content()
        and _variant_registry_is_valid(content.get("variants"))
        and _assessments_are_consistent(content)
        and _fingerprints_are_valid(content)
        and _winner_semantics_are_valid(content)
        and _frozen_models_are_valid(content)
        and content.get("validation_outcomes_read") is False
        and content.get("test_outcomes_read") is False
        and content.get("promotion_eligible") is False
        and content.get("trade_permission") == "NO-TRADE"
        and not forbidden.intersection(_nested_keys(content))
        and len(parent_identity) == 64
        and all(value in "0123456789abcdef" for value in parent_identity)
    )


def five_day_ranking_v3_train_payload(
    review: FiveDayRankingV3TrainReview,
) -> dict[str, object]:
    """Return canonical aggregate-only V3 train evidence."""
    content = _train_content(review)
    if not _train_content_is_valid(content):
        raise ValueError("ranking v3 train artifact safety mismatch")
    return {**content, "artifact_identity": _sha256(content)}


def _write_exclusive_or_verify(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("immutable ranking v3 artifact conflict") from None


def write_five_day_ranking_v3_train(
    review: FiveDayRankingV3TrainReview,
    output_dir: str | Path,
) -> Path:
    """Write once by content identity, or verify identical prior bytes."""
    payload = five_day_ranking_v3_train_payload(review)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (
        f"ranking-v3-train-{payload['artifact_identity']}.json"
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    _write_exclusive_or_verify(path, serialized)
    return path


@dataclass(frozen=True)
class FiveDayRankingV3TrainArtifact:
    artifact_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    split: ChronologicalSplit
    policy_set_hash: str
    winner_policy_id: str | None
    winner_policy_hash: str | None
    winner_train_samples: int
    validation_eligible: bool
    validation_evidence_windows: V3EvidenceWindows
    validation_feature_model: V3FeatureModel
    payload: Mapping[str, object]


def _bucket_key_from_content(value: Mapping[str, object]) -> V3BucketKey:
    setup_type = value["setup_type"]
    return V3BucketKey(
        level=str(value["level"]),
        profile_id=str(value["profile_id"]),
        setup_type=(SetupType(str(setup_type)) if setup_type else None),
        market_status=(
            str(value["market_status"])
            if value["market_status"] is not None
            else None
        ),
        sector_resonating=(
            bool(value["sector_resonating"])
            if value["sector_resonating"] is not None
            else None
        ),
    )


def _bucket_stats_from_content(
    value: Mapping[str, object],
) -> V3BucketStats:
    key = _bucket_key_from_content(value["key"])
    interval = value["profitable_interval"]
    return V3BucketStats(
        key=key,
        data_end=date.fromisoformat(str(value["data_end"])),
        total_plans=int(value["total_plans"]),
        resolved_samples=int(value["resolved_samples"]),
        net_expectancy=Decimal(str(value["net_expectancy"])),
        profit_factor=(
            Decimal(str(value["profit_factor"]))
            if value["profit_factor"] is not None
            else None
        ),
        profitable_interval=(
            Decimal(str(interval[0])),
            Decimal(str(interval[1])),
        ),
        positive_window_ratio=Decimal(
            str(value["positive_window_ratio"])
        ),
        mae_p75=Decimal(str(value["mae_p75"])),
        stop_rate=Decimal(str(value["stop_rate"])),
    )


def _evidence_windows_from_content(
    value: Mapping[str, object],
) -> V3EvidenceWindows:
    full_values = tuple(
        _bucket_stats_from_content(item) for item in value["full"]
    )
    recent_values = tuple(
        _bucket_stats_from_content(item) for item in value["recent"]
    )
    return V3EvidenceWindows(
        full_dates=tuple(
            date.fromisoformat(str(item)) for item in value["full_dates"]
        ),
        recent_dates=tuple(
            date.fromisoformat(str(item)) for item in value["recent_dates"]
        ),
        full={item.key: item for item in full_values},
        recent={item.key: item for item in recent_values},
    )


def _feature_model_from_content(
    value: Mapping[str, object],
) -> V3FeatureModel:
    effects: dict[tuple[str, str, str, str], V3FeatureEffect] = {}
    for item in value["effects"]:
        key = (
            str(item["profile_id"]),
            str(item["setup_type"]),
            str(item["feature_name"]),
            str(item["bin_name"]),
        )
        effects[key] = V3FeatureEffect(
            full_samples=int(item["full_samples"]),
            recent_samples=int(item["recent_samples"]),
            full_delta=Decimal(str(item["full_delta"])),
            recent_delta=Decimal(str(item["recent_delta"])),
        )
    return V3FeatureModel(
        data_end=date.fromisoformat(str(value["data_end"])),
        boundaries={
            str(name): tuple(Decimal(str(item)) for item in boundaries)
            for name, boundaries in value["boundaries"].items()
        },
        effects=effects,
    )


def _split_from_content(value: Mapping[str, object]) -> ChronologicalSplit:
    return ChronologicalSplit(
        train=tuple(date.fromisoformat(str(item)) for item in value["train"]),
        validation=tuple(
            date.fromisoformat(str(item)) for item in value["validation"]
        ),
        test=tuple(date.fromisoformat(str(item)) for item in value["test"]),
    )


def load_five_day_ranking_v3_train(
    path: str | Path,
    *,
    expected_parent_research_identity: str | None = None,
) -> FiveDayRankingV3TrainArtifact:
    """Load only canonical, current-registry, aggregate V3 train evidence."""
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
        parent_identity = str(payload["parent_research_identity"])
        if (
            len(identity) != 64
            or any(value not in "0123456789abcdef" for value in identity)
            or identity != _sha256(content)
            or target.name != f"ranking-v3-train-{identity}.json"
            or not _train_content_is_valid(content)
            or (
                expected_parent_research_identity is not None
                and parent_identity != expected_parent_research_identity
            )
        ):
            raise ValueError
        split = _split_from_content(payload["split"])
        windows = _evidence_windows_from_content(
            payload["validation_evidence_windows"]
        )
        feature_model = _feature_model_from_content(
            payload["validation_feature_model"]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
        IndexError,
        OSError,
        json.JSONDecodeError,
    ):
        raise ValueError("invalid ranking v3 train artifact") from None
    return FiveDayRankingV3TrainArtifact(
        artifact_identity=identity,
        parent_research_identity=parent_identity,
        parent_input_fingerprint=str(payload["parent_input_fingerprint"]),
        split=split,
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
        validation_evidence_windows=windows,
        validation_feature_model=feature_model,
        payload=payload,
    )


def _v3_validation_content(
    review: FiveDayRankingV3ValidationReview,
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


def _is_sha256(value: object) -> bool:
    text = str(value)
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def _validation_segment_is_consistent(segment: object) -> bool:
    if not isinstance(segment, dict):
        return False
    try:
        metrics = segment["metrics"]
        portfolio = segment["portfolio"]
        admitted = segment["admitted_trade_keys"]
        selected = segment["selected_plan_keys"]
        ranked = segment["ranked_plan_keys"]
        funnel = segment["funnel_counts"]
        metric_reasons = metrics["reasons"]
        portfolio_reasons = portfolio["reasons"]
        return (
            segment["metric_version"] == "selected-portfolio-v2"
            and metrics["profile_id"] == "GLOBAL"
            and metrics["segment"] == "validation"
            and isinstance(admitted, list)
            and isinstance(selected, list)
            and isinstance(ranked, list)
            and isinstance(funnel, dict)
            and int(metrics["triggered_resolved"]) == len(admitted)
            and int(portfolio["accepted_trades"]) == len(admitted)
            and int(funnel["SELECTED_PLANS"]) == len(selected)
            and int(funnel["ADMITTED_TRADES"]) == len(admitted)
            and metrics["qualifies"] is (not metric_reasons)
            and portfolio["qualifies"] is (not portfolio_reasons)
            and type(segment["incomplete"]) is bool
            and segment["incomplete"]
            is ("SELECTION_INCOMPLETE" in metric_reasons)
        )
    except (KeyError, TypeError, ValueError):
        return False


def _validation_content_is_safe(content: Mapping[str, object]) -> bool:
    try:
        policy = next(
            (
                value
                for value in build_five_day_v3_policies()
                if value.policy_id == content["winner_policy_id"]
            ),
            None,
        )
        segment = content["segment"]
        dates = [
            date.fromisoformat(str(value))
            for value in content["validation_dates"]
        ]
        reasons = list(content["reasons"])
        expected_reasons = list(
            dict.fromkeys(
                (
                    *segment["metrics"]["reasons"],
                    *segment["portfolio"]["reasons"],
                )
            )
        )
        return (
            content["schema"] == V3_VALIDATION_SCHEMA
            and policy is not None
            and content["winner_policy_hash"]
            == five_day_v3_policy_hash(policy)
            and content["trial_identity"]
            == v3_validation_trial_identity(
                str(content["parent_train_identity"]),
                str(content["winner_policy_hash"]),
            )
            and _is_sha256(content["parent_train_identity"])
            and _is_sha256(content["parent_research_identity"])
            and _is_sha256(content["parent_input_fingerprint"])
            and len(dates) == 126
            and dates == sorted(set(dates))
            and _validation_segment_is_consistent(segment)
            and reasons == expected_reasons
            and content["qualifies_for_test_design"] is (not reasons)
            and content["validation_outcomes_read"] is True
            and content["test_outcomes_read"] is False
            and content["promotion_eligible"] is False
            and content["trade_permission"] == "NO-TRADE"
            and not {"observations", "selected_observations"}.intersection(
                _nested_keys(content)
            )
        )
    except (KeyError, TypeError, ValueError):
        return False


def write_five_day_ranking_v3_validation(
    review: FiveDayRankingV3ValidationReview,
    output_dir: str | Path,
) -> Path:
    """Write one immutable validation result for the frozen V3 winner."""
    content = _v3_validation_content(review)
    if not _validation_content_is_safe(content):
        raise ValueError("ranking v3 validation artifact safety mismatch")
    payload = {**content, "artifact_identity": _sha256(content)}
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (
        f"ranking-v3-validation-{review.trial_identity}.json"
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    _write_exclusive_or_verify(path, serialized)
    return path


def load_five_day_ranking_v3_validation(
    path: str | Path,
    *,
    expected_train_identity: str,
    expected_policy_hash: str,
) -> Mapping[str, object]:
    """Load validation only under its exact frozen train winner."""
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
        expected_trial = v3_validation_trial_identity(
            expected_train_identity,
            expected_policy_hash,
        )
        if (
            not _is_sha256(artifact_identity)
            or artifact_identity != _sha256(content)
            or payload["trial_identity"] != expected_trial
            or target.name
            != f"ranking-v3-validation-{expected_trial}.json"
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
        OSError,
        json.JSONDecodeError,
    ):
        raise ValueError("invalid ranking v3 validation artifact") from None
    return payload
