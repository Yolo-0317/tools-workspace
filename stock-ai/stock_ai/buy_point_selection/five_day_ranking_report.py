"""Immutable artifacts for five-day ranking diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Mapping

from .five_day_ranking_research import (
    REGISTERED_VALIDATION_POLICY,
    FiveDayRankingTrainReview,
    RankingPolicy,
)
from .five_day_return_profiles import build_five_day_return_profiles
from .five_day_return_runtime import FiveDayResearchReview
from .five_day_return_validation import (
    SELECTED_PORTFOLIO_METRIC_VERSION,
    FiveDayPortfolioMetrics,
    FiveDaySegmentMetrics,
    FiveDaySelectedSegment,
    _is_resolved,
    build_five_day_calibrations,
    evaluate_five_day_selection_segment,
    select_five_day_portfolio,
)
from .validation import ChronologicalSplit


RANKING_VALIDATION_SCHEMA = "five-day-ranking-validation-v1"
RANKING_REPORT_VERSION = "five-day-ranking-report-v1"


@dataclass(frozen=True)
class FiveDayRankingTrainArtifact:
    artifact_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    split: ChronologicalSplit
    registered_validation_policy: RankingPolicy
    registered_validation_policy_hash: str
    payload: Mapping[str, object]


@dataclass(frozen=True)
class FiveDayRankingValidationReview:
    schema: str
    parent_train_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    registered_validation_policy: RankingPolicy
    registered_validation_policy_hash: str
    validation_dates: tuple[date, ...]
    profile_segments: tuple[FiveDaySelectedSegment, ...]
    global_segment: FiveDaySelectedSegment
    validation_outcomes_read: bool
    test_outcomes_read: bool


@dataclass(frozen=True)
class FiveDayRankingValidationArtifact:
    artifact_identity: str
    content_revision: str
    parent_train_identity: str
    parent_research_identity: str
    registered_validation_policy_hash: str
    validation_outcomes_read: bool
    test_outcomes_read: bool
    payload: Mapping[str, object]


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _split_payload(value: ChronologicalSplit) -> dict[str, object]:
    return {
        "train": [item.isoformat() for item in value.train],
        "validation": [item.isoformat() for item in value.validation],
        "test": [item.isoformat() for item in value.test],
    }


def _split_from_payload(value: Mapping[str, object]) -> ChronologicalSplit:
    return ChronologicalSplit(
        train=tuple(date.fromisoformat(str(item)) for item in value["train"]),
        validation=tuple(
            date.fromisoformat(str(item)) for item in value["validation"]
        ),
        test=tuple(date.fromisoformat(str(item)) for item in value["test"]),
    )


def _policy_payload(value: RankingPolicy) -> dict[str, object]:
    return {
        "ranking_key_version": value.ranking_key_version,
        "daily_limit": value.daily_limit,
        "capacity": value.capacity,
        "metric_version": value.metric_version,
    }


def _policy_from_payload(value: Mapping[str, object]) -> RankingPolicy:
    return RankingPolicy(
        ranking_key_version=str(value["ranking_key_version"]),
        daily_limit=int(value["daily_limit"]),
        capacity=int(value["capacity"]),
        metric_version=str(value["metric_version"]),
    )


def _metric_payload(value: FiveDaySegmentMetrics) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "segment": value.segment,
        "triggered_resolved": value.triggered_resolved,
        "net_expectancy": str(value.net_expectancy),
        "profit_factor": (
            None if value.profit_factor is None else str(value.profit_factor)
        ),
        "profitable_wilson_lower": str(value.profitable_wilson_lower),
        "stop_rate": str(value.stop_rate),
        "positive_window_ratio": str(value.positive_window_ratio),
        "maximum_drawdown": str(value.maximum_drawdown),
        "qualifies": value.qualifies,
        "reasons": list(value.reasons),
    }


def _portfolio_payload(value: FiveDayPortfolioMetrics) -> dict[str, object]:
    return {
        "accepted_trades": value.accepted_trades,
        "maximum_drawdown": str(value.maximum_drawdown),
        "maximum_stock_trade_share": str(value.maximum_stock_trade_share),
        "maximum_stock_profit_share": str(value.maximum_stock_profit_share),
        "maximum_sector_trade_share": str(value.maximum_sector_trade_share),
        "maximum_sector_profit_share": str(value.maximum_sector_profit_share),
        "top5_profit_share": str(value.top5_profit_share),
        "qualifies": value.qualifies,
        "reasons": list(value.reasons),
    }


def _plan_key_payload(value) -> dict[str, object]:
    return {
        "signal_date": value.candidate.signal_date.isoformat(),
        "code": value.candidate.code,
        "structure_id": value.structure_id,
        "profile_id": value.profile.profile_id,
    }


def _variant_payload(value) -> dict[str, object]:
    selection = value.segment.selection
    return {
        "fold_id": value.fold_id,
        "scope": value.scope,
        "daily_limit": value.daily_limit,
        "metric_version": value.segment.metric_version,
        "metrics": _metric_payload(value.segment.metrics),
        "portfolio": _portfolio_payload(value.segment.portfolio),
        "ranked_plan_keys": [
            {
                **_plan_key_payload(row.plan),
                "rank": row.rank,
                "selected": row.selected,
            }
            for row in selection.ranking.ranked
        ],
        "selected_plan_keys": [
            _plan_key_payload(plan) for plan in selection.ranking.plans
        ],
        "admitted_trade_keys": [
            _plan_key_payload(item.plan) for item in selection.admitted
        ],
        "rejection_counts": dict(
            sorted(selection.ranking.rejection_counts.items())
        ),
        "funnel_counts": dict(sorted(selection.funnel_counts.items())),
        "incomplete": selection.incomplete,
    }


def _attribution_payload(value) -> dict[str, object]:
    return {
        "fold_id": value.fold_id,
        "scope": value.scope,
        "dimension": value.dimension,
        "bucket": value.bucket,
        "selected_plans": value.selected_plans,
        "admitted_trades": value.admitted_trades,
        "resolved_observations": value.resolved_observations,
        "win_count": value.win_count,
        "loss_count": value.loss_count,
        "stop_count": value.stop_count,
        "gross_pnl": str(value.gross_pnl),
        "net_pnl": str(value.net_pnl),
        "cost_drag": str(value.cost_drag),
        "net_expectancy": str(value.net_expectancy),
    }


def _train_content(review: FiveDayRankingTrainReview) -> dict[str, object]:
    policy = _policy_payload(review.registered_validation_policy)
    policy_hash = _sha256(policy)
    selection_policy_hash = _sha256(
        {
            "ranking_key_version": policy["ranking_key_version"],
            "daily_limits": list(review.daily_limits),
            "capacity": policy["capacity"],
            "no_backfill": True,
            "metric_version": SELECTED_PORTFOLIO_METRIC_VERSION,
        }
    )
    variants = tuple(
        sorted(
            review.variants,
            key=lambda item: (item.fold_id, item.scope, item.daily_limit),
        )
    )
    attribution = tuple(
        sorted(
            review.attribution,
            key=lambda item: (
                item.fold_id,
                item.scope,
                item.dimension,
                item.bucket,
            ),
        )
    )
    return {
        "schema": review.schema,
        "stage": "diagnose-train",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": True,
        "promotion_eligible": False,
        "report_version": RANKING_REPORT_VERSION,
        "metric_version": SELECTED_PORTFOLIO_METRIC_VERSION,
        "parent_research_identity": review.parent_research_identity,
        "parent_input_fingerprint": review.parent_input_fingerprint,
        "split": _split_payload(review.split),
        "formal_rule_version": review.formal_rule_version,
        "formal_policy_hash": review.formal_policy_hash,
        "profile_matrix_hash": review.profile_matrix_hash,
        "sizing_version": review.sizing_version,
        "evaluator_version": review.evaluator_version,
        "cost_version": review.cost_version,
        "selection_policy_hash": selection_policy_hash,
        "registered_validation_policy": policy,
        "registered_validation_policy_hash": policy_hash,
        "daily_limits": list(review.daily_limits),
        "folds": [
            {
                "fold_id": item.fold_id,
                "calibration_dates": [
                    value.isoformat() for value in item.calibration_dates
                ],
                "evaluation_dates": [
                    value.isoformat() for value in item.evaluation_dates
                ],
                "calibration_data_end": item.calibration_data_end.isoformat(),
                "excluded_unresolved_calibration_rows": (
                    item.excluded_unresolved_calibration_rows
                ),
            }
            for item in review.folds
        ],
        "variants": [_variant_payload(item) for item in variants],
        "attribution": [_attribution_payload(item) for item in attribution],
        "quintile_boundaries": {
            fold_id: {
                dimension: [str(value) for value in boundaries]
                for dimension, boundaries in sorted(dimensions.items())
            }
            for fold_id, dimensions in sorted(
                review.quintile_boundaries.items()
            )
        },
        "fold_stability": dict(sorted(review.fold_stability.items())),
        "validation_outcomes_read": review.validation_outcomes_read,
        "test_outcomes_read": review.test_outcomes_read,
    }


def five_day_ranking_train_payload(
    review: FiveDayRankingTrainReview,
) -> dict[str, object]:
    content = _train_content(review)
    if (
        content["validation_outcomes_read"] is not False
        or content["test_outcomes_read"] is not False
        or content["metric_version"] != SELECTED_PORTFOLIO_METRIC_VERSION
        or any(
            item["metrics"]["qualifies"] is not False
            or item["portfolio"]["qualifies"] is not False
            for item in content["variants"]
        )
    ):
        raise ValueError("ranking train artifact safety mismatch")
    return {**content, "artifact_identity": _sha256(content)}


def _write_exclusive_or_verify(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("immutable ranking artifact content mismatch")


def write_five_day_ranking_train(
    review: FiveDayRankingTrainReview,
    output_dir: str | Path,
) -> Path:
    payload = five_day_ranking_train_payload(review)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"ranking-train-{payload['artifact_identity']}.json"
    content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    _write_exclusive_or_verify(path, content)
    return path


def load_five_day_ranking_train(
    path: str | Path,
) -> FiveDayRankingTrainArtifact:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        identity = str(payload["artifact_identity"])
        content = {
            key: value
            for key, value in payload.items()
            if key != "artifact_identity"
        }
        if (
            payload["schema"] != "five-day-ranking-train-v1"
            or payload["stage"] != "diagnose-train"
            or payload["status"] != "CASE_ANALYSIS_ONLY"
            or payload["trade_permission"] != "NO-TRADE"
            or payload["retrospective"] is not True
            or payload["promotion_eligible"] is not False
            or payload["metric_version"] != SELECTED_PORTFOLIO_METRIC_VERSION
            or payload["validation_outcomes_read"] is not False
            or payload["test_outcomes_read"] is not False
            or any(
                item["metrics"]["qualifies"] is not False
                or item["portfolio"]["qualifies"] is not False
                for item in payload["variants"]
            )
            or _sha256(content) != identity
        ):
            raise ValueError
        policy_payload = dict(payload["registered_validation_policy"])
        policy = _policy_from_payload(policy_payload)
        policy_hash = str(payload["registered_validation_policy_hash"])
        if _sha256(policy_payload) != policy_hash:
            raise ValueError
        return FiveDayRankingTrainArtifact(
            artifact_identity=identity,
            parent_research_identity=str(payload["parent_research_identity"]),
            parent_input_fingerprint=str(
                payload["parent_input_fingerprint"]
            ),
            split=_split_from_payload(dict(payload["split"])),
            registered_validation_policy=policy,
            registered_validation_policy_hash=policy_hash,
            payload=payload,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("five-day ranking train artifact is invalid") from None


def _prior_admitted_samples(
    train: FiveDayRankingTrainArtifact,
    profile_id: str,
) -> int:
    scope = f"profile:{profile_id}"
    matches = tuple(
        item
        for item in train.payload["variants"]
        if item["fold_id"] == "train-combined"
        and item["scope"] == scope
        and int(item["daily_limit"]) == 3
    )
    if len(matches) != 1:
        raise ValueError("train artifact lacks the combined Top-3 variant")
    return int(matches[0]["metrics"]["triggered_resolved"])


def _verify_validation_parents(
    research: FiveDayResearchReview,
    train: FiveDayRankingTrainArtifact,
) -> None:
    expected_policy_payload = _policy_payload(REGISTERED_VALIDATION_POLICY)
    train_payload_policy = dict(train.payload["registered_validation_policy"])
    if (
        train.registered_validation_policy != REGISTERED_VALIDATION_POLICY
        or train_payload_policy != expected_policy_payload
        or train.registered_validation_policy_hash
        != _sha256(expected_policy_payload)
    ):
        raise ValueError("registered validation policy mismatch")
    lineage = {
        "parent_input_fingerprint": research.input_fingerprint,
        "formal_rule_version": research.formal_rule_version,
        "formal_policy_hash": research.formal_policy_hash,
        "profile_matrix_hash": research.profile_matrix_hash,
        "sizing_version": research.sizing_version,
        "evaluator_version": research.evaluator_version,
        "cost_version": research.cost_version,
    }
    if (
        train.artifact_identity != train.payload["artifact_identity"]
        or train.parent_research_identity
        != train.payload["parent_research_identity"]
        or train.parent_input_fingerprint != research.input_fingerprint
        or train.split != research.split
        or any(train.payload[key] != value for key, value in lineage.items())
        or not research.point_in_time_complete
        or research.test_outcomes_read
    ):
        raise ValueError("ranking validation parent or lineage mismatch")


def build_five_day_ranking_validation_review(
    research: FiveDayResearchReview,
    train: FiveDayRankingTrainArtifact,
) -> FiveDayRankingValidationReview:
    """Evaluate the one preregistered Top-3 policy on validation only."""
    _verify_validation_parents(research, train)
    train_set = frozenset(research.split.train)
    validation_set = frozenset(research.split.validation)
    validation_start = research.split.validation[0]
    train_observations = tuple(
        value
        for value in research.observations
        if value.plan.candidate.signal_date in train_set
        and _is_resolved(value)
        and value.resolution_date < validation_start
    )
    calibrations = build_five_day_calibrations(
        train_observations,
        trading_dates=research.split.train,
    )
    validation_observations = tuple(
        value
        for value in research.observations
        if value.plan.candidate.signal_date in validation_set
    )
    policy = REGISTERED_VALIDATION_POLICY
    profile_segments: list[FiveDaySelectedSegment] = []
    for profile in build_five_day_return_profiles():
        profile_values = tuple(
            value
            for value in validation_observations
            if value.plan.profile.profile_id == profile.profile_id
            and (
                not _is_resolved(value)
                or value.resolution_date <= research.split.validation[-1]
            )
        )
        selection = select_five_day_portfolio(
            tuple(value.plan for value in profile_values),
            profile_values,
            calibrations,
            daily_limit=policy.daily_limit,
            capacity=policy.capacity,
        )
        prior_samples = _prior_admitted_samples(train, profile.profile_id)
        profile_segments.append(
            evaluate_five_day_selection_segment(
                profile_id=profile.profile_id,
                segment="validation",
                selection=selection,
                trading_dates=research.split.validation,
                cumulative_samples=prior_samples + len(selection.admitted),
                required_samples=30,
                required_cumulative_samples=70,
            )
        )
    qualified_ids = frozenset(
        value.metrics.profile_id
        for value in profile_segments
        if value.metrics.qualifies
    )
    global_values = tuple(
        value
        for value in validation_observations
        if value.plan.profile.profile_id in qualified_ids
        and (
            not _is_resolved(value)
            or value.resolution_date <= research.split.validation[-1]
        )
    )
    global_selection = select_five_day_portfolio(
        tuple(value.plan for value in global_values),
        global_values,
        calibrations,
        daily_limit=policy.daily_limit,
        capacity=policy.capacity,
    )
    global_segment = evaluate_five_day_selection_segment(
        profile_id="GLOBAL",
        segment="validation",
        selection=global_selection,
        trading_dates=research.split.validation,
        cumulative_samples=len(global_selection.admitted),
        required_samples=0,
        required_cumulative_samples=0,
    )
    return FiveDayRankingValidationReview(
        schema=RANKING_VALIDATION_SCHEMA,
        parent_train_identity=train.artifact_identity,
        parent_research_identity=train.parent_research_identity,
        parent_input_fingerprint=train.parent_input_fingerprint,
        registered_validation_policy=policy,
        registered_validation_policy_hash=(
            train.registered_validation_policy_hash
        ),
        validation_dates=tuple(research.split.validation),
        profile_segments=tuple(profile_segments),
        global_segment=global_segment,
        validation_outcomes_read=True,
        test_outcomes_read=False,
    )


def validation_trial_identity(train_identity: str, policy_hash: str) -> str:
    return _sha256(
        {
            "schema": RANKING_VALIDATION_SCHEMA,
            "parent_train_identity": train_identity,
            "registered_validation_policy_hash": policy_hash,
        }
    )


def _selection_segment_payload(value: FiveDaySelectedSegment) -> dict[str, object]:
    selection = value.selection
    return {
        "metric_version": value.metric_version,
        "metrics": _metric_payload(value.metrics),
        "portfolio": _portfolio_payload(value.portfolio),
        "selected_plan_keys": [
            _plan_key_payload(plan) for plan in selection.ranking.plans
        ],
        "admitted_trade_keys": [
            _plan_key_payload(item.plan) for item in selection.admitted
        ],
        "rejection_counts": dict(
            sorted(selection.ranking.rejection_counts.items())
        ),
        "funnel_counts": dict(sorted(selection.funnel_counts.items())),
        "incomplete": selection.incomplete,
    }


def _validation_content(
    review: FiveDayRankingValidationReview,
) -> dict[str, object]:
    return {
        "schema": review.schema,
        "stage": "validate-ranking",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": True,
        "promotion_eligible": False,
        "report_version": RANKING_REPORT_VERSION,
        "metric_version": SELECTED_PORTFOLIO_METRIC_VERSION,
        "parent_train_identity": review.parent_train_identity,
        "parent_research_identity": review.parent_research_identity,
        "parent_input_fingerprint": review.parent_input_fingerprint,
        "registered_validation_policy": _policy_payload(
            review.registered_validation_policy
        ),
        "registered_validation_policy_hash": (
            review.registered_validation_policy_hash
        ),
        "validation_dates": [
            value.isoformat() for value in review.validation_dates
        ],
        "profile_segments": [
            _selection_segment_payload(value)
            for value in review.profile_segments
        ],
        "global_segment": _selection_segment_payload(review.global_segment),
        "validation_outcomes_read": review.validation_outcomes_read,
        "test_outcomes_read": review.test_outcomes_read,
    }


def five_day_ranking_validation_payload(
    review: FiveDayRankingValidationReview,
) -> dict[str, object]:
    policy_payload = _policy_payload(review.registered_validation_policy)
    if (
        review.registered_validation_policy != REGISTERED_VALIDATION_POLICY
        or _sha256(policy_payload)
        != review.registered_validation_policy_hash
        or not review.validation_outcomes_read
        or review.test_outcomes_read
    ):
        raise ValueError("ranking validation safety or policy mismatch")
    content = _validation_content(review)
    identity = validation_trial_identity(
        review.parent_train_identity,
        review.registered_validation_policy_hash,
    )
    return {
        **content,
        "artifact_identity": identity,
        "content_revision": _sha256(content),
    }


def write_five_day_ranking_validation(
    review: FiveDayRankingValidationReview,
    output_dir: str | Path,
) -> Path:
    payload = five_day_ranking_validation_payload(review)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"ranking-validation-{payload['artifact_identity']}.json"
    content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    _write_exclusive_or_verify(path, content)
    return path


def load_five_day_ranking_validation(
    path: str | Path,
) -> FiveDayRankingValidationArtifact:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        identity = str(payload["artifact_identity"])
        revision = str(payload["content_revision"])
        content = {
            key: value
            for key, value in payload.items()
            if key not in {"artifact_identity", "content_revision"}
        }
        policy_payload = dict(payload["registered_validation_policy"])
        policy_hash = str(payload["registered_validation_policy_hash"])
        if (
            payload["schema"] != RANKING_VALIDATION_SCHEMA
            or payload["stage"] != "validate-ranking"
            or payload["status"] != "CASE_ANALYSIS_ONLY"
            or payload["trade_permission"] != "NO-TRADE"
            or payload["retrospective"] is not True
            or payload["promotion_eligible"] is not False
            or payload["metric_version"]
            != SELECTED_PORTFOLIO_METRIC_VERSION
            or payload["validation_outcomes_read"] is not True
            or payload["test_outcomes_read"] is not False
            or _policy_from_payload(policy_payload)
            != REGISTERED_VALIDATION_POLICY
            or _sha256(policy_payload) != policy_hash
            or validation_trial_identity(
                str(payload["parent_train_identity"]),
                policy_hash,
            )
            != identity
            or _sha256(content) != revision
        ):
            raise ValueError
        return FiveDayRankingValidationArtifact(
            artifact_identity=identity,
            content_revision=revision,
            parent_train_identity=str(payload["parent_train_identity"]),
            parent_research_identity=str(
                payload["parent_research_identity"]
            ),
            registered_validation_policy_hash=policy_hash,
            validation_outcomes_read=True,
            test_outcomes_read=False,
            payload=payload,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ValueError(
            "five-day ranking validation artifact is invalid"
        ) from None
