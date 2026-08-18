"""Pure train-only market attribution primitives for five-day ranking V3."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, localcontext
import hashlib
import json
import math
from typing import TYPE_CHECKING, Mapping, Sequence

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6

from .five_day_ranking_v3 import (
    V3_POLICY_IDS,
    V3_RANKING_VERSION,
    V3_SELECTION_MODES,
    V3_TRAIN_SCHEMA,
    five_day_v3_policy_set_hash,
)
from .five_day_return_runtime import FiveDayResearchReview
from .validation import ChronologicalSplit

if TYPE_CHECKING:
    from .five_day_ranking_v3_report import FiveDayRankingV3TrainArtifact


ATTRIBUTION_SCHEMA = "five-day-ranking-v3-train-attribution-v2"
ATTRIBUTION_VERSION = "dual-benchmark-exact-aggregate-v2"
UNIVERSE_VERSION = "sh-sz-main-board-close-median-v1"
MIN_MARKET_MEDIAN_MEMBERS = 1000
MIN_ATTRIBUTION_VERDICT_SAMPLES = 30
MIN_RANK_PAIR_DATES = 15
MIN_RANK_CORRELATION_ROWS = 5
_WILSON_Z = Decimal("1.959963984540054")
_ATTRIBUTION_FOLDS = (
    "train-fold-1",
    "train-fold-2",
    "train-combined",
)
_RANK_BANDS = ("RANK_1", "RANK_2_3", "RANK_4_5", "RANK_6_PLUS")
_RESOLVED_STATUSES = (
    "STOPPED",
    "TIME_EXIT_GAIN",
    "TIME_EXIT_FLAT",
    "TIME_EXIT_LOSS",
)


@dataclass(frozen=True, order=True)
class AttributionInterval:
    start: date
    end: date


@dataclass(frozen=True)
class MarketClosePanel:
    train_dates: tuple[date, ...]
    stock_closes: Mapping[str, Mapping[date, Decimal]]
    index_closes: Mapping[str, Mapping[date, Decimal]]


@dataclass(frozen=True)
class AttributedReturn:
    raw_return: Decimal
    matched_index_return: Decimal
    market_median_return: Decimal
    index_excess: Decimal
    market_median_excess: Decimal
    market_members: int


@dataclass(frozen=True)
class AttributionAuditTotals:
    positive_rows: int
    raw_return_sum: Decimal
    matched_index_return_sum: Decimal
    market_median_return_sum: Decimal
    gross_return_sum: Decimal | None


@dataclass(frozen=True)
class AttributionMetrics:
    eligible_rows: int
    completed_rows: int
    excluded_rows: int
    excluded_missing_coverage: int
    audit_totals: AttributionAuditTotals
    mean_return: Decimal | None
    median_return: Decimal | None
    positive_ratio: Decimal | None
    positive_wilson_interval: tuple[Decimal, Decimal] | None
    mean_matched_index_return: Decimal | None
    median_matched_index_return: Decimal | None
    mean_market_median_return: Decimal | None
    median_market_median_return: Decimal | None
    mean_index_excess: Decimal | None
    median_index_excess: Decimal | None
    mean_market_median_excess: Decimal | None
    median_market_median_excess: Decimal | None
    mean_gross_return: Decimal | None
    mean_after_cost_drag: Decimal | None
    verdict: str


@dataclass(frozen=True)
class RankedAttributedReturn:
    signal_date: date
    rank: int
    value: AttributedReturn


@dataclass(frozen=True)
class RankPairMetrics:
    paired_dates: int
    mean_raw_difference: Decimal | None
    median_raw_difference: Decimal | None
    mean_index_excess_difference: Decimal | None
    median_index_excess_difference: Decimal | None
    mean_market_excess_difference: Decimal | None
    median_market_excess_difference: Decimal | None
    rank_one_win_ratio: Decimal | None
    verdict: str


@dataclass(frozen=True)
class RankCorrelationMetrics:
    eligible_dates: int
    completed_dates: int
    mean_raw_correlation: Decimal | None
    median_raw_correlation: Decimal | None
    mean_index_excess_correlation: Decimal | None
    median_index_excess_correlation: Decimal | None
    mean_market_excess_correlation: Decimal | None
    median_market_excess_correlation: Decimal | None


@dataclass(frozen=True)
class RankOneDiagnosis:
    pairs: RankPairMetrics
    correlations: RankCorrelationMetrics


@dataclass(frozen=True)
class AttributionVariantReview:
    fold_id: str
    policy_id: str
    selection_mode: str
    actual: AttributionMetrics
    actual_by_status: Mapping[str, AttributionMetrics]
    fixed_five_by_rank_band: Mapping[str, AttributionMetrics]
    rank_pairs: RankPairMetrics
    rank_correlations: RankCorrelationMetrics
    funnel_counts: Mapping[str, int]


@dataclass(frozen=True)
class CoverageSummary:
    attempted_intervals: int
    completed_intervals: int
    index_endpoint_missing_intervals: int
    market_members_below_threshold_intervals: int
    missing_endpoint_dates: tuple[date, ...]


@dataclass(frozen=True)
class FiveDayRankingV3AttributionReview:
    schema: str
    attribution_version: str
    parent_train_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    split: ChronologicalSplit
    market_data_fingerprint: str
    coverage: CoverageSummary
    variants: tuple[AttributionVariantReview, ...]
    status: str
    train_only: bool
    validation_outcomes_read: bool
    test_outcomes_read: bool
    promotion_eligible: bool
    trade_permission: str


@dataclass(frozen=True)
class _BenchmarkReturn:
    matched_index_return: Decimal
    market_median_return: Decimal
    market_members: int


@dataclass
class _CoverageAccumulator:
    attempted_intervals: int = 0
    completed_intervals: int = 0
    index_endpoint_missing_intervals: int = 0
    market_members_below_threshold_intervals: int = 0
    missing_endpoint_dates: set[date] = field(default_factory=set)

    def record_success(self) -> None:
        self.attempted_intervals += 1
        self.completed_intervals += 1

    def record_failure(
        self,
        reason: str,
        start: date,
        end: date,
    ) -> None:
        self.attempted_intervals += 1
        self.missing_endpoint_dates.update((start, end))
        if reason == "INDEX_ENDPOINT_MISSING":
            self.index_endpoint_missing_intervals += 1
            return
        if reason == "MARKET_MEMBERS_BELOW_1000":
            self.market_members_below_threshold_intervals += 1
            return
        raise ValueError("unsupported market coverage reason")

    def freeze(self) -> CoverageSummary:
        return CoverageSummary(
            attempted_intervals=self.attempted_intervals,
            completed_intervals=self.completed_intervals,
            index_endpoint_missing_intervals=(
                self.index_endpoint_missing_intervals
            ),
            market_members_below_threshold_intervals=(
                self.market_members_below_threshold_intervals
            ),
            missing_endpoint_dates=tuple(sorted(self.missing_endpoint_dates)),
        )


class MarketCoverageIncomplete(ValueError):
    """A required benchmark interval cannot satisfy frozen coverage."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def matched_index_id(code: str) -> str:
    """Return the frozen benchmark index for a supported A-share board."""

    normalized = normalize_code6(code)
    if normalized.startswith(("600", "601", "603", "605")):
        return "sh.000001"
    if normalized.startswith(("000", "001", "002", "003")):
        return "sz.399001"
    if normalized.startswith("688"):
        return "sh.000688"
    raise ValueError(f"unsupported attribution board: {normalized}")


