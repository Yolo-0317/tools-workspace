"""Pure train-only market attribution primitives for five-day ranking V3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from typing import Mapping, Sequence

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6


ATTRIBUTION_SCHEMA = "five-day-ranking-v3-train-attribution-v1"
ATTRIBUTION_VERSION = "dual-benchmark-train-attribution-v1"
UNIVERSE_VERSION = "sh-sz-main-board-close-median-v1"
MIN_MARKET_MEDIAN_MEMBERS = 1000


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
