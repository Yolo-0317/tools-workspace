"""Deterministic NO-TRADE execution for the public strategy challenger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_FLOOR, localcontext
from typing import Sequence

from .execution import ExecutionCosts
from .five_day_return_profiles import evaluation_position
from .models import BuyPointBar
from .planning import atr14
from .public_challenger_signals import (
    EXECUTION_TRACK,
    RESIDUAL_TRACK,
    ChallengerSignal,
)


PUBLIC_CHALLENGER_EVALUATOR_VERSION = "public-challenger-evaluator-v1"


@dataclass(frozen=True)
class ChallengerPlan:
    signal: ChallengerSignal
    valid_entry_dates: tuple[date, ...]
    entry_kind: str
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"
    executable_shares: int = 0


@dataclass(frozen=True)
class ChallengerTrade:
    track_id: str
    signal_date: date
    status: str
    entry_date: date | None
    entry_price: Decimal | None
    exit_date: date | None
    exit_price: Decimal | None
    stop_price: Decimal | None
    net_return: Decimal | None
    mfe: Decimal | None
    mae: Decimal | None
    reasons: tuple[str, ...]


def _empty_trade(
    signal: ChallengerSignal,
    status: str,
    reasons: Sequence[str] = (),
) -> ChallengerTrade:
    return ChallengerTrade(
        track_id=signal.track_id,
        signal_date=signal.signal_date,
        status=status,
        entry_date=None,
        entry_price=None,
        exit_date=None,
        exit_price=None,
        stop_price=None,
        net_return=None,
        mfe=None,
        mae=None,
        reasons=tuple(reasons),
    )


def _ordered_future_bars(
    signal: ChallengerSignal,
    bars: Sequence[BuyPointBar],
) -> tuple[BuyPointBar, ...]:
    ordered = tuple(
        sorted(
            (value for value in bars if value.trade_date > signal.signal_date),
            key=lambda value: value.trade_date,
        )
    )
    if len({value.trade_date for value in ordered}) != len(ordered):
        raise ValueError("FUTURE_BAR_DATES_NOT_STRICT")
    return ordered


def _tradable(value: BuyPointBar) -> bool:
    prices = (value.open, value.high, value.low, value.close)
    return (
        value.amount_qian > 0
        and all(price.is_finite() and price > 0 for price in prices)
        and value.low <= min(value.open, value.close)
        and value.high >= max(value.open, value.close)
    )


def _locked_limit_reason(value: BuyPointBar) -> str | None:
    if value.open != value.high or value.high != value.low or value.low != value.close:
        return None
    if value.pct_chg >= Decimal("9.5"):
        return "LOCKED_LIMIT_UP"
    if value.pct_chg <= Decimal("-9.5"):
        return "LOCKED_LIMIT_DOWN"
    return None


def _commission(gross: Decimal, costs: ExecutionCosts) -> Decimal:
    return max(costs.minimum_commission, gross * costs.commission_rate)


def _floor_cent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_FLOOR)


def _entered_pending_trade(
    *,
    signal: ChallengerSignal,
    entry_date: date,
    entry_price: Decimal,
    stop_price: Decimal | None,
    reasons: Sequence[str] = (),
) -> ChallengerTrade:
    return ChallengerTrade(
        track_id=signal.track_id,
        signal_date=signal.signal_date,
        status="PENDING",
        entry_date=entry_date,
        entry_price=entry_price,
        exit_date=None,
        exit_price=None,
        stop_price=stop_price,
        net_return=None,
        mfe=None,
        mae=None,
        reasons=tuple(reasons),
    )


def _closed_trade(
    *,
    signal: ChallengerSignal,
    entry_date: date,
    entry_price: Decimal,
    exit_bar: BuyPointBar,
    raw_exit_price: Decimal,
    stop_price: Decimal | None,
    observed: Sequence[BuyPointBar],
    costs: ExecutionCosts,
    stopped: bool = False,
    reasons: Sequence[str] = (),
) -> ChallengerTrade:
    position = evaluation_position(entry_price)
    entry_fees = _commission(position.evaluation_notional, costs)
    exit_price = raw_exit_price * (Decimal("1") - costs.slippage_rate)
    exit_gross = exit_price * Decimal(position.evaluation_shares)
    exit_fees = (
        _commission(exit_gross, costs)
        + exit_gross * costs.sell_tax_rate
    )
    with localcontext() as context:
        context.prec = 50
        net_pnl = (
            exit_gross
            - exit_fees
            - position.evaluation_notional
            - entry_fees
        )
        net_return = net_pnl / (
            position.evaluation_notional + entry_fees
        )
        mfe = max(
            (
                max(Decimal("0"), value.high / entry_price - Decimal("1"))
                for value in observed
            ),
            default=Decimal("0"),
        )
        mae = max(
            (
                max(Decimal("0"), Decimal("1") - value.low / entry_price)
                for value in observed
            ),
            default=Decimal("0"),
        )
    if stopped:
        status = "STOPPED"
    elif net_return > 0:
        status = "TIME_EXIT_GAIN"
    elif net_return < 0:
        status = "TIME_EXIT_LOSS"
    else:
        status = "TIME_EXIT_FLAT"
    return ChallengerTrade(
        track_id=signal.track_id,
        signal_date=signal.signal_date,
        status=status,
        entry_date=entry_date,
        entry_price=entry_price,
        exit_date=exit_bar.trade_date,
        exit_price=exit_price,
        stop_price=stop_price,
        net_return=net_return,
        mfe=mfe,
        mae=mae,
        reasons=tuple(reasons),
    )


def simulate_direct_five_day(
    signal: ChallengerSignal,
    bars: Sequence[BuyPointBar],
    costs: ExecutionCosts,
) -> ChallengerTrade:
    if signal.track_id != RESIDUAL_TRACK:
        raise ValueError("DIRECT_SOURCE_TRACK_INVALID")
    future = _ordered_future_bars(signal, bars)
    if not future:
        return _empty_trade(signal, "PENDING")
    entry_bar = future[0]
    locked_reason = _locked_limit_reason(entry_bar)
    if locked_reason is not None:
        return _empty_trade(signal, "CANCELLED", (locked_reason,))
    if not _tradable(entry_bar):
        return _empty_trade(signal, "CANCELLED", ("ENTRY_BAR_INVALID",))
    entry_price = entry_bar.open * (Decimal("1") + costs.slippage_rate)
    if len(future) < 5:
        return _entered_pending_trade(
            signal=signal,
            entry_date=entry_bar.trade_date,
            entry_price=entry_price,
            stop_price=None,
        )
    exit_bar = future[4]
    delayed = (
        not _tradable(exit_bar)
        or _locked_limit_reason(exit_bar) == "LOCKED_LIMIT_DOWN"
    )
    if delayed:
        delayed_bar = next(
            (
                value
                for value in future[5:]
                if _tradable(value)
                and _locked_limit_reason(value) != "LOCKED_LIMIT_DOWN"
            ),
            None,
        )
        if delayed_bar is None:
            return _entered_pending_trade(
                signal=signal,
                entry_date=entry_bar.trade_date,
                entry_price=entry_price,
                stop_price=None,
                reasons=("EXIT_DELAYED",),
            )
        exit_bar = delayed_bar
    return _closed_trade(
        signal=signal,
        entry_date=entry_bar.trade_date,
        entry_price=entry_price,
        exit_bar=exit_bar,
        raw_exit_price=exit_bar.open if delayed else exit_bar.close,
        stop_price=None,
        observed=tuple(
            value
            for value in future
            if value.trade_date <= exit_bar.trade_date
        ),
        costs=costs,
        reasons=("EXIT_DELAYED",) if delayed else (),
    )


def _reclaim_reason(
    signal_close: Decimal,
    value: BuyPointBar,
) -> str | None:
    if not _tradable(value):
        return "ENTRY_BAR_INVALID"
    locked_reason = _locked_limit_reason(value)
    if locked_reason is not None:
        return locked_reason
    if value.high <= value.low:
        return "INVALID_RANGE"
    if value.low > signal_close:
        return "NO_TOUCH"
    if value.close < signal_close:
        return "NO_RECLAIM"
    if (value.close - value.low) / (value.high - value.low) < Decimal("0.60"):
        return "WEAK_CLOSE"
    if value.close / signal_close - Decimal("1") > Decimal("0.03"):
        return "CHASE_CANCELLED"
    return None


def _find_reclaim(
    signal: ChallengerSignal,
    bars: Sequence[BuyPointBar],
) -> tuple[tuple[BuyPointBar, ...], int | None, tuple[str, ...]]:
    future = _ordered_future_bars(signal, bars)
    reasons: list[str] = []
    for index, value in enumerate(future[:2]):
        reason = _reclaim_reason(signal.signal_close, value)
        if reason is None:
            return future, index, tuple(reasons)
        reasons.append(reason)
    return future, None, tuple(reasons)


def _reclaim_stop(
    *,
    signal: ChallengerSignal,
    bars: Sequence[BuyPointBar],
    confirmation: BuyPointBar,
    confirmation_entry_price: Decimal,
) -> tuple[Decimal | None, tuple[str, ...]]:
    bounded = tuple(
        sorted(
            (
                value
                for value in bars
                if value.trade_date <= confirmation.trade_date
            ),
            key=lambda value: value.trade_date,
        )
    )
    volatility = atr14(bounded)
    if not volatility.is_finite() or volatility <= 0:
        return None, ("ATR14_UNAVAILABLE",)
    stop_price = _floor_cent(
        confirmation.low - Decimal("0.2") * volatility
    )
    if stop_price <= 0 or stop_price >= confirmation_entry_price:
        return None, ("RISK_DISTANCE_OUT_OF_RANGE",)
    risk_fraction = (
        confirmation_entry_price - stop_price
    ) / confirmation_entry_price
    if not Decimal("0.015") <= risk_fraction <= Decimal("0.05"):
        return None, ("RISK_DISTANCE_OUT_OF_RANGE",)
    return stop_price, ()


def _simulate_reclaim_exit(
    *,
    signal: ChallengerSignal,
    future: Sequence[BuyPointBar],
    entry_index: int,
    entry_price: Decimal,
    stop_price: Decimal,
    costs: ExecutionCosts,
    monitor_entry_session: bool,
) -> ChallengerTrade:
    entry_bar = future[entry_index]
    planned_exit_index = entry_index + 4
    pending_reason: str | None = None
    scan_start = entry_index if monitor_entry_session else entry_index + 1
    for index in range(scan_start, len(future)):
        value = future[index]
        if pending_reason is not None:
            if _tradable(value) and _locked_limit_reason(value) != "LOCKED_LIMIT_DOWN":
                return _closed_trade(
                    signal=signal,
                    entry_date=entry_bar.trade_date,
                    entry_price=entry_price,
                    exit_bar=value,
                    raw_exit_price=value.open,
                    stop_price=stop_price,
                    observed=future[scan_start : index + 1],
                    costs=costs,
                    stopped=pending_reason == "STOP",
                    reasons=("EXIT_DELAYED",),
                )
            continue
        if _tradable(value) and value.low <= stop_price:
            if _locked_limit_reason(value) == "LOCKED_LIMIT_DOWN":
                pending_reason = "STOP"
                continue
            raw_price = value.open if value.open <= stop_price else stop_price
            return _closed_trade(
                signal=signal,
                entry_date=entry_bar.trade_date,
                entry_price=entry_price,
                exit_bar=value,
                raw_exit_price=raw_price,
                stop_price=stop_price,
                observed=future[scan_start : index + 1],
                costs=costs,
                stopped=True,
            )
        if index == planned_exit_index:
            if not _tradable(value) or _locked_limit_reason(value) == "LOCKED_LIMIT_DOWN":
                pending_reason = "TIME_EXIT"
                continue
            return _closed_trade(
                signal=signal,
                entry_date=entry_bar.trade_date,
                entry_price=entry_price,
                exit_bar=value,
                raw_exit_price=value.close,
                stop_price=stop_price,
                observed=future[scan_start : index + 1],
                costs=costs,
            )
    reasons = ("EXIT_DELAYED",) if pending_reason is not None else ()
    return _entered_pending_trade(
        signal=signal,
        entry_date=entry_bar.trade_date,
        entry_price=entry_price,
        stop_price=stop_price,
        reasons=reasons,
    )


def _confirmed_reclaim(
    signal: ChallengerSignal,
    bars: Sequence[BuyPointBar],
    costs: ExecutionCosts,
) -> tuple[
    tuple[BuyPointBar, ...],
    int | None,
    Decimal | None,
    tuple[str, ...],
]:
    if signal.track_id != EXECUTION_TRACK:
        raise ValueError("RECLAIM_SOURCE_TRACK_INVALID")
    future, confirmation_index, reasons = _find_reclaim(signal, bars)
    if confirmation_index is None:
        return future, None, None, reasons
    confirmation = future[confirmation_index]
    confirmation_entry_price = confirmation.close * (
        Decimal("1") + costs.slippage_rate
    )
    stop_price, stop_reasons = _reclaim_stop(
        signal=signal,
        bars=bars,
        confirmation=confirmation,
        confirmation_entry_price=confirmation_entry_price,
    )
    return future, confirmation_index, stop_price, stop_reasons


def simulate_reclaim_five_day(
    signal: ChallengerSignal,
    bars: Sequence[BuyPointBar],
    costs: ExecutionCosts,
) -> ChallengerTrade:
    future, confirmation_index, stop_price, reasons = _confirmed_reclaim(
        signal,
        bars,
        costs,
    )
    if confirmation_index is None:
        status = "NOT_TRIGGERED" if len(future) >= 2 else "PENDING"
        return _empty_trade(signal, status, reasons)
    if stop_price is None:
        return _empty_trade(signal, "CANCELLED", reasons)
    confirmation = future[confirmation_index]
    entry_price = confirmation.close * (
        Decimal("1") + costs.slippage_rate
    )
    return _simulate_reclaim_exit(
        signal=signal,
        future=future,
        entry_index=confirmation_index,
        entry_price=entry_price,
        stop_price=stop_price,
        costs=costs,
        monitor_entry_session=False,
    )


def simulate_next_open_after_reclaim(
    signal: ChallengerSignal,
    bars: Sequence[BuyPointBar],
    costs: ExecutionCosts,
) -> ChallengerTrade:
    future, confirmation_index, stop_price, reasons = _confirmed_reclaim(
        signal,
        bars,
        costs,
    )
    if confirmation_index is None:
        status = "NOT_TRIGGERED" if len(future) >= 2 else "PENDING"
        return _empty_trade(signal, status, reasons)
    if stop_price is None:
        return _empty_trade(signal, "CANCELLED", reasons)
    entry_index = confirmation_index + 1
    if entry_index >= len(future):
        return _empty_trade(signal, "PENDING", ("NEXT_OPEN_UNAVAILABLE",))
    entry_bar = future[entry_index]
    locked_reason = _locked_limit_reason(entry_bar)
    if locked_reason is not None:
        return _empty_trade(signal, "CANCELLED", (locked_reason,))
    if not _tradable(entry_bar):
        return _empty_trade(signal, "CANCELLED", ("ENTRY_BAR_INVALID",))
    entry_price = entry_bar.open * (Decimal("1") + costs.slippage_rate)
    return _simulate_reclaim_exit(
        signal=signal,
        future=future,
        entry_index=entry_index,
        entry_price=entry_price,
        stop_price=stop_price,
        costs=costs,
        monitor_entry_session=True,
    )
