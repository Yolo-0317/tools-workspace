"""Strict immutable report for ranking V3 score-component attribution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from typing import Mapping

from .five_day_ranking_v3 import (
    V3_POLICY_IDS,
    V3_SCORE_FORMULA_VERSION,
    five_day_v3_policy_set_hash,
)
from .five_day_ranking_v3_attribution import (
    canonical_decimal_mean,
    exact_decimal_sum,
    wilson_interval,
)
from .five_day_ranking_v3_component_attribution import (
    COMPONENT_ATTRIBUTION_SCHEMA,
    COMPONENT_ATTRIBUTION_VERSION,
    COMPONENT_IDS,
    EXPERIMENT_IDS,
    AblationDelta,
    ComponentCorrelationMetrics,
    ComponentCorrelationReview,
    FiveDayRankingV3ComponentAttributionReview,
    FoldExperimentReview,
    PolicyComponentEffect,
    RobustRankMetrics,
    classify_component_effect,
)


_FOLDS = ("train-fold-1", "train-fold-2")
_COMBINED = "train-combined"
_ABLATION_COMPONENTS = ("CONSISTENCY", "STRUCTURE", "DOWNSIDE")
_STATUSES = {
    "LINEAGE_INVALID",
    "SCORE_RECONSTRUCTION_FAILED",
    "BASELINE_REPRODUCTION_FAILED",
    "MARKET_DATA_INCOMPLETE",
    "COMPARABILITY_FAILED",
    "COMPLETE",
}
_FORBIDDEN_KEYS = {
    "code",
    "ts_code",
    "stock_code",
    "plan_key",
    "plan_identity",
    "signal_date",
    "entry_date",
    "exit_date",
    "trade_date",
    "dates",
    "observation",
    "observations",
    "rows",
    "position",
    "positions",
    "holding",
    "holdings",
    "order",
    "orders",
    "credential",
    "credentials",
}


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _canonical_decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else _canonical_decimal_text(value)


def _decimal_required(value: Decimal) -> str:
    return _canonical_decimal_text(value)


def _interval(
    value: tuple[Decimal, Decimal] | None,
) -> list[str] | None:
    return None if value is None else [
        _decimal_required(value[0]),
        _decimal_required(value[1]),
    ]


def _coverage_content(value) -> dict[str, object]:
    return {
        "candidate_rows": value.candidate_rows,
        "eligible_outcomes": value.eligible_outcomes,
        "excluded_without_train_horizon": (
            value.excluded_without_train_horizon
        ),
        "excluded_missing_coverage": value.excluded_missing_coverage,
        "population_fingerprint": value.population_fingerprint,
        "benchmark_fingerprint": value.benchmark_fingerprint,
    }


def _rank_metrics_content(value: RobustRankMetrics) -> dict[str, object]:
    return {
        "candidate_rows": value.candidate_rows,
        "boundary_ties": value.boundary_ties,
        "paired_dates": value.paired_dates,
        "correlation_eligible_dates": value.correlation_eligible_dates,
        "correlation_dates": value.correlation_dates,
        "audit": {
            "raw_difference_sum": _decimal_required(
                value.audit.raw_difference_sum
            ),
            "index_excess_difference_sum": _decimal_required(
                value.audit.index_excess_difference_sum
            ),
            "market_excess_difference_sum": _decimal_required(
                value.audit.market_excess_difference_sum
            ),
            "rank_one_win_dates": value.audit.rank_one_win_dates,
            "raw_correlation_sum": _decimal_required(
                value.audit.raw_correlation_sum
            ),
            "index_excess_correlation_sum": _decimal_required(
                value.audit.index_excess_correlation_sum
            ),
            "market_excess_correlation_sum": _decimal_required(
                value.audit.market_excess_correlation_sum
            ),
            "median_raw_difference": _decimal(
                value.median_raw_difference
            ),
            "median_index_excess_difference": _decimal(
                value.median_index_excess_difference
            ),
            "median_market_excess_difference": _decimal(
                value.median_market_excess_difference
            ),
            "median_raw_correlation": _decimal(
                value.median_raw_correlation
            ),
            "median_index_excess_correlation": _decimal(
                value.median_index_excess_correlation
            ),
            "median_market_excess_correlation": _decimal(
                value.median_market_excess_correlation
            ),
        },
        "mean_raw_difference": _decimal(value.mean_raw_difference),
        "median_raw_difference": _decimal(value.median_raw_difference),
        "mean_index_excess_difference": _decimal(
            value.mean_index_excess_difference
        ),
        "median_index_excess_difference": _decimal(
            value.median_index_excess_difference
        ),
        "mean_market_excess_difference": _decimal(
            value.mean_market_excess_difference
        ),
        "median_market_excess_difference": _decimal(
            value.median_market_excess_difference
        ),
        "rank_one_win_ratio": _decimal(value.rank_one_win_ratio),
        "rank_one_win_interval": _interval(value.rank_one_win_interval),
        "mean_raw_correlation": _decimal(value.mean_raw_correlation),
        "median_raw_correlation": _decimal(value.median_raw_correlation),
        "mean_index_excess_correlation": _decimal(
            value.mean_index_excess_correlation
        ),
        "median_index_excess_correlation": _decimal(
            value.median_index_excess_correlation
        ),
        "mean_market_excess_correlation": _decimal(
            value.mean_market_excess_correlation
        ),
        "median_market_excess_correlation": _decimal(
            value.median_market_excess_correlation
        ),
    }


def _experiment_content(value: FoldExperimentReview) -> dict[str, object]:
    return {
        "fold_id": value.fold_id,
        "policy_id": value.policy_id,
        "experiment_id": value.experiment_id,
        "coverage": _coverage_content(value.coverage),
        "metrics": _rank_metrics_content(value.metrics),
        "status": value.status,
    }


def _correlation_metrics_content(
    value: ComponentCorrelationMetrics,
) -> dict[str, object]:
    return {
        "component_id": value.component_id,
        "eligible_dates": value.eligible_dates,
        "completed_dates": value.completed_dates,
        "audit": {
            "raw_correlation_sum": _decimal_required(
                value.audit.raw_correlation_sum
            ),
            "index_excess_correlation_sum": _decimal_required(
                value.audit.index_excess_correlation_sum
            ),
            "market_excess_correlation_sum": _decimal_required(
                value.audit.market_excess_correlation_sum
            ),
            "median_raw_correlation": _decimal(
                value.median_raw_correlation
            ),
            "median_index_excess_correlation": _decimal(
                value.median_index_excess_correlation
            ),
            "median_market_excess_correlation": _decimal(
                value.median_market_excess_correlation
            ),
        },
        "mean_raw_correlation": _decimal(value.mean_raw_correlation),
        "median_raw_correlation": _decimal(value.median_raw_correlation),
        "mean_index_excess_correlation": _decimal(
            value.mean_index_excess_correlation
        ),
        "median_index_excess_correlation": _decimal(
            value.median_index_excess_correlation
        ),
        "mean_market_excess_correlation": _decimal(
            value.mean_market_excess_correlation
        ),
        "median_market_excess_correlation": _decimal(
            value.median_market_excess_correlation
        ),
    }


def _correlation_content(
    review: ComponentCorrelationReview,
    metric: ComponentCorrelationMetrics,
) -> dict[str, object]:
    return {
        "fold_id": review.fold_id,
        "policy_id": review.policy_id,
        "population_fingerprint": review.population_fingerprint,
        "metrics": _correlation_metrics_content(metric),
    }


def _delta_content(value: AblationDelta) -> dict[str, object]:
    return {
        "paired_dates": value.paired_dates,
        "correlation_dates": value.correlation_dates,
        "boundary_ties": value.boundary_ties,
        "median_raw_difference_delta": _decimal_required(
            value.median_raw_difference_delta
        ),
        "rank_one_win_ratio_delta": _decimal_required(
            value.rank_one_win_ratio_delta
        ),
        "mean_raw_correlation_delta": _decimal_required(
            value.mean_raw_correlation_delta
        ),
        "mean_index_excess_difference_delta": _decimal_required(
            value.mean_index_excess_difference_delta
        ),
        "mean_market_excess_difference_delta": _decimal_required(
            value.mean_market_excess_difference_delta
        ),
    }


def _effect_content(value: PolicyComponentEffect) -> dict[str, object]:
    return {
        "policy_id": value.policy_id,
        "component_id": value.component_id,
        "fold1": _delta_content(value.fold1),
        "fold2": _delta_content(value.fold2),
        "label": value.label,
    }


def five_day_ranking_v3_component_attribution_payload(
    review: FiveDayRankingV3ComponentAttributionReview,
) -> dict[str, object]:
    """Build canonical aggregate-only component-attribution content."""

    fold_experiments = sorted(
        review.fold_experiments,
        key=lambda value: (
            V3_POLICY_IDS.index(value.policy_id),
            _FOLDS.index(value.fold_id),
            EXPERIMENT_IDS.index(value.experiment_id),
        ),
    )
    combined_experiments = sorted(
        review.combined_experiments,
        key=lambda value: (
            V3_POLICY_IDS.index(value.policy_id),
            EXPERIMENT_IDS.index(value.experiment_id),
        ),
    )
    fold_correlations = sorted(
        (
            _correlation_content(block, metric)
            for block in review.fold_component_correlations
            for metric in block.metrics
        ),
        key=lambda value: (
            V3_POLICY_IDS.index(str(value["policy_id"])),
            _FOLDS.index(str(value["fold_id"])),
            COMPONENT_IDS.index(str(value["metrics"]["component_id"])),
        ),
    )
    combined_correlations = sorted(
        (
            _correlation_content(block, metric)
            for block in review.combined_component_correlations
            for metric in block.metrics
        ),
        key=lambda value: (
            V3_POLICY_IDS.index(str(value["policy_id"])),
            COMPONENT_IDS.index(str(value["metrics"]["component_id"])),
        ),
    )
    effects = sorted(
        review.component_effects,
        key=lambda value: (
            V3_POLICY_IDS.index(value.policy_id),
            _ABLATION_COMPONENTS.index(value.component_id),
        ),
    )
    content: dict[str, object] = {
        "schema": review.schema,
        "component_attribution_version": (
            review.component_attribution_version
        ),
        "parent_train_identity": review.parent_train_identity,
        "parent_research_identity": review.parent_research_identity,
        "parent_input_fingerprint": review.parent_input_fingerprint,
        "parent_attribution_identity": review.parent_attribution_identity,
        "market_data_fingerprint": review.market_data_fingerprint,
        "train_split_identity": review.train_split_identity,
        "policy_set_hash": five_day_v3_policy_set_hash(),
        "score_formula_version": V3_SCORE_FORMULA_VERSION,
        "fold_experiments": [
            _experiment_content(value) for value in fold_experiments
        ],
        "combined_experiments": [
            _experiment_content(value) for value in combined_experiments
        ],
        "fold_component_correlations": fold_correlations,
        "combined_component_correlations": combined_correlations,
        "component_effects": [_effect_content(value) for value in effects],
        "status": review.status,
        "train_only": review.train_only,
        "validation_outcomes_read": review.validation_outcomes_read,
        "test_outcomes_read": review.test_outcomes_read,
        "promotion_eligible": review.promotion_eligible,
        "trade_permission": review.trade_permission,
    }
    return {**content, "artifact_identity": _sha256(content)}


def _write_exclusive_or_verify(path: Path, serialized: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != serialized:
            raise FileExistsError(f"immutable artifact conflict: {path}") from None


def write_five_day_ranking_v3_component_attribution(
    review: FiveDayRankingV3ComponentAttributionReview,
    output_dir: str | Path,
) -> Path:
    payload = five_day_ranking_v3_component_attribution_payload(review)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (
        "ranking-v3-component-attribution-"
        f"{payload['artifact_identity']}.json"
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
class FiveDayRankingV3ComponentAttributionArtifact:
    artifact_identity: str
    parent_train_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    parent_attribution_identity: str
    market_data_fingerprint: str
    status: str
    payload: Mapping[str, object]


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(item in "0123456789abcdef" for item in value)
    )


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError
    return value


def _nonnegative_int(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError
    return value


def _finite_decimal(
    value: object,
    *,
    optional: bool = False,
) -> Decimal | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError
    result = Decimal(value)
    if not result.is_finite() or _canonical_decimal_text(result) != value:
        raise ValueError
    return result


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, Mapping):
        return bool(set(value) & _FORBIDDEN_KEYS) or any(
            _contains_forbidden_key(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


_RANK_DECIMAL_FIELDS = (
    "mean_raw_difference",
    "median_raw_difference",
    "mean_index_excess_difference",
    "median_index_excess_difference",
    "mean_market_excess_difference",
    "median_market_excess_difference",
    "rank_one_win_ratio",
    "mean_raw_correlation",
    "median_raw_correlation",
    "mean_index_excess_correlation",
    "median_index_excess_correlation",
    "mean_market_excess_correlation",
    "median_market_excess_correlation",
)
_RANK_AUDIT_SUMS = (
    "raw_difference_sum",
    "index_excess_difference_sum",
    "market_excess_difference_sum",
    "raw_correlation_sum",
    "index_excess_correlation_sum",
    "market_excess_correlation_sum",
)
_RANK_AUDIT_MEDIANS = (
    "median_raw_difference",
    "median_index_excess_difference",
    "median_market_excess_difference",
    "median_raw_correlation",
    "median_index_excess_correlation",
    "median_market_excess_correlation",
)


def _rank_metrics_values(value: object) -> dict[str, object]:
    metric = _mapping(value)
    expected = {
        "candidate_rows",
        "boundary_ties",
        "paired_dates",
        "correlation_eligible_dates",
        "correlation_dates",
        "audit",
        *_RANK_DECIMAL_FIELDS,
        "rank_one_win_interval",
    }
    if set(metric) != expected:
        raise ValueError
    candidate_rows = _nonnegative_int(metric["candidate_rows"])
    boundary_ties = _nonnegative_int(metric["boundary_ties"])
    paired_dates = _nonnegative_int(metric["paired_dates"])
    eligible_dates = _nonnegative_int(metric["correlation_eligible_dates"])
    correlation_dates = _nonnegative_int(metric["correlation_dates"])
    if correlation_dates > eligible_dates:
        raise ValueError
    audit = _mapping(metric["audit"])
    if set(audit) != {
        *_RANK_AUDIT_SUMS,
        *_RANK_AUDIT_MEDIANS,
        "rank_one_win_dates",
    }:
        raise ValueError
    sums = {field: _finite_decimal(audit[field]) for field in _RANK_AUDIT_SUMS}
    medians = {
        field: _finite_decimal(metric[field], optional=True)
        for field in _RANK_AUDIT_MEDIANS
    }
    if any(
        _finite_decimal(audit[field], optional=True) != medians[field]
        for field in _RANK_AUDIT_MEDIANS
    ):
        raise ValueError
    decimals = {
        field: _finite_decimal(metric[field], optional=True)
        for field in _RANK_DECIMAL_FIELDS
    }
    wins = _nonnegative_int(audit["rank_one_win_dates"])
    if wins > paired_dates:
        raise ValueError
    interval_value = metric["rank_one_win_interval"]
    interval: tuple[Decimal, Decimal] | None = None
    if interval_value is not None:
        if not isinstance(interval_value, list) or len(interval_value) != 2:
            raise ValueError
        lower = _finite_decimal(interval_value[0])
        upper = _finite_decimal(interval_value[1])
        assert lower is not None and upper is not None
        interval = (lower, upper)
    pair_fields = _RANK_DECIMAL_FIELDS[:7]
    correlation_fields = _RANK_DECIMAL_FIELDS[7:]
    if paired_dates == 0:
        if (
            wins
            or any(decimals[field] is not None for field in pair_fields)
            or interval is not None
        ):
            raise ValueError
    else:
        if any(decimals[field] is None for field in pair_fields):
            raise ValueError
        raw_sum = sums["raw_difference_sum"]
        index_sum = sums["index_excess_difference_sum"]
        market_sum = sums["market_excess_difference_sum"]
        assert raw_sum is not None and index_sum is not None and market_sum is not None
        if (
            decimals["mean_raw_difference"]
            != canonical_decimal_mean(raw_sum, paired_dates)
            or decimals["mean_index_excess_difference"]
            != canonical_decimal_mean(index_sum, paired_dates)
            or decimals["mean_market_excess_difference"]
            != canonical_decimal_mean(market_sum, paired_dates)
            or decimals["rank_one_win_ratio"]
            != canonical_decimal_mean(Decimal(wins), paired_dates)
            or interval != wilson_interval(wins, paired_dates)
        ):
            raise ValueError
    if correlation_dates == 0:
        if any(decimals[field] is not None for field in correlation_fields):
            raise ValueError
    else:
        if any(decimals[field] is None for field in correlation_fields):
            raise ValueError
        raw_correlation_sum = sums["raw_correlation_sum"]
        index_correlation_sum = sums["index_excess_correlation_sum"]
        market_correlation_sum = sums["market_excess_correlation_sum"]
        assert (
            raw_correlation_sum is not None
            and index_correlation_sum is not None
            and market_correlation_sum is not None
        )
        if (
            decimals["mean_raw_correlation"]
            != canonical_decimal_mean(raw_correlation_sum, correlation_dates)
            or decimals["mean_index_excess_correlation"]
            != canonical_decimal_mean(index_correlation_sum, correlation_dates)
            or decimals["mean_market_excess_correlation"]
            != canonical_decimal_mean(market_correlation_sum, correlation_dates)
        ):
            raise ValueError
        if any(
            value is not None and not Decimal("-1") <= value <= Decimal("1")
            for field, value in decimals.items()
            if "correlation" in field
        ):
            raise ValueError
    return {
        "candidate_rows": candidate_rows,
        "boundary_ties": boundary_ties,
        "paired_dates": paired_dates,
        "correlation_dates": correlation_dates,
        **decimals,
    }


def _coverage_values(value: object) -> dict[str, object]:
    coverage = _mapping(value)
    expected = {
        "candidate_rows",
        "eligible_outcomes",
        "excluded_without_train_horizon",
        "excluded_missing_coverage",
        "population_fingerprint",
        "benchmark_fingerprint",
    }
    if set(coverage) != expected:
        raise ValueError
    candidate_rows = _nonnegative_int(coverage["candidate_rows"])
    eligible = _nonnegative_int(coverage["eligible_outcomes"])
    without_horizon = _nonnegative_int(
        coverage["excluded_without_train_horizon"]
    )
    missing = _nonnegative_int(coverage["excluded_missing_coverage"])
    if candidate_rows != eligible + without_horizon + missing:
        raise ValueError
    population = coverage["population_fingerprint"]
    benchmark = coverage["benchmark_fingerprint"]
    if not _digest(population) or not _digest(benchmark):
        raise ValueError
    return {
        "candidate_rows": candidate_rows,
        "eligible_outcomes": eligible,
        "population_fingerprint": population,
        "benchmark_fingerprint": benchmark,
    }


def _experiment_registry(
    values: object,
    *,
    folds: tuple[str, ...],
) -> dict[tuple[str, str, str], Mapping[str, object]]:
    if not isinstance(values, list):
        raise ValueError
    expected = tuple(
        (fold_id, policy_id, experiment_id)
        for policy_id in V3_POLICY_IDS
        for fold_id in folds
        for experiment_id in EXPERIMENT_IDS
    )
    registry: dict[tuple[str, str, str], Mapping[str, object]] = {}
    actual: list[tuple[str, str, str]] = []
    for item in values:
        value = _mapping(item)
        if set(value) != {
            "fold_id",
            "policy_id",
            "experiment_id",
            "coverage",
            "metrics",
            "status",
        }:
            raise ValueError
        key = (
            str(value["fold_id"]),
            str(value["policy_id"]),
            str(value["experiment_id"]),
        )
        coverage = _coverage_values(value["coverage"])
        metrics = _rank_metrics_values(value["metrics"])
        if metrics["candidate_rows"] != coverage["eligible_outcomes"]:
            raise ValueError
        expected_status = (
            "BOUNDARY_TIE_INCONCLUSIVE"
            if metrics["boundary_ties"]
            else "COMPLETE"
        )
        if value["status"] != expected_status:
            raise ValueError
        actual.append(key)
        registry[key] = value
    if tuple(actual) != expected or len(registry) != len(expected):
        raise ValueError
    for fold_id in folds:
        for policy_id in V3_POLICY_IDS:
            populations = {
                _mapping(registry[(fold_id, policy_id, experiment_id)]["coverage"])[
                    "population_fingerprint"
                ]
                for experiment_id in EXPERIMENT_IDS
            }
            coverages = {
                json.dumps(
                    registry[(fold_id, policy_id, experiment_id)]["coverage"],
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for experiment_id in EXPERIMENT_IDS
            }
            if len(populations) != 1 or len(coverages) != 1:
                raise ValueError
    return registry


_CORRELATION_DECIMAL_FIELDS = (
    "mean_raw_correlation",
    "median_raw_correlation",
    "mean_index_excess_correlation",
    "median_index_excess_correlation",
    "mean_market_excess_correlation",
    "median_market_excess_correlation",
)


def _correlation_registry(
    values: object,
    *,
    folds: tuple[str, ...],
    experiments: Mapping[tuple[str, str, str], Mapping[str, object]],
) -> dict[tuple[str, str, str], Mapping[str, object]]:
    if not isinstance(values, list):
        raise ValueError
    expected = tuple(
        (fold_id, policy_id, component_id)
        for policy_id in V3_POLICY_IDS
        for fold_id in folds
        for component_id in COMPONENT_IDS
    )
    actual: list[tuple[str, str, str]] = []
    registry: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for item in values:
        value = _mapping(item)
        if set(value) != {
            "fold_id",
            "policy_id",
            "population_fingerprint",
            "metrics",
        }:
            raise ValueError
        metric = _mapping(value["metrics"])
        if set(metric) != {
            "component_id",
            "eligible_dates",
            "completed_dates",
            "audit",
            *_CORRELATION_DECIMAL_FIELDS,
        }:
            raise ValueError
        fold_id = str(value["fold_id"])
        policy_id = str(value["policy_id"])
        component_id = str(metric["component_id"])
        actual.append((fold_id, policy_id, component_id))
        registry[(fold_id, policy_id, component_id)] = value
        population = value["population_fingerprint"]
        baseline = experiments[(fold_id, policy_id, "BASELINE")]
        if (
            not _digest(population)
            or population
            != _mapping(baseline["coverage"])["population_fingerprint"]
        ):
            raise ValueError
        eligible = _nonnegative_int(metric["eligible_dates"])
        completed = _nonnegative_int(metric["completed_dates"])
        if completed > eligible:
            raise ValueError
        audit = _mapping(metric["audit"])
        if set(audit) != {
            "raw_correlation_sum",
            "index_excess_correlation_sum",
            "market_excess_correlation_sum",
            "median_raw_correlation",
            "median_index_excess_correlation",
            "median_market_excess_correlation",
        }:
            raise ValueError
        decimals = {
            field: _finite_decimal(metric[field], optional=True)
            for field in _CORRELATION_DECIMAL_FIELDS
        }
        for field in (
            "median_raw_correlation",
            "median_index_excess_correlation",
            "median_market_excess_correlation",
        ):
            if _finite_decimal(audit[field], optional=True) != decimals[field]:
                raise ValueError
        sums = {
            field: _finite_decimal(audit[field])
            for field in (
                "raw_correlation_sum",
                "index_excess_correlation_sum",
                "market_excess_correlation_sum",
            )
        }
        if completed == 0:
            if any(value is not None for value in decimals.values()):
                raise ValueError
        elif (
            any(value is None for value in decimals.values())
            or decimals["mean_raw_correlation"]
            != canonical_decimal_mean(sums["raw_correlation_sum"], completed)
            or decimals["mean_index_excess_correlation"]
            != canonical_decimal_mean(
                sums["index_excess_correlation_sum"], completed
            )
            or decimals["mean_market_excess_correlation"]
            != canonical_decimal_mean(
                sums["market_excess_correlation_sum"], completed
            )
        ):
            raise ValueError
    if tuple(actual) != expected:
        raise ValueError
    return registry


def _sum_decimal_fields(
    left: Mapping[str, object],
    right: Mapping[str, object],
    combined: Mapping[str, object],
    fields: tuple[str, ...],
) -> bool:
    return all(
        _finite_decimal(combined[field])
        == exact_decimal_sum(
            (
                _finite_decimal(left[field]),
                _finite_decimal(right[field]),
            )
        )
        for field in fields
    )


def _combined_experiments_are_valid(
    folds: Mapping[tuple[str, str, str], Mapping[str, object]],
    combined: Mapping[tuple[str, str, str], Mapping[str, object]],
) -> bool:
    for policy_id in V3_POLICY_IDS:
        for experiment_id in EXPERIMENT_IDS:
            left = folds[("train-fold-1", policy_id, experiment_id)]
            right = folds[("train-fold-2", policy_id, experiment_id)]
            total = combined[(_COMBINED, policy_id, experiment_id)]
            left_coverage = _mapping(left["coverage"])
            right_coverage = _mapping(right["coverage"])
            total_coverage = _mapping(total["coverage"])
            for field in (
                "candidate_rows",
                "eligible_outcomes",
                "excluded_without_train_horizon",
                "excluded_missing_coverage",
            ):
                if _nonnegative_int(total_coverage[field]) != (
                    _nonnegative_int(left_coverage[field])
                    + _nonnegative_int(right_coverage[field])
                ):
                    return False
            left_metrics = _mapping(left["metrics"])
            right_metrics = _mapping(right["metrics"])
            total_metrics = _mapping(total["metrics"])
            for field in (
                "candidate_rows",
                "boundary_ties",
                "paired_dates",
                "correlation_eligible_dates",
                "correlation_dates",
            ):
                if _nonnegative_int(total_metrics[field]) != (
                    _nonnegative_int(left_metrics[field])
                    + _nonnegative_int(right_metrics[field])
                ):
                    return False
            left_audit = _mapping(left_metrics["audit"])
            right_audit = _mapping(right_metrics["audit"])
            total_audit = _mapping(total_metrics["audit"])
            if _nonnegative_int(total_audit["rank_one_win_dates"]) != (
                _nonnegative_int(left_audit["rank_one_win_dates"])
                + _nonnegative_int(right_audit["rank_one_win_dates"])
            ) or not _sum_decimal_fields(
                left_audit,
                right_audit,
                total_audit,
                _RANK_AUDIT_SUMS,
            ):
                return False
    return True


def _combined_correlations_are_valid(
    folds: Mapping[tuple[str, str, str], Mapping[str, object]],
    combined: Mapping[tuple[str, str, str], Mapping[str, object]],
) -> bool:
    sum_fields = (
        "raw_correlation_sum",
        "index_excess_correlation_sum",
        "market_excess_correlation_sum",
    )
    for policy_id in V3_POLICY_IDS:
        for component_id in COMPONENT_IDS:
            left = _mapping(
                folds[("train-fold-1", policy_id, component_id)]["metrics"]
            )
            right = _mapping(
                folds[("train-fold-2", policy_id, component_id)]["metrics"]
            )
            total = _mapping(
                combined[(_COMBINED, policy_id, component_id)]["metrics"]
            )
            for field in ("eligible_dates", "completed_dates"):
                if _nonnegative_int(total[field]) != (
                    _nonnegative_int(left[field])
                    + _nonnegative_int(right[field])
                ):
                    return False
            if not _sum_decimal_fields(
                _mapping(left["audit"]),
                _mapping(right["audit"]),
                _mapping(total["audit"]),
                sum_fields,
            ):
                return False
    return True


_DELTA_FIELDS = (
    "median_raw_difference_delta",
    "rank_one_win_ratio_delta",
    "mean_raw_correlation_delta",
    "mean_index_excess_difference_delta",
    "mean_market_excess_difference_delta",
)


def _delta_values(value: object) -> AblationDelta:
    delta = _mapping(value)
    if set(delta) != {
        "paired_dates",
        "correlation_dates",
        "boundary_ties",
        *_DELTA_FIELDS,
    }:
        raise ValueError
    decimals = {field: _finite_decimal(delta[field]) for field in _DELTA_FIELDS}
    return AblationDelta(
        paired_dates=_nonnegative_int(delta["paired_dates"]),
        correlation_dates=_nonnegative_int(delta["correlation_dates"]),
        boundary_ties=_nonnegative_int(delta["boundary_ties"]),
        **decimals,
    )


def _expected_delta(
    baseline: Mapping[str, object],
    ablation: Mapping[str, object],
) -> AblationDelta:
    base = _rank_metrics_values(baseline["metrics"])
    removed = _rank_metrics_values(ablation["metrics"])
    if (
        base["candidate_rows"] != removed["candidate_rows"]
        or base["paired_dates"] != removed["paired_dates"]
        or base["correlation_dates"] != removed["correlation_dates"]
    ):
        raise ValueError
    fields = (
        "median_raw_difference",
        "rank_one_win_ratio",
        "mean_raw_correlation",
        "mean_index_excess_difference",
        "mean_market_excess_difference",
    )
    if any(base[field] is None or removed[field] is None for field in fields):
        raise ValueError
    return AblationDelta(
        paired_dates=int(base["paired_dates"]),
        correlation_dates=int(base["correlation_dates"]),
        boundary_ties=int(removed["boundary_ties"]),
        median_raw_difference_delta=removed[fields[0]] - base[fields[0]],
        rank_one_win_ratio_delta=removed[fields[1]] - base[fields[1]],
        mean_raw_correlation_delta=removed[fields[2]] - base[fields[2]],
        mean_index_excess_difference_delta=(
            removed[fields[3]] - base[fields[3]]
        ),
        mean_market_excess_difference_delta=(
            removed[fields[4]] - base[fields[4]]
        ),
    )


def _effects_are_valid(
    values: object,
    experiments: Mapping[tuple[str, str, str], Mapping[str, object]],
) -> bool:
    if not isinstance(values, list):
        return False
    expected = tuple(
        (policy_id, component_id)
        for policy_id in V3_POLICY_IDS
        for component_id in _ABLATION_COMPONENTS
    )
    experiment_by_component = {
        "CONSISTENCY": "WITHOUT_CONSISTENCY",
        "STRUCTURE": "WITHOUT_STRUCTURE",
        "DOWNSIDE": "WITHOUT_DOWNSIDE",
    }
    actual: list[tuple[str, str]] = []
    for item in values:
        value = _mapping(item)
        if set(value) != {
            "policy_id",
            "component_id",
            "fold1",
            "fold2",
            "label",
        }:
            return False
        policy_id = str(value["policy_id"])
        component_id = str(value["component_id"])
        actual.append((policy_id, component_id))
        experiment_id = experiment_by_component.get(component_id)
        if experiment_id is None:
            return False
        fold1 = _delta_values(value["fold1"])
        fold2 = _delta_values(value["fold2"])
        if (
            fold1
            != _expected_delta(
                experiments[("train-fold-1", policy_id, "BASELINE")],
                experiments[("train-fold-1", policy_id, experiment_id)],
            )
            or fold2
            != _expected_delta(
                experiments[("train-fold-2", policy_id, "BASELINE")],
                experiments[("train-fold-2", policy_id, experiment_id)],
            )
        ):
            return False
        expected_label = classify_component_effect(
            fold1, fold2, component_id=component_id
        ).label
        if value["label"] != expected_label:
            return False
    return tuple(actual) == expected


def _basic_content_is_valid(content: Mapping[str, object]) -> bool:
    expected = {
        "schema",
        "component_attribution_version",
        "parent_train_identity",
        "parent_research_identity",
        "parent_input_fingerprint",
        "parent_attribution_identity",
        "market_data_fingerprint",
        "train_split_identity",
        "policy_set_hash",
        "score_formula_version",
        "fold_experiments",
        "combined_experiments",
        "fold_component_correlations",
        "combined_component_correlations",
        "component_effects",
        "status",
        "train_only",
        "validation_outcomes_read",
        "test_outcomes_read",
        "promotion_eligible",
        "trade_permission",
    }
    try:
        status = content.get("status")
        complete = status == "COMPLETE"
        if not (
            set(content) == expected
            and content.get("schema") == COMPONENT_ATTRIBUTION_SCHEMA
            and content.get("component_attribution_version")
            == COMPONENT_ATTRIBUTION_VERSION
            and all(
                _digest(content.get(key))
                for key in (
                    "parent_train_identity",
                    "parent_research_identity",
                    "parent_input_fingerprint",
                    "parent_attribution_identity",
                    "market_data_fingerprint",
                    "train_split_identity",
                    "policy_set_hash",
                )
            )
            and content.get("policy_set_hash")
            == five_day_v3_policy_set_hash()
            and content.get("score_formula_version")
            == V3_SCORE_FORMULA_VERSION
            and status in _STATUSES
            and content.get("train_only") is True
            and content.get("validation_outcomes_read") is False
            and content.get("test_outcomes_read") is False
            and content.get("promotion_eligible") is False
            and content.get("trade_permission") == "NO-TRADE"
            and not _contains_forbidden_key(content)
        ):
            return False
        if not complete:
            return all(
                isinstance(content[key], list) and not content[key]
                for key in (
                    "fold_experiments",
                    "combined_experiments",
                    "fold_component_correlations",
                    "combined_component_correlations",
                    "component_effects",
                )
            )
        fold_registry = _experiment_registry(
            content["fold_experiments"], folds=_FOLDS
        )
        combined_registry = _experiment_registry(
            content["combined_experiments"], folds=(_COMBINED,)
        )
        fold_correlations = _correlation_registry(
            content["fold_component_correlations"],
            folds=_FOLDS,
            experiments=fold_registry,
        )
        combined_correlations = _correlation_registry(
            content["combined_component_correlations"],
            folds=(_COMBINED,),
            experiments=combined_registry,
        )
        return (
            _combined_experiments_are_valid(
                fold_registry, combined_registry
            )
            and _combined_correlations_are_valid(
                fold_correlations, combined_correlations
            )
            and _effects_are_valid(
                content["component_effects"], fold_registry
            )
        )
    except (
        AssertionError,
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
        IndexError,
    ):
        return False


def load_five_day_ranking_v3_component_attribution(
    path: str | Path,
    *,
    expected_parent_train_identity: str | None = None,
    expected_parent_research_identity: str | None = None,
    expected_parent_attribution_identity: str | None = None,
) -> FiveDayRankingV3ComponentAttributionArtifact:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError
        identity = payload["artifact_identity"]
        content = {
            key: value
            for key, value in payload.items()
            if key != "artifact_identity"
        }
        if (
            not _digest(identity)
            or set(payload) != set(content) | {"artifact_identity"}
            or identity != _sha256(content)
            or target.name
            != f"ranking-v3-component-attribution-{identity}.json"
            or not _basic_content_is_valid(content)
            or (
                expected_parent_train_identity is not None
                and content["parent_train_identity"]
                != expected_parent_train_identity
            )
            or (
                expected_parent_research_identity is not None
                and content["parent_research_identity"]
                != expected_parent_research_identity
            )
            or (
                expected_parent_attribution_identity is not None
                and content["parent_attribution_identity"]
                != expected_parent_attribution_identity
            )
        ):
            raise ValueError
    except (
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
        OSError,
        json.JSONDecodeError,
    ):
        raise ValueError(
            "invalid ranking v3 component attribution artifact"
        ) from None
    return FiveDayRankingV3ComponentAttributionArtifact(
        artifact_identity=identity,
        parent_train_identity=str(content["parent_train_identity"]),
        parent_research_identity=str(content["parent_research_identity"]),
        parent_input_fingerprint=str(content["parent_input_fingerprint"]),
        parent_attribution_identity=str(
            content["parent_attribution_identity"]
        ),
        market_data_fingerprint=str(content["market_data_fingerprint"]),
        status=str(content["status"]),
        payload=payload,
    )
