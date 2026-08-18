"""Strict immutable aggregate-only attribution evidence for ranking V3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from typing import Mapping

from .five_day_ranking_v3 import V3_POLICY_IDS, V3_SELECTION_MODES
from .five_day_ranking_v3_attribution import (
    ATTRIBUTION_SCHEMA,
    ATTRIBUTION_VERSION,
    MIN_MARKET_MEDIAN_MEMBERS,
    MIN_RANK_PAIR_DATES,
    UNIVERSE_VERSION,
    AttributionMetrics,
    AttributionVariantReview,
    CoverageSummary,
    FiveDayRankingV3AttributionReview,
    RankCorrelationMetrics,
    RankPairMetrics,
    attribution_verdict,
    canonical_decimal_mean,
    exact_decimal_sum,
    wilson_interval,
)


_FOLDS = ("train-fold-1", "train-fold-2", "train-combined")
_RANK_BANDS = ("RANK_1", "RANK_2_3", "RANK_4_5", "RANK_6_PLUS")
_STATUSES = (
    "STOPPED",
    "TIME_EXIT_GAIN",
    "TIME_EXIT_FLAT",
    "TIME_EXIT_LOSS",
)
_ATTRIBUTION_VERDICTS = {
    "INCONCLUSIVE",
    "MARKET_DRAG",
    "STRATEGY_DRAG",
    "MIXED",
}
_RANK_VERDICTS = {
    "RANKER_INCONCLUSIVE",
    "RANKER_HEALTHY",
    "RANKER_INVERTED",
    "RANKER_MIXED",
}
_FORBIDDEN_KEYS = {
    "observations",
    "selected_observations",
    "plans",
    "plan_keys",
    "ranked_plan_keys",
    "admitted_trade_keys",
    "code",
    "ts_code",
    "position",
    "holding",
    "order",
    "notification",
    "memory",
}
_REQUIRED_FUNNEL_KEYS = {
    "ACTUAL_ATTRIBUTION_ELIGIBLE",
    "ACTUAL_ATTRIBUTION_COMPLETED",
    "ACTUAL_ATTRIBUTION_MISSING_COVERAGE",
    "FIXED_FIVE_RANKED_ELIGIBLE",
    "FIXED_FIVE_COMPLETED",
    "FIXED_FIVE_MISSING_COVERAGE",
    "FIXED_FIVE_WITHOUT_TRAIN_HORIZON",
    "FIXED_FIVE_STOCK_ENDPOINT_MISSING",
}
_BENCHMARK_DEFINITIONS = {
    "actual_interval_basis": (
        "entry-date-close-to-exit-date-close-attribution-approximation-v1"
    ),
    "fixed_five_basis": (
        "signal-close-to-fifth-subsequent-train-close-v1"
    ),
    "matched_indexes": {
        "000|001|002|003": "sz.399001",
        "600|601|603|605": "sh.000001",
        "688": "sh.000688",
    },
    "minimum_market_members": MIN_MARKET_MEDIAN_MEMBERS,
    "universe_version": UNIVERSE_VERSION,
}
_METRIC_DECIMAL_FIELDS = (
    "mean_return",
    "median_return",
    "positive_ratio",
    "mean_matched_index_return",
    "median_matched_index_return",
    "mean_market_median_return",
    "median_market_median_return",
    "mean_index_excess",
    "median_index_excess",
    "mean_market_median_excess",
    "median_market_median_excess",
    "mean_gross_return",
    "mean_after_cost_drag",
)
_METRIC_KEYS = {
    "eligible_rows",
    "completed_rows",
    "excluded_rows",
    "excluded_missing_coverage",
    "audit_totals",
    *_METRIC_DECIMAL_FIELDS,
    "positive_wilson_interval",
    "verdict",
}
_AUDIT_TOTAL_KEYS = {
    "positive_rows",
    "raw_return_sum",
    "matched_index_return_sum",
    "market_median_return_sum",
    "gross_return_sum",
}
_PAIR_DECIMAL_FIELDS = (
    "mean_raw_difference",
    "median_raw_difference",
    "mean_index_excess_difference",
    "median_index_excess_difference",
    "mean_market_excess_difference",
    "median_market_excess_difference",
    "rank_one_win_ratio",
)
_CORRELATION_DECIMAL_FIELDS = (
    "mean_raw_correlation",
    "median_raw_correlation",
    "mean_index_excess_correlation",
    "median_index_excess_correlation",
    "mean_market_excess_correlation",
    "median_market_excess_correlation",
)


def _benchmark_definitions_content() -> dict[str, object]:
    return {
        "actual_interval_basis": _BENCHMARK_DEFINITIONS[
            "actual_interval_basis"
        ],
        "fixed_five_basis": _BENCHMARK_DEFINITIONS["fixed_five_basis"],
        "matched_indexes": dict(_BENCHMARK_DEFINITIONS["matched_indexes"]),
        "minimum_market_members": _BENCHMARK_DEFINITIONS[
            "minimum_market_members"
        ],
        "universe_version": _BENCHMARK_DEFINITIONS["universe_version"],
    }


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _digest_is_valid(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _decimal_content(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _metrics_content(value: AttributionMetrics) -> dict[str, object]:
    return {
        "eligible_rows": value.eligible_rows,
        "completed_rows": value.completed_rows,
        "excluded_rows": value.excluded_rows,
        "excluded_missing_coverage": value.excluded_missing_coverage,
        "audit_totals": {
            "positive_rows": value.audit_totals.positive_rows,
            "raw_return_sum": _decimal_content(
                value.audit_totals.raw_return_sum
            ),
            "matched_index_return_sum": _decimal_content(
                value.audit_totals.matched_index_return_sum
            ),
            "market_median_return_sum": _decimal_content(
                value.audit_totals.market_median_return_sum
            ),
            "gross_return_sum": _decimal_content(
                value.audit_totals.gross_return_sum
            ),
        },
        "mean_return": _decimal_content(value.mean_return),
        "median_return": _decimal_content(value.median_return),
        "positive_ratio": _decimal_content(value.positive_ratio),
        "positive_wilson_interval": (
            [_decimal_content(item) for item in value.positive_wilson_interval]
            if value.positive_wilson_interval is not None
            else None
        ),
        "mean_matched_index_return": _decimal_content(
            value.mean_matched_index_return
        ),
        "median_matched_index_return": _decimal_content(
            value.median_matched_index_return
        ),
        "mean_market_median_return": _decimal_content(
            value.mean_market_median_return
        ),
        "median_market_median_return": _decimal_content(
            value.median_market_median_return
        ),
        "mean_index_excess": _decimal_content(value.mean_index_excess),
        "median_index_excess": _decimal_content(value.median_index_excess),
        "mean_market_median_excess": _decimal_content(
            value.mean_market_median_excess
        ),
        "median_market_median_excess": _decimal_content(
            value.median_market_median_excess
        ),
        "mean_gross_return": _decimal_content(value.mean_gross_return),
        "mean_after_cost_drag": _decimal_content(value.mean_after_cost_drag),
        "verdict": value.verdict,
    }


def _rank_pairs_content(value: RankPairMetrics) -> dict[str, object]:
    return {
        "paired_dates": value.paired_dates,
        **{
            field: _decimal_content(getattr(value, field))
            for field in _PAIR_DECIMAL_FIELDS
        },
        "verdict": value.verdict,
    }


def _rank_correlations_content(
    value: RankCorrelationMetrics,
) -> dict[str, object]:
    return {
        "eligible_dates": value.eligible_dates,
        "completed_dates": value.completed_dates,
        **{
            field: _decimal_content(getattr(value, field))
            for field in _CORRELATION_DECIMAL_FIELDS
        },
    }


def _variant_content(value: AttributionVariantReview) -> dict[str, object]:
    return {
        "fold_id": value.fold_id,
        "policy_id": value.policy_id,
        "selection_mode": value.selection_mode,
        "actual": _metrics_content(value.actual),
        "actual_by_status": {
            status: _metrics_content(value.actual_by_status[status])
            for status in _STATUSES
        },
        "fixed_five_by_rank_band": {
            band: _metrics_content(value.fixed_five_by_rank_band[band])
            for band in _RANK_BANDS
        },
        "rank_pairs": _rank_pairs_content(value.rank_pairs),
        "rank_correlations": _rank_correlations_content(
            value.rank_correlations
        ),
        "funnel_counts": {
            str(key): count
            for key, count in sorted(value.funnel_counts.items())
        },
    }


def _coverage_content(value: CoverageSummary) -> dict[str, object]:
    return {
        "attempted_intervals": value.attempted_intervals,
        "completed_intervals": value.completed_intervals,
        "index_endpoint_missing_intervals": (
            value.index_endpoint_missing_intervals
        ),
        "market_members_below_threshold_intervals": (
            value.market_members_below_threshold_intervals
        ),
        "missing_endpoint_dates": [
            item.isoformat() for item in value.missing_endpoint_dates
        ],
    }


def _split_content(review: FiveDayRankingV3AttributionReview) -> dict[str, object]:
    return {
        "train": [item.isoformat() for item in review.split.train],
        "validation": [item.isoformat() for item in review.split.validation],
        "test": [item.isoformat() for item in review.split.test],
    }


def five_day_ranking_v3_attribution_payload(
    review: FiveDayRankingV3AttributionReview,
) -> dict[str, object]:
    """Build explicit aggregate-only canonical attribution content."""

    registry = {
        (variant.fold_id, variant.policy_id, variant.selection_mode): variant
        for variant in review.variants
    }
    expected = tuple(
        (fold_id, policy_id, mode)
        for policy_id in V3_POLICY_IDS
        for mode in V3_SELECTION_MODES
        for fold_id in _FOLDS
    )
    if len(registry) != len(review.variants) or set(registry) != set(expected):
        raise ValueError("ranking v3 attribution safety mismatch")
    content: dict[str, object] = {
        "schema": review.schema,
        "attribution_version": review.attribution_version,
        "parent_train_identity": review.parent_train_identity,
        "parent_research_identity": review.parent_research_identity,
        "parent_input_fingerprint": review.parent_input_fingerprint,
        "split": _split_content(review),
        "market_data_fingerprint": review.market_data_fingerprint,
        "benchmark_definitions": _benchmark_definitions_content(),
        "coverage": _coverage_content(review.coverage),
        "variants": [_variant_content(registry[key]) for key in expected],
        "status": review.status,
        "train_only": review.train_only,
        "validation_outcomes_read": review.validation_outcomes_read,
        "test_outcomes_read": review.test_outcomes_read,
        "promotion_eligible": review.promotion_eligible,
        "trade_permission": review.trade_permission,
    }
    if not _content_is_valid(content):
        raise ValueError("ranking v3 attribution safety mismatch")
    return {**content, "artifact_identity": _sha256(content)}


def _write_exclusive_or_verify(path: Path, serialized: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != serialized:
            raise FileExistsError(f"immutable artifact conflict: {path}") from None


def write_five_day_ranking_v3_attribution(
    review: FiveDayRankingV3AttributionReview,
    output_dir: str | Path,
) -> Path:
    """Write once by content identity, or verify identical prior bytes."""

    payload = five_day_ranking_v3_attribution_payload(review)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (
        f"ranking-v3-train-attribution-{payload['artifact_identity']}.json"
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
class FiveDayRankingV3AttributionArtifact:
    artifact_identity: str
    parent_train_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    market_data_fingerprint: str
    status: str
    payload: Mapping[str, object]


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError
    return value


def _exact_keys(value: Mapping[str, object], expected: set[str]) -> bool:
    return set(value) == expected


def _nonnegative_int(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError
    return value


def _finite_decimal(value: object, *, optional: bool = False) -> Decimal | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError
    result = Decimal(value)
    if not result.is_finite():
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


def _audit_totals_values(
    value: object,
    *,
    require_gross: bool,
) -> dict[str, int | Decimal | None]:
    totals = _mapping(value)
    if not _exact_keys(totals, _AUDIT_TOTAL_KEYS):
        raise ValueError
    result: dict[str, int | Decimal | None] = {
        "positive_rows": _nonnegative_int(totals["positive_rows"]),
        "raw_return_sum": _finite_decimal(totals["raw_return_sum"]),
        "matched_index_return_sum": _finite_decimal(
            totals["matched_index_return_sum"]
        ),
        "market_median_return_sum": _finite_decimal(
            totals["market_median_return_sum"]
        ),
        "gross_return_sum": _finite_decimal(
            totals["gross_return_sum"],
            optional=True,
        ),
    }
    gross = result["gross_return_sum"]
    if require_gross != (gross is not None):
        raise ValueError
    return result


def _metric_values(
    value: object,
    *,
    status: str,
    require_gross: bool,
) -> dict[str, Decimal | None] | None:
    metric = _mapping(value)
    if not _exact_keys(metric, _METRIC_KEYS):
        raise ValueError
    eligible = _nonnegative_int(metric["eligible_rows"])
    completed = _nonnegative_int(metric["completed_rows"])
    excluded = _nonnegative_int(metric["excluded_rows"])
    missing = _nonnegative_int(metric["excluded_missing_coverage"])
    if eligible != completed + excluded or missing > excluded:
        raise ValueError
    totals = _audit_totals_values(
        metric["audit_totals"],
        require_gross=require_gross,
    )
    positive_rows = totals["positive_rows"]
    raw_sum = totals["raw_return_sum"]
    index_sum = totals["matched_index_return_sum"]
    market_sum = totals["market_median_return_sum"]
    gross_sum = totals["gross_return_sum"]
    assert isinstance(positive_rows, int)
    assert isinstance(raw_sum, Decimal)
    assert isinstance(index_sum, Decimal)
    assert isinstance(market_sum, Decimal)
    assert gross_sum is None or isinstance(gross_sum, Decimal)
    if positive_rows > completed:
        raise ValueError
    decimals = {
        field: _finite_decimal(metric[field], optional=True)
        for field in _METRIC_DECIMAL_FIELDS
    }
    interval_value = metric["positive_wilson_interval"]
    interval: tuple[Decimal, Decimal] | None = None
    if interval_value is not None:
        if not isinstance(interval_value, list) or len(interval_value) != 2:
            raise ValueError
        lower = _finite_decimal(interval_value[0])
        upper = _finite_decimal(interval_value[1])
        assert lower is not None and upper is not None
        interval = (lower, upper)
    verdict = metric["verdict"]
    if verdict not in _ATTRIBUTION_VERDICTS:
        raise ValueError
    gross = decimals["mean_gross_return"]
    drag = decimals["mean_after_cost_drag"]
    if (gross is None) != (drag is None):
        raise ValueError
    if completed == 0:
        if (
            positive_rows != 0
            or raw_sum != 0
            or index_sum != 0
            or market_sum != 0
            or (require_gross and gross_sum != 0)
            or any(item is not None for item in decimals.values())
            or interval is not None
        ):
            raise ValueError
        if verdict != "INCONCLUSIVE":
            raise ValueError
        return decimals
    base_fields = set(_METRIC_DECIMAL_FIELDS) - {
        "mean_gross_return",
        "mean_after_cost_drag",
    }
    if any(decimals[field] is None for field in base_fields) or interval is None:
        raise ValueError
    if require_gross and (gross is None or drag is None or gross_sum is None):
        raise ValueError
    if not require_gross and (gross is not None or drag is not None):
        raise ValueError
    ratio = decimals["positive_ratio"]
    assert ratio is not None
    if ratio < 0 or ratio > 1 or interval[0] < 0 or interval[1] > 1:
        raise ValueError
    if interval[0] > ratio or interval[1] < ratio:
        raise ValueError
    mean_return = decimals["mean_return"]
    mean_index = decimals["mean_matched_index_return"]
    mean_market = decimals["mean_market_median_return"]
    mean_index_excess = decimals["mean_index_excess"]
    mean_market_excess = decimals["mean_market_median_excess"]
    assert all(
        item is not None
        for item in (
            mean_return,
            mean_index,
            mean_market,
            mean_index_excess,
            mean_market_excess,
        )
    )
    expected_mean_return = canonical_decimal_mean(raw_sum, completed)
    expected_mean_index = canonical_decimal_mean(index_sum, completed)
    expected_mean_market = canonical_decimal_mean(market_sum, completed)
    expected_mean_index_excess = canonical_decimal_mean(
        exact_decimal_sum((raw_sum, index_sum.copy_negate())),
        completed,
    )
    expected_mean_market_excess = canonical_decimal_mean(
        exact_decimal_sum((raw_sum, market_sum.copy_negate())),
        completed,
    )
    expected_ratio = canonical_decimal_mean(
        Decimal(positive_rows),
        completed,
    )
    if (
        mean_return != expected_mean_return
        or mean_index != expected_mean_index
        or mean_market != expected_mean_market
        or mean_index_excess != expected_mean_index_excess
        or mean_market_excess != expected_mean_market_excess
        or ratio != expected_ratio
        or interval != wilson_interval(positive_rows, completed)
    ):
        raise ValueError
    if gross_sum is not None:
        if (
            gross != canonical_decimal_mean(gross_sum, completed)
            or drag
            != canonical_decimal_mean(
                exact_decimal_sum((gross_sum, raw_sum.copy_negate())),
                completed,
            )
        ):
            raise ValueError
    expected_verdict = attribution_verdict(
        completed_rows=completed,
        mean_return=mean_return,
        mean_index_excess=mean_index_excess,
        mean_market_median_excess=mean_market_excess,
    )
    if status == "MARKET_DATA_INCOMPLETE":
        expected_verdict = "INCONCLUSIVE"
    if verdict != expected_verdict:
        raise ValueError
    return decimals


def _status_aggregates_are_valid(
    total: Mapping[str, object],
    parts_by_status: Mapping[str, object],
) -> bool:
    parts = tuple(_mapping(parts_by_status[key]) for key in _STATUSES)
    for field in (
        "eligible_rows",
        "completed_rows",
        "excluded_rows",
        "excluded_missing_coverage",
    ):
        if _nonnegative_int(total[field]) != sum(
            _nonnegative_int(part[field]) for part in parts
        ):
            return False
    total_audit = _audit_totals_values(
        total["audit_totals"],
        require_gross=True,
    )
    part_audits = tuple(
        _audit_totals_values(
            part["audit_totals"],
            require_gross=True,
        )
        for part in parts
    )
    if total_audit["positive_rows"] != sum(
        audit["positive_rows"] for audit in part_audits
    ):
        return False
    for field in (
        "raw_return_sum",
        "matched_index_return_sum",
        "market_median_return_sum",
        "gross_return_sum",
    ):
        total_value = total_audit[field]
        part_values = tuple(audit[field] for audit in part_audits)
        assert isinstance(total_value, Decimal)
        assert all(isinstance(value, Decimal) for value in part_values)
        if total_value != exact_decimal_sum(part_values):
            return False
    return True


def _rank_pairs_are_valid(value: object, *, status: str) -> bool:
    pairs = _mapping(value)
    expected = {"paired_dates", *_PAIR_DECIMAL_FIELDS, "verdict"}
    if not _exact_keys(pairs, expected):
        return False
    paired = _nonnegative_int(pairs["paired_dates"])
    decimals = {
        field: _finite_decimal(pairs[field], optional=True)
        for field in _PAIR_DECIMAL_FIELDS
    }
    verdict = pairs["verdict"]
    if verdict not in _RANK_VERDICTS:
        return False
    if paired == 0:
        return (
            all(item is None for item in decimals.values())
            and verdict == "RANKER_INCONCLUSIVE"
        )
    if any(item is None for item in decimals.values()):
        return False
    win_ratio = decimals["rank_one_win_ratio"]
    assert win_ratio is not None
    if win_ratio < 0 or win_ratio > 1:
        return False
    expected_verdict = "RANKER_INCONCLUSIVE"
    index_difference = decimals["mean_index_excess_difference"]
    market_difference = decimals["mean_market_excess_difference"]
    assert index_difference is not None and market_difference is not None
    if status == "COMPLETE" and paired >= MIN_RANK_PAIR_DATES:
        if index_difference > 0 and market_difference > 0:
            expected_verdict = "RANKER_HEALTHY"
        elif index_difference <= 0 and market_difference <= 0:
            expected_verdict = "RANKER_INVERTED"
        else:
            expected_verdict = "RANKER_MIXED"
    return verdict == expected_verdict


def _rank_correlations_are_valid(value: object) -> bool:
    correlations = _mapping(value)
    expected = {
        "eligible_dates",
        "completed_dates",
        *_CORRELATION_DECIMAL_FIELDS,
    }
    if not _exact_keys(correlations, expected):
        return False
    eligible = _nonnegative_int(correlations["eligible_dates"])
    completed = _nonnegative_int(correlations["completed_dates"])
    if completed > eligible:
        return False
    values = tuple(
        _finite_decimal(correlations[field], optional=True)
        for field in _CORRELATION_DECIMAL_FIELDS
    )
    if completed == 0:
        return all(item is None for item in values)
    return all(item is not None and -1 <= item <= 1 for item in values)


def _coverage_is_valid(value: object, *, status: str) -> bool:
    coverage = _mapping(value)
    expected = {
        "attempted_intervals",
        "completed_intervals",
        "index_endpoint_missing_intervals",
        "market_members_below_threshold_intervals",
        "missing_endpoint_dates",
    }
    if not _exact_keys(coverage, expected):
        return False
    attempted = _nonnegative_int(coverage["attempted_intervals"])
    completed = _nonnegative_int(coverage["completed_intervals"])
    index_missing = _nonnegative_int(
        coverage["index_endpoint_missing_intervals"]
    )
    market_missing = _nonnegative_int(
        coverage["market_members_below_threshold_intervals"]
    )
    raw_dates = coverage["missing_endpoint_dates"]
    if not isinstance(raw_dates, list):
        return False
    dates = tuple(date.fromisoformat(item) for item in raw_dates)
    if tuple(sorted(set(dates))) != dates:
        return False
    if attempted != completed + index_missing + market_missing:
        return False
    missing = index_missing + market_missing
    if status == "COMPLETE":
        return missing == 0 and not dates
    return status == "MARKET_DATA_INCOMPLETE" and missing > 0 and bool(dates)


def _split_is_valid(value: object) -> bool:
    split = _mapping(value)
    if not _exact_keys(split, {"train", "validation", "test"}):
        return False
    parsed: list[tuple[date, ...]] = []
    for key, length in (("train", 378), ("validation", 126), ("test", 126)):
        raw = split[key]
        if not isinstance(raw, list) or len(raw) != length:
            return False
        dates = tuple(date.fromisoformat(item) for item in raw)
        if any(left >= right for left, right in zip(dates, dates[1:])):
            return False
        parsed.append(dates)
    return parsed[0][-1] < parsed[1][0] and parsed[1][-1] < parsed[2][0]


def _variant_is_valid(value: object, *, status: str) -> bool:
    variant = _mapping(value)
    expected = {
        "fold_id",
        "policy_id",
        "selection_mode",
        "actual",
        "actual_by_status",
        "fixed_five_by_rank_band",
        "rank_pairs",
        "rank_correlations",
        "funnel_counts",
    }
    if not _exact_keys(variant, expected):
        return False
    actual = _mapping(variant["actual"])
    _metric_values(actual, status=status, require_gross=True)
    by_status = _mapping(variant["actual_by_status"])
    if not _exact_keys(by_status, set(_STATUSES)):
        return False
    for metric in by_status.values():
        _metric_values(metric, status=status, require_gross=True)
    if not _status_aggregates_are_valid(actual, by_status):
        return False
    bands = _mapping(variant["fixed_five_by_rank_band"])
    if not _exact_keys(bands, set(_RANK_BANDS)):
        return False
    for metric in bands.values():
        _metric_values(metric, status=status, require_gross=False)
        mapped = _mapping(metric)
        if (
            mapped["mean_gross_return"] is not None
            or mapped["mean_after_cost_drag"] is not None
        ):
            return False
    if not _rank_pairs_are_valid(variant["rank_pairs"], status=status):
        return False
    if not _rank_correlations_are_valid(variant["rank_correlations"]):
        return False
    funnel = _mapping(variant["funnel_counts"])
    if not _REQUIRED_FUNNEL_KEYS.issubset(funnel):
        return False
    if any(type(count) is not int or count < 0 for count in funnel.values()):
        return False
    actual_eligible = _nonnegative_int(actual["eligible_rows"])
    actual_completed = _nonnegative_int(actual["completed_rows"])
    if (
        funnel["ACTUAL_ATTRIBUTION_ELIGIBLE"] != actual_eligible
        or funnel["ACTUAL_ATTRIBUTION_COMPLETED"] != actual_completed
        or funnel["ACTUAL_ATTRIBUTION_MISSING_COVERAGE"]
        != actual["excluded_missing_coverage"]
        or actual_eligible
        != actual_completed + funnel["ACTUAL_ATTRIBUTION_MISSING_COVERAGE"]
    ):
        return False
    band_values = tuple(_mapping(bands[band]) for band in _RANK_BANDS)
    fixed_eligible = sum(
        _nonnegative_int(metric["eligible_rows"]) for metric in band_values
    )
    fixed_completed = sum(
        _nonnegative_int(metric["completed_rows"]) for metric in band_values
    )
    fixed_missing = sum(
        _nonnegative_int(metric["excluded_missing_coverage"])
        for metric in band_values
    )
    return (
        funnel["FIXED_FIVE_RANKED_ELIGIBLE"] == fixed_eligible
        and funnel["FIXED_FIVE_COMPLETED"] == fixed_completed
        and funnel["FIXED_FIVE_MISSING_COVERAGE"] == fixed_missing
        and fixed_eligible
        == fixed_completed
        + fixed_missing
        + funnel["FIXED_FIVE_WITHOUT_TRAIN_HORIZON"]
        + funnel["FIXED_FIVE_STOCK_ENDPOINT_MISSING"]
    )


def _content_is_valid(content: Mapping[str, object]) -> bool:
    try:
        expected_keys = {
            "schema",
            "attribution_version",
            "parent_train_identity",
            "parent_research_identity",
            "parent_input_fingerprint",
            "split",
            "market_data_fingerprint",
            "benchmark_definitions",
            "coverage",
            "variants",
            "status",
            "train_only",
            "validation_outcomes_read",
            "test_outcomes_read",
            "promotion_eligible",
            "trade_permission",
        }
        status = content["status"]
        if (
            not _exact_keys(content, expected_keys)
            or content["schema"] != ATTRIBUTION_SCHEMA
            or content["attribution_version"] != ATTRIBUTION_VERSION
            or status not in {"COMPLETE", "MARKET_DATA_INCOMPLETE"}
            or not _digest_is_valid(content["parent_train_identity"])
            or not _digest_is_valid(content["parent_research_identity"])
            or not _digest_is_valid(content["parent_input_fingerprint"])
            or not _digest_is_valid(content["market_data_fingerprint"])
            or content["benchmark_definitions"] != _BENCHMARK_DEFINITIONS
            or content["train_only"] is not True
            or content["validation_outcomes_read"] is not False
            or content["test_outcomes_read"] is not False
            or content["promotion_eligible"] is not False
            or content["trade_permission"] != "NO-TRADE"
            or not _split_is_valid(content["split"])
            or not _coverage_is_valid(content["coverage"], status=status)
            or _contains_forbidden_key(content)
        ):
            return False
        variants = content["variants"]
        if not isinstance(variants, list):
            return False
        expected_registry = tuple(
            (fold_id, policy_id, mode)
            for policy_id in V3_POLICY_IDS
            for mode in V3_SELECTION_MODES
            for fold_id in _FOLDS
        )
        registry = tuple(
            (
                value["fold_id"],
                value["policy_id"],
                value["selection_mode"],
            )
            for value in variants
            if isinstance(value, Mapping)
        )
        if registry != expected_registry:
            return False
        if not all(_variant_is_valid(value, status=status) for value in variants):
            return False
        coverage = _mapping(content["coverage"])
        completed = sum(
            _nonnegative_int(_mapping(value["actual"])["completed_rows"])
            + sum(
                _nonnegative_int(_mapping(item)["completed_rows"])
                for item in _mapping(
                    value["fixed_five_by_rank_band"]
                ).values()
            )
            for value in variants
        )
        failures = sum(
            value["funnel_counts"]["ACTUAL_ATTRIBUTION_MISSING_COVERAGE"]
            + value["funnel_counts"]["FIXED_FIVE_MISSING_COVERAGE"]
            for value in variants
        )
        return (
            coverage["completed_intervals"] == completed
            and coverage["index_endpoint_missing_intervals"]
            + coverage["market_members_below_threshold_intervals"]
            == failures
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


def load_five_day_ranking_v3_attribution(
    path: str | Path,
    *,
    expected_parent_train_identity: str | None = None,
    expected_parent_research_identity: str | None = None,
) -> FiveDayRankingV3AttributionArtifact:
    """Strict-load a canonical aggregate-only train attribution artifact."""

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
        parent_train = payload["parent_train_identity"]
        parent_research = payload["parent_research_identity"]
        if (
            not _digest_is_valid(identity)
            or set(payload) != set(content) | {"artifact_identity"}
            or identity != _sha256(content)
            or target.name
            != f"ranking-v3-train-attribution-{identity}.json"
            or not _content_is_valid(content)
            or (
                expected_parent_train_identity is not None
                and parent_train != expected_parent_train_identity
            )
            or (
                expected_parent_research_identity is not None
                and parent_research != expected_parent_research_identity
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
        raise ValueError("invalid ranking v3 attribution artifact") from None
    return FiveDayRankingV3AttributionArtifact(
        artifact_identity=identity,
        parent_train_identity=parent_train,
        parent_research_identity=parent_research,
        parent_input_fingerprint=payload["parent_input_fingerprint"],
        market_data_fingerprint=payload["market_data_fingerprint"],
        status=payload["status"],
        payload=payload,
    )
