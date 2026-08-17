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
