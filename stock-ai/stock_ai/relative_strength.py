"""Full-market 20-session relative-strength snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from types import MappingProxyType
from typing import Iterable, Mapping

from sqlalchemy import Engine, text

from .market_codes import is_sh_sz_main_board_code, normalize_code6


class RelativeStrengthDataError(RuntimeError):
    """Raised when the database cannot provide a completed comparison window."""


@dataclass(frozen=True)
class ClosePair:
    code: str
    prior_close: float
    current_close: float


@dataclass(frozen=True)
class RelativeStrengthSnapshot:
    current_trade_date: date
    prior_trade_date: date
    returns20: Mapping[str, float]
    percentiles: Mapping[str, float]
    eligible_count: int
    current_count: int
    coverage_ratio: float

    @property
    def is_usable(self) -> bool:
        return self.eligible_count > 0 and self.coverage_ratio >= 0.95


def _is_valid_close(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def _has_suffix(code: str) -> bool:
    return "." in str(code).strip()


def _deduplicate_pairs(pairs: Iterable[ClosePair]) -> dict[str, ClosePair]:
    selected: dict[str, ClosePair] = {}
    for pair in pairs:
        code = normalize_code6(pair.code)
        if not is_sh_sz_main_board_code(code):
            continue
        if not _is_valid_close(pair.prior_close) or not _is_valid_close(pair.current_close):
            continue
        existing = selected.get(code)
        if existing is None or (_has_suffix(pair.code) and not _has_suffix(existing.code)):
            selected[code] = pair
    return selected


def _percentile_ranks(returns20: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(returns20.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    if count == 1:
        return {ordered[0][0]: 1.0}
    ranked: dict[str, float] = {}
    start = 0
    while start < count:
        end = start + 1
        while end < count and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        percentile = (average_rank - 1.0) / (count - 1.0)
        for index in range(start, end):
            ranked[ordered[index][0]] = percentile
        start = end
    return ranked


def build_relative_strength_snapshot(
    *,
    current_trade_date: date,
    current_count: int,
    prior_trade_date: date,
    pairs: Iterable[ClosePair],
) -> RelativeStrengthSnapshot:
    """Rank valid main-board 20-session returns within the complete market slice."""

    if current_count < 0:
        raise ValueError("current_count must not be negative")
    if prior_trade_date >= current_trade_date:
        raise ValueError("prior_trade_date must be earlier than current_trade_date")
    selected = _deduplicate_pairs(pairs)
    returns20 = {
        code: float(pair.current_close) / float(pair.prior_close) - 1.0
        for code, pair in selected.items()
    }
    percentiles = _percentile_ranks(returns20) if returns20 else {}
    coverage = len(returns20) / current_count if current_count else 0.0
    return RelativeStrengthSnapshot(
        current_trade_date=current_trade_date,
        prior_trade_date=prior_trade_date,
        returns20=MappingProxyType(returns20),
        percentiles=MappingProxyType(percentiles),
        eligible_count=len(returns20),
        current_count=current_count,
        coverage_ratio=coverage,
    )


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _preferred_closes(rows: Iterable[object]) -> dict[str, float]:
    selected: dict[str, tuple[bool, float]] = {}
    for row in rows:
        mapping = row._mapping  # type: ignore[attr-defined]
        raw_code = str(mapping["ts_code"])
        code = normalize_code6(raw_code)
        close = mapping["close"]
        if not is_sh_sz_main_board_code(code) or not _is_valid_close(close):
            continue
        suffixed = _has_suffix(raw_code)
        existing = selected.get(code)
        if existing is None or (suffixed and not existing[0]):
            selected[code] = (suffixed, float(close))
    return {code: value for code, (_, value) in selected.items()}


def load_relative_strength_snapshot(
    engine: Engine,
    analysis_date: date,
) -> RelativeStrengthSnapshot:
    """Load a read-only full-market snapshot ending at the latest completed date."""

    with engine.connect() as connection:
        dates = connection.execute(
            text(
                "SELECT DISTINCT trade_date FROM stock_daily "
                "WHERE trade_date <= :analysis_date "
                "ORDER BY trade_date DESC LIMIT 21"
            ),
            {"analysis_date": analysis_date},
        ).scalars().all()
        if len(dates) < 21:
            raise RelativeStrengthDataError("stock_daily has fewer than 21 completed market dates")
        current_trade_date = _as_date(dates[0])
        prior_trade_date = _as_date(dates[20])
        rows = connection.execute(
            text(
                "SELECT ts_code, trade_date, close FROM stock_daily "
                "WHERE trade_date IN (:current_trade_date, :prior_trade_date)"
            ),
            {
                "current_trade_date": current_trade_date,
                "prior_trade_date": prior_trade_date,
            },
        ).all()

    current_rows = [row for row in rows if _as_date(row._mapping["trade_date"]) == current_trade_date]
    prior_rows = [row for row in rows if _as_date(row._mapping["trade_date"]) == prior_trade_date]
    current_closes = _preferred_closes(current_rows)
    prior_closes = _preferred_closes(prior_rows)
    pairs = (
        ClosePair(code, prior_closes[code], current_close)
        for code, current_close in current_closes.items()
        if code in prior_closes
    )
    return build_relative_strength_snapshot(
        current_trade_date=current_trade_date,
        current_count=len(current_closes),
        prior_trade_date=prior_trade_date,
        pairs=pairs,
    )
