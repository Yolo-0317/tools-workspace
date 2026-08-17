"""Pure train-only market attribution primitives for five-day ranking V3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
import math
from typing import Mapping, Sequence

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6


ATTRIBUTION_SCHEMA = "five-day-ranking-v3-train-attribution-v1"
ATTRIBUTION_VERSION = "dual-benchmark-train-attribution-v1"
UNIVERSE_VERSION = "sh-sz-main-board-close-median-v1"
MIN_MARKET_MEDIAN_MEMBERS = 1000
MIN_ATTRIBUTION_VERDICT_SAMPLES = 30
MIN_RANK_PAIR_DATES = 15
MIN_RANK_CORRELATION_ROWS = 5
_WILSON_Z = Decimal("1.959963984540054")


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
class AttributionMetrics:
    eligible_rows: int
    completed_rows: int
    excluded_rows: int
    excluded_missing_coverage: int
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
        return (
            max(Decimal("0"), (centre - margin) / denominator),
            min(Decimal("1"), (centre + margin) / denominator),
        )


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
    mean_return = _mean(raw_returns)
    mean_index_excess = _mean(index_excesses)
    mean_market_median_excess = _mean(market_median_excesses)

    mean_gross_return: Decimal | None = None
    mean_after_cost_drag: Decimal | None = None
    if gross_returns is not None:
        gross_values = tuple(gross_returns)
        mean_gross_return = _mean(gross_values)
        mean_after_cost_drag = _mean(
            tuple(
                gross_value - raw_value
                for gross_value, raw_value in zip(gross_values, raw_returns)
            )
        )

    with localcontext() as context:
        context.prec = 28
        positive_ratio = Decimal(positive_count) / Decimal(completed_rows)

    return AttributionMetrics(
        eligible_rows=eligible_rows,
        completed_rows=completed_rows,
        excluded_rows=excluded_rows,
        excluded_missing_coverage=excluded_missing_coverage,
        mean_return=mean_return,
        median_return=_median(raw_returns),
        positive_ratio=positive_ratio,
        positive_wilson_interval=_wilson_interval(
            positive_count,
            completed_rows,
        ),
        mean_matched_index_return=_mean(matched_index_returns),
        median_matched_index_return=_median(matched_index_returns),
        mean_market_median_return=_mean(market_median_returns),
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


def attribute_interval(
    code: str,
    start: date,
    end: date,
    panel: MarketClosePanel,
) -> AttributedReturn:
    """Attribute one stock close return to matched and universe benchmarks."""

    train_dates = _validate_train_dates(panel.train_dates)
    if start not in train_dates or end not in train_dates or start >= end:
        raise ValueError("interval endpoints must be train dates in order")

    normalized_code = normalize_code6(code)
    stock_series = panel.stock_closes.get(normalized_code)
    if stock_series is None or start not in stock_series or end not in stock_series:
        raise ValueError("stock interval endpoints are missing")
    raw_return = simple_return(stock_series[start], stock_series[end])

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

    market_return = _median(market_returns)
    with localcontext() as context:
        context.prec = 28
        return AttributedReturn(
            raw_return=raw_return,
            matched_index_return=index_return,
            market_median_return=market_return,
            index_excess=raw_return - index_return,
            market_median_excess=raw_return - market_return,
            market_members=len(market_returns),
        )