def _validate_train_dates(train_dates: Sequence[date]) -> tuple[date, ...]:
    dates = tuple(train_dates)
    if any(current >= following for current, following in zip(dates, dates[1:])):
        raise ValueError("train calendar must be strictly increasing")
    return dates


def fifth_subsequent_train_date(
    signal_date: date,
    train_dates: Sequence[date],
) -> date | None:
    """Return the fifth later train session without crossing its boundary."""

    dates = _validate_train_dates(train_dates)
    try:
        signal_index = dates.index(signal_date)
    except ValueError as exc:
        raise ValueError("signal date is not in train calendar") from exc
    target_index = signal_index + 5
    return dates[target_index] if target_index < len(dates) else None


def simple_return(start: Decimal, end: Decimal) -> Decimal:
    """Calculate an exact close-to-close simple return."""

    if (
        not start.is_finite()
        or not end.is_finite()
        or start <= 0
        or end <= 0
    ):
        raise ValueError("return endpoints must be finite positive close values")
    with localcontext() as context:
        context.prec = 28
        return end / start - Decimal("1")


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = tuple(sorted(values))
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    with localcontext() as context:
        context.prec = 28
        return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def exact_decimal_sum(values: Sequence[Decimal]) -> Decimal:
    """Add finite decimals exactly without ambient-context rounding."""

    finite = tuple(values)
    if any(not value.is_finite() for value in finite):
        raise ValueError("exact decimal values must be finite")
    if not finite:
        return Decimal("0")
    exponent = min(value.as_tuple().exponent for value in finite)
    coefficient_sum = 0
    for value in finite:
        item = value.as_tuple()
        coefficient = int(
            "".join(str(digit) for digit in item.digits) or "0"
        )
        if item.sign:
            coefficient = -coefficient
        coefficient_sum += coefficient * (10 ** (item.exponent - exponent))
    sign = int(coefficient_sum < 0)
    digits = tuple(
        int(character) for character in str(abs(coefficient_sum))
    )
    return Decimal((sign, digits, exponent))


def canonical_decimal_mean(total: Decimal, count: int) -> Decimal:
    """Divide an exact total under the frozen aggregate precision."""

    if not total.is_finite() or count <= 0:
        raise ValueError(
            "canonical decimal mean requires finite total and positive count"
        )
    with localcontext() as context:
        context.prec = 28
        return total / Decimal(count)


