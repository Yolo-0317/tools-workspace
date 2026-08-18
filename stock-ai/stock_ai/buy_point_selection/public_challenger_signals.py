"""Pure signals for the isolated public short-term strategy challenger."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, localcontext
from typing import Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .five_day_ranking_v3_attribution import matched_index_id
from .models import BuyPointBar
from .reference_data import SectorMembership, membership_on


CONTRARIAN_TRACK = "A_SHARE_CONTRARIAN_REFERENCE"
RESIDUAL_TRACK = "RESIDUAL_REVERSAL_CORE"
EXECUTION_TRACK = "RESIDUAL_RECLAIM_EXECUTION"
PUBLIC_CHALLENGER_SIGNAL_VERSION = "public-challenger-signals-v1"


@dataclass(frozen=True)
class ChallengerSignal:
    track_id: str
    signal_date: date
    code: str
    sector_code: str
    matched_index_id: str
    signal_close: Decimal
    formation_return: Decimal
    residual_5d: Decimal | None
    market_percentile: Decimal
    sector_percentile: Decimal | None
    reference_bucket: str | None
    in_candidate_pool: bool
    audit_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResidualEstimate:
    alpha: Decimal
    beta_market: Decimal
    beta_sector: Decimal
    estimation_dates: tuple[date, ...]
    signal_dates: tuple[date, ...]
    residual_5d: Decimal


def _ordered_bars(
    bars: Sequence[BuyPointBar],
    through: date,
) -> tuple[BuyPointBar, ...]:
    ordered = tuple(
        sorted(
            (row for row in bars if row.trade_date <= through),
            key=lambda row: row.trade_date,
        )
    )
    if any(
        current.trade_date >= following.trade_date
        for current, following in zip(ordered, ordered[1:])
    ):
        raise ValueError("BAR_DATES_NOT_STRICT")
    if any(not row.close.is_finite() or row.close <= 0 for row in ordered):
        raise ValueError("BAR_CLOSE_INVALID")
    return ordered


def _five_session_return(bars: Sequence[BuyPointBar]) -> Decimal:
    if len(bars) < 6:
        raise ValueError("FIVE_SESSION_RETURN_INCOMPLETE")
    with localcontext() as context:
        context.prec = 50
        return bars[-1].close / bars[-6].close - Decimal("1")


def _percentile(rank: int, total: int) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return Decimal(rank) / Decimal(total)


def _sector_percentiles(
    rows: Sequence[tuple[str, str, Decimal]],
) -> dict[str, Decimal]:
    grouped: dict[str, list[tuple[Decimal, str]]] = {}
    for code, sector_code, score in rows:
        grouped.setdefault(sector_code, []).append((score, code))
    result: dict[str, Decimal] = {}
    for values in grouped.values():
        ordered = tuple(sorted(values))
        for rank, (_, code) in enumerate(ordered, start=1):
            result[code] = _percentile(rank, len(ordered))
    return result


def build_contrarian_signals(
    *,
    signal_date: date,
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    sector_by_code: Mapping[str, str],
) -> tuple[ChallengerSignal, ...]:
    scored: list[tuple[str, str, Decimal, Decimal]] = []
    for raw_code, bars in bars_by_code.items():
        code = normalize_code6(raw_code)
        sector_code = str(sector_by_code.get(raw_code) or sector_by_code.get(code) or "")
        if not sector_code:
            continue
        ordered = _ordered_bars(bars, signal_date)
        if len(ordered) < 6 or ordered[-1].trade_date != signal_date:
            continue
        scored.append(
            (
                code,
                sector_code,
                _five_session_return(ordered),
                ordered[-1].close,
            )
        )
    if len(scored) < 5:
        return ()
    ordered_scores = tuple(sorted(scored, key=lambda row: (row[2], row[0])))
    bucket_size = (len(ordered_scores) + 4) // 5
    sector_percentiles = _sector_percentiles(
        tuple((code, sector, score) for code, sector, score, _ in ordered_scores)
    )
    result: list[ChallengerSignal] = []
    for rank, (code, sector_code, score, signal_close) in enumerate(
        ordered_scores,
        start=1,
    ):
        if rank <= bucket_size:
            bucket = "LOSER"
        elif rank > len(ordered_scores) - bucket_size:
            bucket = "WINNER"
        else:
            bucket = "MIDDLE"
        result.append(
            ChallengerSignal(
                track_id=CONTRARIAN_TRACK,
                signal_date=signal_date,
                code=code,
                sector_code=sector_code,
                matched_index_id=matched_index_id(code),
                signal_close=signal_close,
                formation_return=score,
                residual_5d=None,
                market_percentile=_percentile(rank, len(ordered_scores)),
                sector_percentile=sector_percentiles[code],
                reference_bucket=bucket,
                in_candidate_pool=bucket == "LOSER",
            )
        )
    return tuple(result)


def _daily_return_on(
    bars: Sequence[BuyPointBar],
    trade_date: date,
) -> Decimal | None:
    ordered = _ordered_bars(bars, trade_date)
    if len(ordered) < 2 or ordered[-1].trade_date != trade_date:
        return None
    with localcontext() as context:
        context.prec = 50
        return ordered[-1].close / ordered[-2].close - Decimal("1")


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = tuple(sorted(values))
    if not ordered:
        raise ValueError("MEDIAN_EMPTY")
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def build_sector_return_series(
    *,
    dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    minimum_members: int = 10,
) -> dict[str, dict[date, Decimal]]:
    if minimum_members <= 0:
        raise ValueError("SECTOR_MINIMUM_MEMBERS_INVALID")
    requested_dates = tuple(dates)
    if not requested_dates:
        return {}
    by_sector: dict[str, dict[date, Decimal]] = {}
    valid_every_day: set[str] | None = None
    saw_insufficient = False
    for trade_date in requested_dates:
        active = membership_on(memberships, trade_date)
        grouped: dict[str, list[Decimal]] = {}
        for raw_code, membership in active.items():
            code = normalize_code6(raw_code)
            bars = bars_by_code.get(raw_code) or bars_by_code.get(code)
            if bars is None:
                continue
            value = _daily_return_on(bars, trade_date)
            if value is None:
                continue
            grouped.setdefault(membership.sector_code, []).append(value)
        valid_today = {
            sector_code
            for sector_code, values in grouped.items()
            if len(values) >= minimum_members
        }
        if any(len(values) < minimum_members for values in grouped.values()):
            saw_insufficient = True
        valid_every_day = (
            valid_today
            if valid_every_day is None
            else valid_every_day & valid_today
        )
        for sector_code in valid_today:
            by_sector.setdefault(sector_code, {})[trade_date] = _median(
                grouped[sector_code]
            )
    complete = {
        sector_code: dict(sorted(by_sector[sector_code].items()))
        for sector_code in sorted(valid_every_day or ())
        if len(by_sector.get(sector_code, {})) == len(requested_dates)
    }
    if not complete and saw_insufficient:
        raise ValueError("SECTOR_MEMBERS_BELOW_10")
    return complete


def _design_row(
    market: Decimal,
    sector: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    return Decimal("1"), market, sector - market


def _solve_decimal_normal_equations(
    rows: Sequence[tuple[Decimal, Decimal, Decimal]],
    targets: Sequence[Decimal],
) -> tuple[Decimal, Decimal, Decimal]:
    if len(rows) != len(targets) or not rows:
        raise ValueError("RESIDUAL_REGRESSION_INPUT_INVALID")
    with localcontext() as context:
        context.prec = 80
        matrix = [
            [
                sum((row[left] * row[right] for row in rows), Decimal("0"))
                for right in range(3)
            ]
            + [
                sum(
                    (row[left] * target for row, target in zip(rows, targets)),
                    Decimal("0"),
                )
            ]
            for left in range(3)
        ]
        for column in range(3):
            pivot_index = max(
                range(column, 3),
                key=lambda index: abs(matrix[index][column]),
            )
            if matrix[pivot_index][column] == 0:
                raise ValueError("RESIDUAL_REGRESSION_SINGULAR")
            matrix[column], matrix[pivot_index] = (
                matrix[pivot_index],
                matrix[column],
            )
            pivot = matrix[column][column]
            matrix[column] = [value / pivot for value in matrix[column]]
            for row_index in range(3):
                if row_index == column:
                    continue
                factor = matrix[row_index][column]
                matrix[row_index] = [
                    current - factor * pivot_value
                    for current, pivot_value in zip(
                        matrix[row_index],
                        matrix[column],
                    )
                ]
        return matrix[0][3], matrix[1][3], matrix[2][3]


def estimate_residual_signal(
    *,
    stock_returns: Mapping[date, Decimal],
    market_returns: Mapping[date, Decimal],
    sector_returns: Mapping[date, Decimal],
    estimation_dates: Sequence[date],
    signal_dates: Sequence[date],
) -> ResidualEstimate:
    estimation = tuple(estimation_dates)
    signal = tuple(signal_dates)
    if set(estimation) & set(signal):
        raise ValueError("ESTIMATION_SIGNAL_OVERLAP")
    if len(estimation) < 40 or len(signal) != 5:
        raise ValueError("RESIDUAL_WINDOW_INCOMPLETE")
    required = estimation + signal
    if any(
        trade_date not in values
        for trade_date in required
        for values in (stock_returns, market_returns, sector_returns)
    ):
        raise ValueError("RESIDUAL_COVERAGE_INCOMPLETE")
    rows = tuple(
        _design_row(market_returns[trade_date], sector_returns[trade_date])
        for trade_date in estimation
    )
    targets = tuple(stock_returns[trade_date] for trade_date in estimation)
    coefficients = _solve_decimal_normal_equations(rows, targets)
    with localcontext() as context:
        context.prec = 80
        residual = sum(
            (
                stock_returns[trade_date]
                - sum(
                    (
                        value * coefficient
                        for value, coefficient in zip(
                            _design_row(
                                market_returns[trade_date],
                                sector_returns[trade_date],
                            ),
                            coefficients,
                        )
                    ),
                    Decimal("0"),
                )
            )
            for trade_date in signal
        )
    return ResidualEstimate(
        alpha=coefficients[0],
        beta_market=coefficients[1],
        beta_sector=coefficients[2],
        estimation_dates=estimation,
        signal_dates=signal,
        residual_5d=residual,
    )


def _returns_for_dates(
    bars: Sequence[BuyPointBar],
    dates: Sequence[date],
) -> dict[date, Decimal]:
    result: dict[date, Decimal] = {}
    for trade_date in dates:
        value = _daily_return_on(bars, trade_date)
        if value is None:
            raise ValueError("STOCK_RETURN_COVERAGE_INCOMPLETE")
        result[trade_date] = value
    return result


def _index_returns_for_dates(
    closes: Mapping[date, Decimal],
    dates: Sequence[date],
    previous_date: date,
) -> dict[date, Decimal]:
    ordered_dates = (previous_date,) + tuple(dates)
    if any(trade_date not in closes for trade_date in ordered_dates):
        raise ValueError("INDEX_RETURN_COVERAGE_INCOMPLETE")
    result: dict[date, Decimal] = {}
    with localcontext() as context:
        context.prec = 50
        for prior, current in zip(ordered_dates, ordered_dates[1:]):
            prior_close = closes[prior]
            current_close = closes[current]
            if (
                not prior_close.is_finite()
                or not current_close.is_finite()
                or prior_close <= 0
                or current_close <= 0
            ):
                raise ValueError("INDEX_CLOSE_INVALID")
            result[current] = current_close / prior_close - Decimal("1")
    return result


def build_residual_signals(
    *,
    signal_date: date,
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    index_closes: Mapping[str, Mapping[date, Decimal]],
) -> tuple[ChallengerSignal, ...]:
    active_memberships = membership_on(memberships, signal_date)
    histories: dict[str, tuple[BuyPointBar, ...]] = {}
    for raw_code, bars in bars_by_code.items():
        code = normalize_code6(raw_code)
        ordered = _ordered_bars(bars, signal_date)
        if (
            len(ordered) >= 66
            and ordered[-1].trade_date == signal_date
            and (raw_code in active_memberships or code in active_memberships)
        ):
            histories[code] = ordered[-66:]
    if not histories:
        return ()
    calendars = Counter(
        tuple(row.trade_date for row in bars)
        for bars in histories.values()
    )
    largest_group = max(calendars.values())
    canonical_dates = min(
        values
        for values, count in calendars.items()
        if count == largest_group
    )
    histories = {
        code: bars
        for code, bars in histories.items()
        if tuple(row.trade_date for row in bars) == canonical_dates
    }
    previous_date = canonical_dates[0]
    calendar = canonical_dates[1:]
    sector_returns = build_sector_return_series(
        dates=calendar,
        bars_by_code=histories,
        memberships=memberships,
        minimum_members=10,
    )
    scored: list[tuple[str, str, Decimal, Decimal, Decimal]] = []
    for code, bars in sorted(histories.items()):
        membership = active_memberships.get(code)
        if membership is None or membership.sector_code not in sector_returns:
            continue
        index_id = matched_index_id(code)
        closes = index_closes.get(index_id)
        if closes is None:
            continue
        stock_returns = _returns_for_dates(bars, calendar)
        market_returns = _index_returns_for_dates(
            closes,
            calendar,
            previous_date,
        )
        estimate = estimate_residual_signal(
            stock_returns=stock_returns,
            market_returns=market_returns,
            sector_returns=sector_returns[membership.sector_code],
            estimation_dates=calendar[:60],
            signal_dates=calendar[60:],
        )
        scored.append(
            (
                code,
                membership.sector_code,
                estimate.residual_5d,
                _five_session_return(bars),
                bars[-1].close,
            )
        )
    if not scored:
        return ()
    ordered_scores = tuple(sorted(scored, key=lambda row: (row[2], row[0])))
    pool_size = (len(ordered_scores) + 9) // 10
    sector_percentiles = _sector_percentiles(
        tuple((code, sector, residual) for code, sector, residual, _, _ in ordered_scores)
    )
    return tuple(
        ChallengerSignal(
            track_id=RESIDUAL_TRACK,
            signal_date=signal_date,
            code=code,
            sector_code=sector_code,
            matched_index_id=matched_index_id(code),
            signal_close=signal_close,
            formation_return=formation_return,
            residual_5d=residual,
            market_percentile=_percentile(rank, len(ordered_scores)),
            sector_percentile=sector_percentiles[code],
            reference_bucket=None,
            in_candidate_pool=rank <= pool_size,
        )
        for rank, (
            code,
            sector_code,
            residual,
            formation_return,
            signal_close,
        ) in enumerate(ordered_scores, start=1)
    )


def build_execution_signals(
    core_signals: Sequence[ChallengerSignal],
) -> tuple[ChallengerSignal, ...]:
    if any(row.track_id != RESIDUAL_TRACK for row in core_signals):
        raise ValueError("EXECUTION_SOURCE_TRACK_INVALID")
    return tuple(replace(row, track_id=EXECUTION_TRACK) for row in core_signals)
