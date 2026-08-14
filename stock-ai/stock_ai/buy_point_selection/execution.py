"""Conservative next-session execution and portfolio simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from .models import BuyPointBar
from .planning import PricePlan


@dataclass(frozen=True)
class ExecutionCosts:
    commission_rate: Decimal = Decimal("0.001")
    minimum_commission: Decimal = Decimal("5")
    slippage_rate: Decimal = Decimal("0.001")
    sell_tax_rate: Decimal = Decimal("0.001")


@dataclass(frozen=True)
class ExitLeg:
    exit_date: date
    price: Decimal
    quantity: int
    reason: str
    fees: Decimal


@dataclass(frozen=True)
class SimulatedTrade:
    structure_id: str
    code: str
    sector_code: str
    status: str
    entry_date: date | None
    entry_price: Decimal | None
    entry_fees: Decimal
    quantity: int
    exit_legs: tuple[ExitLeg, ...]
    net_pnl: Decimal
    net_return: Decimal | None

    @property
    def exit_reason(self) -> str | None:
        return self.exit_legs[-1].reason if self.exit_legs else None


@dataclass(frozen=True)
class PortfolioCase:
    plan: PricePlan
    sector_code: str
    bars: tuple[BuyPointBar, ...]


def _commission(gross: Decimal, costs: ExecutionCosts) -> Decimal:
    return max(costs.minimum_commission, gross * costs.commission_rate)


def _empty_trade(plan: PricePlan, sector_code: str, status: str) -> SimulatedTrade:
    return SimulatedTrade(
        structure_id=plan.structure_id,
        code=plan.code,
        sector_code=sector_code,
        status=status,
        entry_date=None,
        entry_price=None,
        entry_fees=Decimal("0"),
        quantity=0,
        exit_legs=(),
        net_pnl=Decimal("0"),
        net_return=None,
    )


def _locked_limit_up(value: BuyPointBar) -> bool:
    return (
        value.open == value.high == value.low == value.close
        and value.pct_chg >= Decimal("9.5")
    )


def _sell_leg(
    value: BuyPointBar,
    raw_price: Decimal,
    quantity: int,
    reason: str,
    costs: ExecutionCosts,
) -> ExitLeg:
    price = raw_price * (Decimal("1") - costs.slippage_rate)
    gross = price * Decimal(quantity)
    fees = _commission(gross, costs) + gross * costs.sell_tax_rate
    return ExitLeg(value.trade_date, price, quantity, reason, fees)


def _entry_for_bar(
    plan: PricePlan,
    value: BuyPointBar,
    costs: ExecutionCosts,
) -> tuple[Decimal | None, str | None]:
    if _locked_limit_up(value):
        return None, "LOCKED_LIMIT_UP"
    gap = value.open / plan.signal_close - Decimal("1")
    if gap > Decimal("0.03"):
        return None, "GAP_CANCELLED"
    if value.open >= plan.trigger_price:
        base_price = value.open
    elif value.high >= plan.trigger_price:
        base_price = plan.trigger_price
    else:
        return None, None
    if base_price / plan.signal_close - Decimal("1") > Decimal("0.05"):
        return None, "CHASE_CANCELLED"
    return base_price * (Decimal("1") + costs.slippage_rate), None


def _simulate_exits(
    plan: PricePlan,
    holding_bars: Sequence[BuyPointBar],
    entry_price: Decimal,
    costs: ExecutionCosts,
) -> tuple[ExitLeg, ...]:
    remaining = plan.maximum_shares
    protection = plan.invalidation_price
    target_taken = False
    exits: list[ExitLeg] = []
    for session_index, value in enumerate(holding_bars):
        if value.low <= protection:
            raw_price = value.open if value.open <= protection else protection
            reason = "BREAKEVEN_STOP" if target_taken else "STOP"
            exits.append(_sell_leg(value, raw_price, remaining, reason, costs))
            remaining = 0
            break

        if not target_taken and value.high >= plan.target_2r:
            target_quantity = (
                remaining
                if remaining < 200
                else (remaining // 200) * 100
            )
            exits.append(
                _sell_leg(value, plan.target_2r, target_quantity, "TARGET_2R", costs)
            )
            remaining -= target_quantity
            target_taken = True
            protection = entry_price
            if remaining == 0:
                break

        if session_index == 4 and remaining:
            exits.append(_sell_leg(value, value.close, remaining, "TIME_EXIT", costs))
            remaining = 0
            break
    return tuple(exits)


def simulate_plan(
    plan: PricePlan,
    bars: Sequence[BuyPointBar],
    costs: ExecutionCosts | None = None,
    *,
    sector_code: str,
) -> SimulatedTrade:
    resolved_costs = costs or ExecutionCosts()
    ordered = tuple(
        sorted(
            (value for value in bars if value.trade_date > plan.signal_date),
            key=lambda value: value.trade_date,
        )
    )
    trigger_window = tuple(
        value for value in ordered if value.trade_date <= plan.valid_through_trade_date
    )[:2]
    entry_index: int | None = None
    entry_price: Decimal | None = None
    for value in trigger_window:
        price, cancellation = _entry_for_bar(plan, value, resolved_costs)
        if cancellation is not None:
            return _empty_trade(plan, sector_code, cancellation)
        if price is not None:
            entry_price = price
            entry_index = ordered.index(value)
            break
    if entry_price is None or entry_index is None:
        status = "EXPIRED" if len(trigger_window) >= 2 else "PENDING"
        return _empty_trade(plan, sector_code, status)

    entry_gross = entry_price * Decimal(plan.maximum_shares)
    entry_fees = _commission(entry_gross, resolved_costs)
    exits = _simulate_exits(plan, ordered[entry_index : entry_index + 5], entry_price, resolved_costs)
    exited_quantity = sum(value.quantity for value in exits)
    closed = exited_quantity == plan.maximum_shares
    if closed:
        proceeds = sum(
            (value.price * Decimal(value.quantity) - value.fees for value in exits),
            Decimal("0"),
        )
        net_pnl = proceeds - entry_gross - entry_fees
        net_return = net_pnl / (entry_gross + entry_fees)
        status = "CLOSED"
    else:
        net_pnl = Decimal("0")
        net_return = None
        status = "OPEN"
    return SimulatedTrade(
        structure_id=plan.structure_id,
        code=plan.code,
        sector_code=sector_code,
        status=status,
        entry_date=ordered[entry_index].trade_date,
        entry_price=entry_price,
        entry_fees=entry_fees,
        quantity=plan.maximum_shares,
        exit_legs=exits,
        net_pnl=net_pnl,
        net_return=net_return,
    )


def simulate_portfolio(
    cases: Sequence[PortfolioCase],
    costs: ExecutionCosts | None = None,
    *,
    maximum_positions: int = 3,
    maximum_exposure: Decimal = Decimal("40000"),
) -> tuple[SimulatedTrade, ...]:
    resolved_costs = costs or ExecutionCosts()
    accepted: list[SimulatedTrade] = []
    results: list[SimulatedTrade] = []
    for case in cases:
        trade = simulate_plan(
            case.plan,
            case.bars,
            resolved_costs,
            sector_code=case.sector_code,
        )
        if trade.entry_date is None or trade.entry_price is None:
            results.append(trade)
            continue
        active = [
            value
            for value in accepted
            if not value.exit_legs or value.exit_legs[-1].exit_date >= trade.entry_date
        ]
        if any(value.sector_code == trade.sector_code for value in active):
            results.append(_empty_trade(case.plan, case.sector_code, "SECTOR_POSITION_LIMIT"))
            continue
        if len(active) >= maximum_positions:
            results.append(_empty_trade(case.plan, case.sector_code, "POSITION_COUNT_LIMIT"))
            continue
        active_exposure = sum(
            (
                value.entry_price * Decimal(value.quantity)
                for value in active
                if value.entry_price is not None
            ),
            Decimal("0"),
        )
        trade_exposure = trade.entry_price * Decimal(trade.quantity)
        if active_exposure + trade_exposure > maximum_exposure:
            results.append(_empty_trade(case.plan, case.sector_code, "EXPOSURE_LIMIT"))
            continue
        accepted.append(trade)
        results.append(trade)
    return tuple(results)