def _mean(values: Sequence[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = 28
        return sum(values, Decimal("0")) / Decimal(len(values))


def _wilson_interval(successes: int, total: int) -> tuple[Decimal, Decimal]:
    with localcontext() as context:
        context.prec = 28
        n = Decimal(total)
        rate = Decimal(successes) / n
        z_squared = _WILSON_Z * _WILSON_Z
        denominator = Decimal("1") + z_squared / n
        centre = rate + z_squared / (Decimal("2") * n)
        variance = (
            rate * (Decimal("1") - rate) / n
            + z_squared / (Decimal("4") * n * n)
        )
        margin = _WILSON_Z * Decimal(str(math.sqrt(float(variance))))
        lower = max(Decimal("0"), (centre - margin) / denominator)
        upper = min(Decimal("1"), (centre + margin) / denominator)
        if successes == 0:
            lower = Decimal("0")
        if successes == total:
            upper = Decimal("1")
        return lower, upper


def attribution_verdict(
    *,
    completed_rows: int,
    mean_return: Decimal | None,
    mean_index_excess: Decimal | None,
    mean_market_median_excess: Decimal | None,
) -> str:
    """Classify negative performance without granting trading permission."""

    if (
        completed_rows < MIN_ATTRIBUTION_VERDICT_SAMPLES
        or mean_return is None
        or mean_index_excess is None
        or mean_market_median_excess is None
        or mean_return >= 0
    ):
        return "INCONCLUSIVE"
    if mean_index_excess > 0 and mean_market_median_excess > 0:
        return "MARKET_DRAG"
    if mean_index_excess <= 0 and mean_market_median_excess <= 0:
        return "STRATEGY_DRAG"
    return "MIXED"


def summarize_attributed_returns(
    rows: Sequence[AttributedReturn],
    *,
    eligible_rows: int,
    excluded_missing_coverage: int,
    gross_returns: Sequence[Decimal] | None = None,
) -> AttributionMetrics:
    """Aggregate attributed returns under frozen count and verdict rules."""

    completed_rows = len(rows)
    if eligible_rows < 0 or excluded_missing_coverage < 0:
        raise ValueError("attribution counts must be non-negative")
    if completed_rows > eligible_rows:
        raise ValueError("completed rows cannot exceed eligible rows")
    excluded_rows = eligible_rows - completed_rows
    if excluded_missing_coverage > excluded_rows:
        raise ValueError("missing coverage cannot exceed excluded rows")
    if gross_returns is not None and len(gross_returns) != completed_rows:
        raise ValueError("gross returns must align with completed rows")

    decimal_fields = tuple(
        value
        for row in rows
        for value in (
            row.raw_return,
            row.matched_index_return,
            row.market_median_return,
            row.index_excess,
            row.market_median_excess,
        )
    )
    if any(not value.is_finite() for value in decimal_fields):
        raise ValueError("all attribution values must be finite attribution values")
    if gross_returns is not None and any(
        not value.is_finite() for value in gross_returns
    ):
        raise ValueError("all attribution values must be finite attribution values")
    if not rows:
        return AttributionMetrics(
            eligible_rows=eligible_rows,
            completed_rows=0,
            excluded_rows=excluded_rows,
            excluded_missing_coverage=excluded_missing_coverage,
            audit_totals=AttributionAuditTotals(
                positive_rows=0,
                raw_return_sum=Decimal("0"),
                matched_index_return_sum=Decimal("0"),
                market_median_return_sum=Decimal("0"),
                gross_return_sum=(
                    Decimal("0") if gross_returns is not None else None
                ),
            ),
            mean_return=None,
            median_return=None,
            positive_ratio=None,
            positive_wilson_interval=None,
            mean_matched_index_return=None,
            median_matched_index_return=None,
            mean_market_median_return=None,
            median_market_median_return=None,
            mean_index_excess=None,
            median_index_excess=None,
            mean_market_median_excess=None,
            median_market_median_excess=None,
            mean_gross_return=None,
            mean_after_cost_drag=None,
            verdict="INCONCLUSIVE",
        )

    raw_returns = tuple(row.raw_return for row in rows)
    matched_index_returns = tuple(row.matched_index_return for row in rows)
    market_median_returns = tuple(row.market_median_return for row in rows)
    index_excesses = tuple(row.index_excess for row in rows)
    market_median_excesses = tuple(row.market_median_excess for row in rows)
    positive_count = sum(value > 0 for value in raw_returns)
    raw_sum = exact_decimal_sum(raw_returns)
    index_sum = exact_decimal_sum(matched_index_returns)
    market_sum = exact_decimal_sum(market_median_returns)
    gross_sum = (
        exact_decimal_sum(tuple(gross_returns))
        if gross_returns is not None
        else None
    )
    audit_totals = AttributionAuditTotals(
        positive_rows=positive_count,
        raw_return_sum=raw_sum,
        matched_index_return_sum=index_sum,
        market_median_return_sum=market_sum,
        gross_return_sum=gross_sum,
    )
    mean_return = canonical_decimal_mean(raw_sum, completed_rows)
    mean_index_excess = canonical_decimal_mean(
        exact_decimal_sum((raw_sum, index_sum.copy_negate())),
        completed_rows,
    )
    mean_market_median_excess = canonical_decimal_mean(
        exact_decimal_sum((raw_sum, market_sum.copy_negate())),
        completed_rows,
    )

    mean_gross_return: Decimal | None = None
    mean_after_cost_drag: Decimal | None = None
    if gross_sum is not None:
        mean_gross_return = canonical_decimal_mean(gross_sum, completed_rows)
        mean_after_cost_drag = canonical_decimal_mean(
            exact_decimal_sum((gross_sum, raw_sum.copy_negate())),
            completed_rows,
        )
    positive_ratio = canonical_decimal_mean(
        Decimal(positive_count),
        completed_rows,
    )

    return AttributionMetrics(
        eligible_rows=eligible_rows,
        completed_rows=completed_rows,
        excluded_rows=excluded_rows,
        excluded_missing_coverage=excluded_missing_coverage,
        audit_totals=audit_totals,
        mean_return=mean_return,
        median_return=_median(raw_returns),
        positive_ratio=positive_ratio,
        positive_wilson_interval=_wilson_interval(
            positive_count,
            completed_rows,
        ),
        mean_matched_index_return=canonical_decimal_mean(
            index_sum,
            completed_rows,
        ),
        median_matched_index_return=_median(matched_index_returns),
        mean_market_median_return=canonical_decimal_mean(
            market_sum,
            completed_rows,
        ),
        median_market_median_return=_median(market_median_returns),
        mean_index_excess=mean_index_excess,
        median_index_excess=_median(index_excesses),
        mean_market_median_excess=mean_market_median_excess,
        median_market_median_excess=_median(market_median_excesses),
        mean_gross_return=mean_gross_return,
        mean_after_cost_drag=mean_after_cost_drag,
        verdict=attribution_verdict(
            completed_rows=completed_rows,
            mean_return=mean_return,
            mean_index_excess=mean_index_excess,
            mean_market_median_excess=mean_market_median_excess,
        ),
    )


def _rank_pair_verdict(
    paired_dates: int,
    mean_index_excess_difference: Decimal | None,
    mean_market_excess_difference: Decimal | None,
) -> str:
    if (
        paired_dates < MIN_RANK_PAIR_DATES
        or mean_index_excess_difference is None
        or mean_market_excess_difference is None
    ):
        return "RANKER_INCONCLUSIVE"
    if (
        mean_index_excess_difference > 0
        and mean_market_excess_difference > 0
    ):
        return "RANKER_HEALTHY"
    if (
        mean_index_excess_difference <= 0
        and mean_market_excess_difference <= 0
    ):
        return "RANKER_INVERTED"
    return "RANKER_MIXED"


def _average_ranks(values: Sequence[Decimal]) -> tuple[Decimal, ...]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [Decimal("0")] * len(values)
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        with localcontext() as context:
            context.prec = 28
            average_rank = (
                Decimal(start + 1) + Decimal(end)
            ) / Decimal("2")
        for position in range(start, end):
            ranks[indexed[position][0]] = average_rank
        start = end
    return tuple(ranks)


def _pearson_correlation(
    left: Sequence[Decimal],
    right: Sequence[Decimal],
) -> Decimal | None:
    left_mean = _mean(left)
    right_mean = _mean(right)
    with localcontext() as context:
        context.prec = 28
        numerator = sum(
            (
                (left_value - left_mean) * (right_value - right_mean)
                for left_value, right_value in zip(left, right)
            ),
            Decimal("0"),
        )
        left_squared = sum(
            ((value - left_mean) ** 2 for value in left),
            Decimal("0"),
        )
        right_squared = sum(
            ((value - right_mean) ** 2 for value in right),
            Decimal("0"),
        )
        if left_squared == 0 or right_squared == 0:
            return None
        return numerator / (left_squared * right_squared).sqrt()


def _spearman_correlation(
    ordinal_ranks: Sequence[int],
    target: Sequence[Decimal],
) -> Decimal | None:
    negative_ordinal = tuple(Decimal(-rank) for rank in ordinal_ranks)
    return _pearson_correlation(
        _average_ranks(negative_ordinal),
        _average_ranks(target),
    )


def _optional_mean(values: Sequence[Decimal]) -> Decimal | None:
    return _mean(values) if values else None


def _optional_median(values: Sequence[Decimal]) -> Decimal | None:
    return _median(values) if values else None


def diagnose_rank_one(
    rows: Sequence[RankedAttributedReturn],
) -> RankOneDiagnosis:
    """Diagnose Rank-1 with same-date pairs and aggregate correlations."""

    grouped: dict[date, dict[int, AttributedReturn]] = {}
    for row in rows:
        dated = grouped.setdefault(row.signal_date, {})
        if row.rank <= 0 or row.rank in dated:
            raise ValueError(
                "ordinal ranks must be positive and unique within date"
            )
        dated[row.rank] = row.value

    raw_differences: list[Decimal] = []
    index_differences: list[Decimal] = []
    market_differences: list[Decimal] = []
    raw_correlations: list[Decimal] = []
    index_correlations: list[Decimal] = []
    market_correlations: list[Decimal] = []
    eligible_correlation_dates = 0

    for signal_date in sorted(grouped):
        dated = grouped[signal_date]
        rank_one = dated.get(1)
        lower = tuple(
            dated[rank]
            for rank in (2, 3)
            if rank in dated
        )
        if rank_one is not None and lower:
            raw_differences.append(
                rank_one.raw_return
                - _median(tuple(value.raw_return for value in lower))
            )
            index_differences.append(
                rank_one.index_excess
                - _median(tuple(value.index_excess for value in lower))
            )
            market_differences.append(
                rank_one.market_median_excess
                - _median(
                    tuple(value.market_median_excess for value in lower)
                )
            )

        if len(dated) < MIN_RANK_CORRELATION_ROWS:
            continue
        eligible_correlation_dates += 1
        ordered = tuple(sorted(dated.items()))
        ordinal_ranks = tuple(rank for rank, _ in ordered)
        raw_correlation = _spearman_correlation(
            ordinal_ranks,
            tuple(value.raw_return for _, value in ordered),
        )
        index_correlation = _spearman_correlation(
            ordinal_ranks,
            tuple(value.index_excess for _, value in ordered),
        )
        market_correlation = _spearman_correlation(
            ordinal_ranks,
            tuple(value.market_median_excess for _, value in ordered),
        )
        if (
            raw_correlation is None
            or index_correlation is None
            or market_correlation is None
        ):
            continue
        raw_correlations.append(raw_correlation)
        index_correlations.append(index_correlation)
        market_correlations.append(market_correlation)

    paired_dates = len(raw_differences)
    mean_index_difference = _optional_mean(index_differences)
    mean_market_difference = _optional_mean(market_differences)
    rank_one_win_ratio: Decimal | None = None
    if paired_dates:
        with localcontext() as context:
            context.prec = 28
            rank_one_win_ratio = Decimal(
                sum(value > 0 for value in raw_differences)
            ) / Decimal(paired_dates)

    return RankOneDiagnosis(
        pairs=RankPairMetrics(
            paired_dates=paired_dates,
            mean_raw_difference=_optional_mean(raw_differences),
            median_raw_difference=_optional_median(raw_differences),
            mean_index_excess_difference=mean_index_difference,
            median_index_excess_difference=_optional_median(index_differences),
            mean_market_excess_difference=mean_market_difference,
            median_market_excess_difference=_optional_median(market_differences),
            rank_one_win_ratio=rank_one_win_ratio,
            verdict=_rank_pair_verdict(
                paired_dates,
                mean_index_difference,
                mean_market_difference,
            ),
        ),
        correlations=RankCorrelationMetrics(
            eligible_dates=eligible_correlation_dates,
            completed_dates=len(raw_correlations),
            mean_raw_correlation=_optional_mean(raw_correlations),
            median_raw_correlation=_optional_median(raw_correlations),
            mean_index_excess_correlation=_optional_mean(index_correlations),
            median_index_excess_correlation=_optional_median(
                index_correlations
            ),
            mean_market_excess_correlation=_optional_mean(
                market_correlations
            ),
            median_market_excess_correlation=_optional_median(
                market_correlations
            ),
        ),
    )


def _benchmark_interval(
    code: str,
    start: date,
    end: date,
    panel: MarketClosePanel,
) -> _BenchmarkReturn:
    train_dates = _validate_train_dates(panel.train_dates)
    if start not in train_dates or end not in train_dates or start > end:
        raise ValueError("interval endpoints must be train dates in order")
    normalized_code = normalize_code6(code)
    index_id = matched_index_id(normalized_code)
    index_series = panel.index_closes.get(index_id)
    if index_series is None or start not in index_series or end not in index_series:
        raise MarketCoverageIncomplete("INDEX_ENDPOINT_MISSING")
    try:
        index_return = simple_return(index_series[start], index_series[end])
    except ValueError as exc:
        raise MarketCoverageIncomplete("INDEX_ENDPOINT_MISSING") from exc

    market_returns: list[Decimal] = []
    for member_code, member_series in panel.stock_closes.items():
        if not is_sh_sz_main_board_code(member_code):
            continue
        if start not in member_series or end not in member_series:
            continue
        try:
            market_returns.append(
                simple_return(member_series[start], member_series[end])
            )
        except ValueError:
            continue
    if len(market_returns) < MIN_MARKET_MEDIAN_MEMBERS:
        raise MarketCoverageIncomplete("MARKET_MEMBERS_BELOW_1000")

    return _BenchmarkReturn(
        matched_index_return=index_return,
        market_median_return=_median(market_returns),
        market_members=len(market_returns),
    )


def _attribute_raw_return(
    raw_return: Decimal,
    benchmark: _BenchmarkReturn,
) -> AttributedReturn:
    with localcontext() as context:
        context.prec = 28
        return AttributedReturn(
            raw_return=raw_return,
            matched_index_return=benchmark.matched_index_return,
            market_median_return=benchmark.market_median_return,
            index_excess=raw_return - benchmark.matched_index_return,
            market_median_excess=(
                raw_return - benchmark.market_median_return
            ),
            market_members=benchmark.market_members,
        )


def attribute_interval(
    code: str,
    start: date,
    end: date,
    panel: MarketClosePanel,
) -> AttributedReturn:
    """Attribute one stock close return to matched and universe benchmarks."""

    train_dates = _validate_train_dates(panel.train_dates)
    if start not in train_dates or end not in train_dates or start > end:
        raise ValueError("interval endpoints must be train dates in order")
    normalized_code = normalize_code6(code)
    stock_series = panel.stock_closes.get(normalized_code)
    if stock_series is None or start not in stock_series or end not in stock_series:
        raise ValueError("stock interval endpoints are missing")
    raw_return = simple_return(stock_series[start], stock_series[end])
    benchmark = _benchmark_interval(normalized_code, start, end, panel)

    return _attribute_raw_return(raw_return, benchmark)


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _split_content(split: ChronologicalSplit) -> dict[str, list[str]]:
    return {
        "train": [value.isoformat() for value in split.train],
        "validation": [value.isoformat() for value in split.validation],
        "test": [value.isoformat() for value in split.test],
    }


def _validate_train_artifact(
    train_artifact: FiveDayRankingV3TrainArtifact,
) -> tuple[Mapping[str, object], ...]:
    payload = train_artifact.payload
    if not isinstance(payload, Mapping):
        raise ValueError("train artifact safety mismatch")
    content = {
        key: value
        for key, value in payload.items()
        if key != "artifact_identity"
    }
    identity = str(payload.get("artifact_identity", ""))
    variants = payload.get("variants")
    expected_registry = tuple(
        (fold_id, policy_id, selection_mode)
        for policy_id in V3_POLICY_IDS
        for selection_mode in V3_SELECTION_MODES
        for fold_id in _ATTRIBUTION_FOLDS
    )
    try:
        if not isinstance(variants, list):
            raise ValueError
        actual_registry = tuple(
            (
                str(value["fold_id"]),
                str(value["policy_id"]),
                str(value["selection_mode"]),
            )
            for value in variants
        )
        if any(not isinstance(value.get("segment"), Mapping) for value in variants):
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("train artifact safety mismatch") from None
    if (
        len(identity) != 64
        or any(value not in "0123456789abcdef" for value in identity)
        or identity != train_artifact.artifact_identity
        or identity != _canonical_hash(content)
        or payload.get("schema") != V3_TRAIN_SCHEMA
        or payload.get("ranking_version") != V3_RANKING_VERSION
        or payload.get("policy_set_hash") != five_day_v3_policy_set_hash()
        or train_artifact.policy_set_hash != five_day_v3_policy_set_hash()
        or payload.get("split") != _split_content(train_artifact.split)
        or actual_registry != expected_registry
        or payload.get("validation_outcomes_read") is not False
        or payload.get("test_outcomes_read") is not False
        or payload.get("promotion_eligible") is not False
        or payload.get("trade_permission") != "NO-TRADE"
    ):
        raise ValueError("train artifact safety mismatch")
    return tuple(variants)


def _observation_key(value: object) -> tuple[date, str, str, str]:
    plan = value.plan
    return (
        plan.candidate.signal_date,
        normalize_code6(plan.candidate.code),
        plan.structure_id,
        plan.profile.profile_id,
    )


def _plan_key_from_content(value: object) -> tuple[date, str, str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("invalid V3 plan key")
    try:
        signal_date = date.fromisoformat(str(value["signal_date"]))
        code = normalize_code6(str(value["code"]))
        structure_id = str(value["structure_id"])
        profile_id = str(value["profile_id"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid V3 plan key") from None
    if not code or not structure_id or not profile_id:
        raise ValueError("invalid V3 plan key")
    return signal_date, code, structure_id, profile_id


def _rank_band(rank: int) -> str:
    if rank <= 0:
        raise ValueError("ranked plan rank must be positive")
    if rank == 1:
        return "RANK_1"
    if rank <= 3:
        return "RANK_2_3"
    if rank <= 5:
        return "RANK_4_5"
    return "RANK_6_PLUS"


def _market_data_fingerprint(
    panel: MarketClosePanel,
    *,
    endpoint_dates: set[date],
    target_codes: set[str],
    index_ids: set[str],
) -> str:
    stock_rows = sorted(
        (
            normalize_code6(code),
            endpoint.isoformat(),
            str(close),
        )
        for code, series in panel.stock_closes.items()
        if is_sh_sz_main_board_code(code)
        or normalize_code6(code) in target_codes
        for endpoint, close in series.items()
        if endpoint in endpoint_dates
    )
    index_rows = sorted(
        (index_id, endpoint.isoformat(), str(close))
        for index_id, series in panel.index_closes.items()
        if index_id in index_ids
        for endpoint, close in series.items()
        if endpoint in endpoint_dates
    )
    return _canonical_hash(
        {
            "train_dates": [value.isoformat() for value in panel.train_dates],
            "benchmark_mapping": {
                "000|001|002|003": "sz.399001",
                "600|601|603|605": "sh.000001",
                "688": "sh.000688",
            },
            "universe_version": UNIVERSE_VERSION,
            "minimum_market_members": MIN_MARKET_MEDIAN_MEMBERS,
            "required_endpoint_dates": [
                value.isoformat() for value in sorted(endpoint_dates)
            ],
            "required_target_codes": sorted(target_codes),
            "required_index_ids": sorted(index_ids),
            "stock_closes": stock_rows,
            "index_closes": index_rows,
        }
    )


def _force_metrics_inconclusive(value: AttributionMetrics) -> AttributionMetrics:
    return replace(value, verdict="INCONCLUSIVE")


def _force_variant_inconclusive(
    value: AttributionVariantReview,
) -> AttributionVariantReview:
    return replace(
        value,
        actual=_force_metrics_inconclusive(value.actual),
        actual_by_status={
            key: _force_metrics_inconclusive(item)
            for key, item in value.actual_by_status.items()
        },
        fixed_five_by_rank_band={
            key: _force_metrics_inconclusive(item)
            for key, item in value.fixed_five_by_rank_band.items()
        },
        rank_pairs=replace(
            value.rank_pairs,
            verdict="RANKER_INCONCLUSIVE",
        ),
    )


def build_five_day_ranking_v3_attribution_review(
    train_artifact: FiveDayRankingV3TrainArtifact,
    research: FiveDayResearchReview,
    *,
    parent_research_identity: str,
    market_panel: MarketClosePanel,
) -> FiveDayRankingV3AttributionReview:
    """Build one aggregate-only attribution review from verified train data."""

    payload = train_artifact.payload
    if (
        len(parent_research_identity) != 64
        or any(
            value not in "0123456789abcdef"
            for value in parent_research_identity
        )
        or parent_research_identity != train_artifact.parent_research_identity
        or not isinstance(payload, Mapping)
        or parent_research_identity
        != str(payload.get("parent_research_identity", ""))
    ):
        raise ValueError("parent research identity mismatch")
    if (
        research.input_fingerprint
        != train_artifact.parent_input_fingerprint
        or research.input_fingerprint
        != str(payload.get("parent_input_fingerprint", ""))
    ):
        raise ValueError("parent input fingerprint mismatch")
    if (
        research.split != train_artifact.split
        or not research.point_in_time_complete
        or research.test_outcomes_read
    ):
        raise ValueError("parent research safety mismatch")

    variants_content = _validate_train_artifact(train_artifact)
    train_dates = tuple(train_artifact.split.train)
    train_set = frozenset(train_dates)
    if tuple(market_panel.train_dates) != train_dates:
        raise ValueError("market panel train calendar mismatch")

    observations: dict[tuple[date, str, str, str], object] = {}
    for observation in research.observations:
        key = _observation_key(observation)
        if key in observations:
            raise ValueError("duplicate parent observation key")
        observations[key] = observation

    def mapped_observation(value: object) -> tuple[tuple[date, str, str, str], object]:
        key = _plan_key_from_content(value)
        if key[0] not in train_set:
            raise ValueError("plan key is outside train split")
        observation = observations.get(key)
        if observation is None:
            raise ValueError("plan key has no parent observation")
        return key, observation

    coverage = _CoverageAccumulator()
    endpoint_dates: set[date] = set()
    target_codes: set[str] = set()
    index_ids: set[str] = set()
    benchmark_cache: dict[
        tuple[str, date, date],
        _BenchmarkReturn | str,
    ] = {}

    def benchmark_for(
        code: str,
        start: date,
        end: date,
    ) -> _BenchmarkReturn:
        normalized = normalize_code6(code)
        index_id = matched_index_id(normalized)
        endpoint_dates.update((start, end))
        target_codes.add(normalized)
        index_ids.add(index_id)
        cache_key = (index_id, start, end)
        cached = benchmark_cache.get(cache_key)
        if isinstance(cached, str):
            coverage.record_failure(cached, start, end)
            raise MarketCoverageIncomplete(cached)
        if cached is not None:
            coverage.record_success()
            return cached
        try:
            benchmark = _benchmark_interval(
                normalized,
                start,
                end,
                market_panel,
            )
        except MarketCoverageIncomplete as exc:
            benchmark_cache[cache_key] = exc.reason
            coverage.record_failure(exc.reason, start, end)
            raise
        benchmark_cache[cache_key] = benchmark
        coverage.record_success()
        return benchmark

    variant_reviews: list[AttributionVariantReview] = []
    for variant_content in variants_content:
        segment = variant_content["segment"]
        if not isinstance(segment, Mapping):
            raise ValueError("train artifact safety mismatch")
        admitted_content = segment.get("admitted_trade_keys")
        ranked_content = segment.get("ranked_plan_keys")
        raw_funnel = segment.get("funnel_counts")
        if (
            not isinstance(admitted_content, list)
            or not isinstance(ranked_content, list)
            or not isinstance(raw_funnel, Mapping)
        ):
            raise ValueError("train artifact safety mismatch")

        funnel_counts: dict[str, int] = {}
        for key, value in raw_funnel.items():
            if type(value) is not int or value < 0:
                raise ValueError("train artifact safety mismatch")
            funnel_counts[str(key)] = value

        actual_rows: list[AttributedReturn] = []
        actual_gross: list[Decimal] = []
        actual_missing_coverage = 0
        actual_by_status_rows = {
            status: [] for status in _RESOLVED_STATUSES
        }
        actual_by_status_gross = {
            status: [] for status in _RESOLVED_STATUSES
        }
        actual_by_status_eligible = {
            status: 0 for status in _RESOLVED_STATUSES
        }
        actual_by_status_missing = {
            status: 0 for status in _RESOLVED_STATUSES
        }
        admitted_seen: set[tuple[date, str, str, str]] = set()
        for item in admitted_content:
            key, observation = mapped_observation(item)
            if key in admitted_seen:
                raise ValueError("duplicate admitted plan key")
            admitted_seen.add(key)
            trade = observation.trade
            if (
                trade.status not in actual_by_status_rows
                or trade.entry_date is None
                or trade.entry_price is None
                or trade.exit is None
                or trade.net_return is None
                or not trade.net_return.is_finite()
            ):
                raise ValueError("admitted trade is not completed")
            status = trade.status
            actual_by_status_eligible[status] += 1
            gross_return = simple_return(trade.entry_price, trade.exit.price)
            try:
                benchmark = benchmark_for(
                    key[1],
                    trade.entry_date,
                    trade.exit.actual_exit_date,
                )
            except MarketCoverageIncomplete:
                actual_missing_coverage += 1
                actual_by_status_missing[status] += 1
                continue
            attributed = _attribute_raw_return(trade.net_return, benchmark)
            actual_rows.append(attributed)
            actual_gross.append(gross_return)
            actual_by_status_rows[status].append(attributed)
            actual_by_status_gross[status].append(gross_return)

        actual_metrics = summarize_attributed_returns(
            actual_rows,
            eligible_rows=len(admitted_content),
            excluded_missing_coverage=actual_missing_coverage,
            gross_returns=actual_gross,
        )
        actual_by_status = {
            status: summarize_attributed_returns(
                actual_by_status_rows[status],
                eligible_rows=actual_by_status_eligible[status],
                excluded_missing_coverage=actual_by_status_missing[status],
                gross_returns=actual_by_status_gross[status],
            )
            for status in _RESOLVED_STATUSES
        }

        fixed_rows = {band: [] for band in _RANK_BANDS}
        fixed_eligible = {band: 0 for band in _RANK_BANDS}
        fixed_missing_coverage = {band: 0 for band in _RANK_BANDS}
        ranked_for_diagnosis: list[RankedAttributedReturn] = []
        without_horizon = 0
        stock_endpoint_missing = 0
        ranked_seen: set[tuple[date, str, str, str]] = set()
        for item in ranked_content:
            key, _ = mapped_observation(item)
            if key in ranked_seen:
                raise ValueError("duplicate ranked plan key")
            ranked_seen.add(key)
            if not isinstance(item, Mapping) or type(item.get("rank")) is not int:
                raise ValueError("invalid ranked plan key")
            rank = int(item["rank"])
            band = _rank_band(rank)
            fixed_eligible[band] += 1
            end = fifth_subsequent_train_date(key[0], train_dates)
            if end is None:
                without_horizon += 1
                continue
            target_codes.add(key[1])
            endpoint_dates.update((key[0], end))
            series = market_panel.stock_closes.get(key[1])
            if series is None or key[0] not in series or end not in series:
                stock_endpoint_missing += 1
                continue
            try:
                raw_return = simple_return(series[key[0]], series[end])
            except ValueError:
                stock_endpoint_missing += 1
                continue
            try:
                benchmark = benchmark_for(key[1], key[0], end)
            except MarketCoverageIncomplete:
                fixed_missing_coverage[band] += 1
                continue
            attributed = _attribute_raw_return(raw_return, benchmark)
            fixed_rows[band].append(attributed)
            ranked_for_diagnosis.append(
                RankedAttributedReturn(
                    signal_date=key[0],
                    rank=rank,
                    value=attributed,
                )
            )

        fixed_metrics = {
            band: summarize_attributed_returns(
                fixed_rows[band],
                eligible_rows=fixed_eligible[band],
                excluded_missing_coverage=fixed_missing_coverage[band],
            )
            for band in _RANK_BANDS
        }
        diagnosis = diagnose_rank_one(ranked_for_diagnosis)
        funnel_counts.update(
            {
                "ACTUAL_ATTRIBUTION_ELIGIBLE": len(admitted_content),
                "ACTUAL_ATTRIBUTION_COMPLETED": len(actual_rows),
                "ACTUAL_ATTRIBUTION_MISSING_COVERAGE": (
                    actual_missing_coverage
                ),
                "FIXED_FIVE_RANKED_ELIGIBLE": len(ranked_content),
                "FIXED_FIVE_COMPLETED": sum(
                    len(values) for values in fixed_rows.values()
                ),
                "FIXED_FIVE_MISSING_COVERAGE": sum(
                    fixed_missing_coverage.values()
                ),
                "FIXED_FIVE_WITHOUT_TRAIN_HORIZON": without_horizon,
                "FIXED_FIVE_STOCK_ENDPOINT_MISSING": (
                    stock_endpoint_missing
                ),
            }
        )
        variant_reviews.append(
            AttributionVariantReview(
                fold_id=str(variant_content["fold_id"]),
                policy_id=str(variant_content["policy_id"]),
                selection_mode=str(variant_content["selection_mode"]),
                actual=actual_metrics,
                actual_by_status=actual_by_status,
                fixed_five_by_rank_band=fixed_metrics,
                rank_pairs=diagnosis.pairs,
                rank_correlations=diagnosis.correlations,
                funnel_counts=dict(sorted(funnel_counts.items())),
            )
        )

    frozen_coverage = coverage.freeze()
    incomplete = (
        frozen_coverage.index_endpoint_missing_intervals > 0
        or frozen_coverage.market_members_below_threshold_intervals > 0
    )
    variants = tuple(variant_reviews)
    if incomplete:
        variants = tuple(
            _force_variant_inconclusive(value) for value in variants
        )
    return FiveDayRankingV3AttributionReview(
        schema=ATTRIBUTION_SCHEMA,
        attribution_version=ATTRIBUTION_VERSION,
        parent_train_identity=train_artifact.artifact_identity,
        parent_research_identity=parent_research_identity,
        parent_input_fingerprint=research.input_fingerprint,
        split=train_artifact.split,
        market_data_fingerprint=_market_data_fingerprint(
            market_panel,
            endpoint_dates=endpoint_dates,
            target_codes=target_codes,
            index_ids=index_ids,
        ),
        coverage=frozen_coverage,
        variants=variants,
        status=("MARKET_DATA_INCOMPLETE" if incomplete else "COMPLETE"),
        train_only=True,
        validation_outcomes_read=False,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )
