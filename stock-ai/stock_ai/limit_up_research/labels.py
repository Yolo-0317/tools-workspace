"""Forward outcome labels using exact market-session horizons."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from stock_ai.limit_up_logic import limit_up_threshold

from .models import ForwardLabel


_HORIZONS = (("T1", 1), ("T3", 3), ("T5", 5))


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _is_limit_up(code: str, pct_chg: Any) -> bool:
    if pct_chg is None:
        return False
    threshold = limit_up_threshold(code)
    return threshold is not None and float(pct_chg) >= threshold - 0.05


def _board_height(code: str, rows: Sequence[Mapping[str, Any]], outcome: date) -> int:
    ordered = sorted((row for row in rows if _as_date(row["trade_date"]) <= outcome), key=lambda r: _as_date(r["trade_date"]))
    count = 0
    for row in reversed(ordered):
        if not _is_limit_up(code, row.get("pct_chg")):
            break
        count += 1
    return count


def compute_forward_labels(
    signal_date: date,
    code: str,
    bars: Sequence[Mapping[str, Any]],
    market_dates: Sequence[date],
) -> tuple[ForwardLabel, ...]:
    sessions = tuple(sorted({_as_date(value) for value in market_dates}))
    if signal_date not in sessions:
        raise ValueError("signal_date is not a market session")
    position = sessions.index(signal_date)
    by_date = {_as_date(row["trade_date"]): row for row in bars}
    signal = by_date.get(signal_date)
    signal_close = float(signal["close"]) if signal and signal.get("close") is not None else None
    labels: list[ForwardLabel] = []
    for horizon, offset in _HORIZONS:
        target_index = position + offset
        if target_index >= len(sessions):
            continue
        outcome_date = sessions[target_index]
        outcome = by_date.get(outcome_date)
        missing: list[str] = []
        if signal_close is None or signal_close <= 0:
            missing.append("INVALID_SIGNAL_CLOSE")
        if outcome is None:
            missing.append("OUTCOME_BAR_MISSING")
        interval_dates = sessions[position + 1 : target_index + 1]
        interval = [by_date[value] for value in interval_dates if value in by_date]
        if len(interval) != len(interval_dates):
            missing.append("INTERVAL_BAR_MISSING")
        complete = not missing
        outcome_close = float(outcome["close"]) if outcome and outcome.get("close") is not None else None
        close_return = (
            (outcome_close / signal_close - 1.0) * 100.0
            if complete and signal_close and outcome_close is not None
            else None
        )
        max_return = (
            (max(float(row["high"]) for row in interval) / signal_close - 1.0) * 100.0
            if complete and signal_close
            else None
        )
        max_drawdown = (
            (min(float(row["low"]) for row in interval) / signal_close - 1.0) * 100.0
            if complete and signal_close
            else None
        )
        labels.append(
            ForwardLabel(
                signal_date=signal_date,
                code=str(code).split(".")[0].zfill(6),
                horizon=horizon,
                outcome_date=outcome_date,
                signal_close=signal_close,
                outcome_close=outcome_close,
                close_return_pct=close_return,
                max_return_pct=max_return,
                max_drawdown_pct=max_drawdown,
                closed_limit_up=(
                    _is_limit_up(code, outcome.get("pct_chg")) if outcome is not None else None
                ),
                board_height=(
                    _board_height(code, bars, outcome_date) if outcome is not None else None
                ),
                data_complete=complete,
                missing_fields=tuple(dict.fromkeys(missing)),
            )
        )
    return tuple(labels)
