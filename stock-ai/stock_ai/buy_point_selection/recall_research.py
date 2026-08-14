"""Pure, zero-share diagnostics for exact-date short-term recall."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6

from .models import BuyPointBar, SelectionPolicy
from .reference_data import RiskFlag, risk_flags_on


@dataclass(frozen=True)
class DailyRecallWinner:
    code: str
    signal_date: date
    horizon_end_date: date
    entry_date: date
    entry_price: Decimal
    forward_maximum_gain: Decimal
    maximum_gain_date: date
    captured_tiers: tuple[str, ...] = ()
    first_rejection: str | None = None
    executable_shares: int = 0


@dataclass(frozen=True)
class DailyRecallCohort:
    signal_date: date
    outcome_dates: tuple[date, ...]
    complete: bool
    winners: tuple[DailyRecallWinner, ...]


def next_five_trading_dates(
    signal_date: date,
    trading_dates: Sequence[date],
    cutoff: date,
) -> tuple[date, ...]:
    return tuple(
        value
        for value in sorted(set(trading_dates))
        if signal_date < value <= cutoff
    )[:5]


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def find_daily_actionable_winners(
    *,
    signal_date: date,
    outcome_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    risk_flags: Sequence[RiskFlag],
    holding_codes: frozenset[str],
    policy: SelectionPolicy | None = None,
) -> DailyRecallCohort:
    resolved = policy or SelectionPolicy()
    horizon = tuple(sorted(set(outcome_dates)))
    if len(horizon) != 5:
        return DailyRecallCohort(signal_date, horizon, False, ())
    dated_flags = risk_flags_on(risk_flags, signal_date)
    vetoed = {
        code
        for code, flags in dated_flags.items()
        if any(value.severity == "VETO" for value in flags)
    }
    held = {normalize_code6(value) for value in holding_codes}
    horizon_set = frozenset(horizon)
    winners = []
    for raw_code, values in sorted(bars_by_code.items()):
        code = normalize_code6(raw_code)
        if not is_sh_sz_main_board_code(code) or code in vetoed or code in held:
            continue
        ordered = tuple(sorted(values, key=lambda value: value.trade_date))
        history = tuple(value for value in ordered if value.trade_date <= signal_date)
        if len(history) < 5 or history[-1].trade_date != signal_date:
            continue
        if _average([value.amount_qian for value in history[-5:]]) < resolved.min_average_amount5_qian:
            continue
        outcome = tuple(value for value in ordered if value.trade_date in horizon_set)
        if tuple(value.trade_date for value in outcome) != horizon:
            continue
        previous_close = history[-1].close
        selected: DailyRecallWinner | None = None
        for index, entry in enumerate(outcome):
            if (
                not entry.open.is_finite()
                or entry.open <= 0
                or not previous_close.is_finite()
                or previous_close <= 0
            ):
                previous_close = entry.close
                continue
            locked_limit_up = (
                entry.open == entry.high == entry.low == entry.close
                and entry.pct_chg >= Decimal("9.5")
            )
            gap = entry.open / previous_close - Decimal("1")
            if not locked_limit_up and gap <= Decimal("0.03"):
                forward = outcome[index:]
                maximum_high = max(value.high for value in forward)
                maximum_gain = maximum_high / entry.open - Decimal("1")
                if maximum_gain >= Decimal("0.05"):
                    maximum_date = next(
                        value.trade_date
                        for value in forward
                        if value.high == maximum_high
                    )
                    selected = DailyRecallWinner(
                        code,
                        signal_date,
                        horizon[-1],
                        entry.trade_date,
                        entry.open,
                        maximum_gain,
                        maximum_date,
                    )
                    break
            previous_close = entry.close
        if selected is not None:
            winners.append(selected)
    return DailyRecallCohort(
        signal_date,
        horizon,
        True,
        tuple(sorted(winners, key=lambda value: value.code)),
    )
