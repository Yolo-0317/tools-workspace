"""Deterministic execution for five-day return shadow plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from .execution import ExecutionCosts
from .five_day_return_profiles import (
    EvaluationPosition,
    EvaluationSizing,
    evaluation_position,
    resolve_profile_stop,
)
from .five_day_return_runtime import FiveDaySignalPlan
from .models import BuyPointBar


EVALUATOR_VERSION = "five-day-return-evaluator-v1"
COST_VERSION = "execution-costs-default-v1"


@dataclass(frozen=True)
class FiveDayExit:
    planned_exit_date: date
    actual_exit_date: date
    price: Decimal
    reason: str
    fees: Decimal
    delayed: bool


@dataclass(frozen=True)
class FiveDayTrade:
    profile_id: str
    structure_id: str
    code: str
    signal_date: date
    status: str
    entry_date: date | None
    entry_price: Decimal | None
    stop_price: Decimal | None
    evaluation_target_notional: Decimal
    evaluation_shares: int
    evaluation_notional: Decimal
    entry_fees: Decimal
    exit: FiveDayExit | None
    net_pnl: Decimal
    net_return: Decimal | None
    mfe: Decimal | None
    mae: Decimal | None
    intraday_order_ambiguous: bool
    reasons: tuple[str, ...]
    executable_shares: int = 0


@dataclass(frozen=True)
class _EntryFill:
    entry_date: date
    entry_price: Decimal
    intraday_cross: bool


def _commission(gross: Decimal, costs: ExecutionCosts) -> Decimal:
    return max(costs.minimum_commission, gross * costs.commission_rate)


def _locked_limit_up(value: BuyPointBar) -> bool:
    return (
        value.open == value.high == value.low == value.close
        and value.pct_chg >= Decimal("9.5")
    )


def _locked_limit_down(value: BuyPointBar) -> bool:
    return (
        value.open == value.high == value.low == value.close
        and value.pct_chg <= Decimal("-9.5")
    )


def _tradable(value: BuyPointBar | None) -> bool:
    if value is None or value.amount_qian <= 0:
        return False
    prices = (value.open, value.high, value.low, value.close)
    return (
        all(price.is_finite() and price > 0 for price in prices)
        and value.high >= value.low
    )


def _empty_trade(
    plan: FiveDaySignalPlan,
    status: str,
    reasons: Sequence[str] = (),
) -> FiveDayTrade:
    return FiveDayTrade(
        profile_id=plan.profile.profile_id,
        structure_id=plan.structure_id,
        code=plan.candidate.code,
        signal_date=plan.candidate.signal_date,
        status=status,
        entry_date=None,
        entry_price=None,
        stop_price=None,
        evaluation_target_notional=EvaluationSizing().target_notional,
        evaluation_shares=0,
        evaluation_notional=Decimal("0"),
        entry_fees=Decimal("0"),
        exit=None,
        net_pnl=Decimal("0"),
        net_return=None,
        mfe=None,
        mae=None,
        intraday_order_ambiguous=False,
        reasons=tuple(reasons),
    )


def _breakout_entry(
    plan: FiveDaySignalPlan,
    value: BuyPointBar,
    costs: ExecutionCosts,
) -> tuple[_EntryFill | None, str | None]:
    if _locked_limit_up(value):
        return None, "LOCKED_LIMIT_UP"
    gap = value.open / plan.signal_close - Decimal("1")
    if gap > Decimal("0.03"):
        return None, "GAP_CANCELLED"
    if value.open >= plan.breakout_trigger:
        base_price = value.open
        intraday_cross = False
    elif value.high >= plan.breakout_trigger:
        base_price = plan.breakout_trigger
        intraday_cross = True
    else:
        return None, None
    if base_price / plan.signal_close - Decimal("1") > Decimal("0.05"):
        return None, "CHASE_CANCELLED"
    return (
        _EntryFill(
            value.trade_date,
            base_price * (Decimal("1") + costs.slippage_rate),
            intraday_cross,
        ),
        None,
    )


def _pullback_reclaim_entry(
    plan: FiveDaySignalPlan,
    value: BuyPointBar,
    costs: ExecutionCosts,
) -> tuple[_EntryFill | None, str | None]:
    if _locked_limit_up(value):
        return None, "LOCKED_LIMIT_UP"
    session_range = value.high - value.low
    if (
        session_range <= 0
        or value.low > plan.signal_close
        or value.close < plan.signal_close
    ):
        return None, None
    close_location = (value.close - value.low) / session_range
    if close_location < Decimal("0.60"):
        return None, None
    if value.close / plan.signal_close - Decimal("1") > Decimal("0.03"):
        return None, "CHASE_CANCELLED"
    return (
        _EntryFill(
            value.trade_date,
            value.close * (Decimal("1") + costs.slippage_rate),
            False,
        ),
        None,
    )


def _entered_trade(
    plan: FiveDaySignalPlan,
    fill: _EntryFill,
    stop_price: Decimal,
    position: EvaluationPosition,
    entry_fees: Decimal,
    reasons: Sequence[str],
    *,
    status: str = "PENDING",
    exit: FiveDayExit | None = None,
    net_pnl: Decimal = Decimal("0"),
    net_return: Decimal | None = None,
    mfe: Decimal | None = None,
    mae: Decimal | None = None,
    intraday_order_ambiguous: bool = False,
) -> FiveDayTrade:
    return FiveDayTrade(
        profile_id=plan.profile.profile_id,
        structure_id=plan.structure_id,
        code=plan.candidate.code,
        signal_date=plan.candidate.signal_date,
        status=status,
        entry_date=fill.entry_date,
        entry_price=fill.entry_price,
        stop_price=stop_price,
        evaluation_target_notional=position.evaluation_target_notional,
        evaluation_shares=position.evaluation_shares,
        evaluation_notional=position.evaluation_notional,
        entry_fees=entry_fees,
        exit=exit,
        net_pnl=net_pnl,
        net_return=net_return,
        mfe=mfe,
        mae=mae,
        intraday_order_ambiguous=intraday_order_ambiguous,
        reasons=tuple(reasons),
    )


def _sell_exit(
    planned_exit_date: date,
    actual_bar: BuyPointBar,
    raw_price: Decimal,
    reason: str,
    shares: int,
    costs: ExecutionCosts,
    *,
    delayed: bool,
) -> FiveDayExit:
    price = raw_price * (Decimal("1") - costs.slippage_rate)
    gross = price * Decimal(shares)
    fees = _commission(gross, costs) + gross * costs.sell_tax_rate
    return FiveDayExit(
        planned_exit_date=planned_exit_date,
        actual_exit_date=actual_bar.trade_date,
        price=price,
        reason=reason,
        fees=fees,
        delayed=delayed,
    )


def _excursions(
    plan: FiveDaySignalPlan,
    fill: _EntryFill,
    exit: FiveDayExit,
    bars_by_date: Mapping[date, BuyPointBar],
    confirmed_dates: frozenset[date],
) -> tuple[Decimal, Decimal]:
    include_entry_date = plan.profile.entry_kind == "BREAKOUT_TRIGGER"
    observed = tuple(
        value
        for trade_date, value in sorted(bars_by_date.items())
        if (
            trade_date in confirmed_dates
            and (
                trade_date >= fill.entry_date
                if include_entry_date
                else trade_date > fill.entry_date
            )
            and trade_date <= exit.actual_exit_date
            and _tradable(value)
        )
    )
    mfe = max(
        (
            max(Decimal("0"), value.high / fill.entry_price - Decimal("1"))
            for value in observed
        ),
        default=Decimal("0"),
    )
    mae = max(
        (
            max(Decimal("0"), Decimal("1") - value.low / fill.entry_price)
            for value in observed
        ),
        default=Decimal("0"),
    )
    return mfe, mae


def simulate_five_day_plan(
    plan: FiveDaySignalPlan,
    bars: Sequence[BuyPointBar],
    trading_calendar: Sequence[date],
    costs: ExecutionCosts | None = None,
    *,
    entry_blockers: Mapping[date, Sequence[str]] | None = None,
) -> FiveDayTrade:
    resolved_costs = costs or ExecutionCosts()
    calendar = tuple(sorted(set(trading_calendar)))
    bars_by_date = {value.trade_date: value for value in bars}
    entry_dates = tuple(
        value
        for value in calendar
        if plan.candidate.signal_date < value
        <= plan.candidate.valid_through_trade_date
    )[:2]
    blockers = entry_blockers or {}
    fill: _EntryFill | None = None
    for entry_date in entry_dates:
        reasons = tuple(sorted(set(blockers.get(entry_date, ()))))
        if reasons:
            return _empty_trade(plan, "CANCELLED", reasons)
        value = bars_by_date.get(entry_date)
        if value is None:
            continue
        if plan.profile.entry_kind == "BREAKOUT_TRIGGER":
            fill, cancellation = _breakout_entry(plan, value, resolved_costs)
        else:
            fill, cancellation = _pullback_reclaim_entry(
                plan, value, resolved_costs
            )
        if cancellation is not None:
            return _empty_trade(plan, "CANCELLED", (cancellation,))
        if fill is not None:
            break

    if fill is None:
        status = "NOT_TRIGGERED" if len(entry_dates) == 2 else "PENDING"
        return _empty_trade(plan, status)

    stop_decision = resolve_profile_stop(
        plan.profile,
        fill.entry_price,
        plan.structure_stop,
    )
    if stop_decision.stop_price is None:
        return _empty_trade(plan, "CANCELLED", stop_decision.reasons)
    stop_price = stop_decision.stop_price
    position = evaluation_position(fill.entry_price)
    entry_fees = _commission(position.evaluation_notional, resolved_costs)
    base_reasons = (
        ["MINIMUM_LOT_EXCEEDS_TARGET_NOTIONAL"]
        if position.minimum_lot_exceeds_target
        else []
    )
    entry_calendar_index = calendar.index(fill.entry_date)
    holding_dates = calendar[entry_calendar_index : entry_calendar_index + 5]
    planned_time_exit = holding_dates[4] if len(holding_dates) == 5 else None
    scan_dates = calendar[entry_calendar_index:]
    monitor_entry = plan.profile.entry_kind == "BREAKOUT_TRIGGER"
    pending_reason: str | None = None
    pending_planned_date: date | None = None
    exit: FiveDayExit | None = None
    intraday_order_ambiguous = False

    for trade_date in scan_dates:
        if trade_date == fill.entry_date and not monitor_entry:
            continue
        value = bars_by_date.get(trade_date)
        if pending_reason is not None and pending_planned_date is not None:
            if _tradable(value) and not _locked_limit_down(value):
                exit = _sell_exit(
                    pending_planned_date,
                    value,
                    value.open,
                    pending_reason,
                    position.evaluation_shares,
                    resolved_costs,
                    delayed=True,
                )
                break
            continue

        if _tradable(value) and value.low <= stop_price:
            if (
                trade_date == fill.entry_date
                and fill.intraday_cross
                and plan.profile.entry_kind == "BREAKOUT_TRIGGER"
            ):
                intraday_order_ambiguous = True
            if _locked_limit_down(value):
                pending_reason = "STOP"
                pending_planned_date = trade_date
                continue
            raw_price = value.open if value.open <= stop_price else stop_price
            exit = _sell_exit(
                trade_date,
                value,
                raw_price,
                "STOP",
                position.evaluation_shares,
                resolved_costs,
                delayed=False,
            )
            break

        if planned_time_exit is not None and trade_date == planned_time_exit:
            if not _tradable(value) or _locked_limit_down(value):
                pending_reason = "TIME_EXIT"
                pending_planned_date = trade_date
                continue
            exit = _sell_exit(
                trade_date,
                value,
                value.close,
                "TIME_EXIT",
                position.evaluation_shares,
                resolved_costs,
                delayed=False,
            )
            break

    if exit is None:
        pending_reasons = list(base_reasons)
        if pending_reason is not None:
            pending_reasons.append("EXIT_DELAYED")
        return _entered_trade(
            plan,
            fill,
            stop_price,
            position,
            entry_fees,
            pending_reasons,
            intraday_order_ambiguous=intraday_order_ambiguous,
        )

    exit_gross = exit.price * Decimal(position.evaluation_shares)
    net_pnl = (
        exit_gross
        - exit.fees
        - position.evaluation_notional
        - entry_fees
    )
    net_return = net_pnl / (position.evaluation_notional + entry_fees)
    if exit.reason == "STOP":
        status = "STOPPED"
    elif net_return > 0:
        status = "TIME_EXIT_GAIN"
    elif net_return < 0:
        status = "TIME_EXIT_LOSS"
    else:
        status = "TIME_EXIT_FLAT"
    reasons = list(base_reasons)
    if exit.delayed:
        reasons.append("EXIT_DELAYED")
    mfe, mae = _excursions(
        plan,
        fill,
        exit,
        bars_by_date,
        frozenset(calendar),
    )
    return _entered_trade(
        plan,
        fill,
        stop_price,
        position,
        entry_fees,
        reasons,
        status=status,
        exit=exit,
        net_pnl=net_pnl,
        net_return=net_return,
        mfe=mfe,
        mae=mae,
        intraday_order_ambiguous=intraday_order_ambiguous,
    )
