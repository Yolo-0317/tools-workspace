"""Conservative daily-bar execution proxy for short-term selection research."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Literal, Sequence

from .short_term_selection import CandidateSignal, CandidateType, SelectionBar


PlanStatus = Literal["READY", "RISK_DISTANCE_OUT_OF_RANGE"]


@dataclass(frozen=True)
class TechnicalProxyPlan:
    code: str
    candidate_type: CandidateType
    signal_date: date
    trigger_price: float
    entry_ceiling: float
    invalidation_price: float
    target_price: float
    risk_distance: float
    risk_ratio: float
    status: str


@dataclass(frozen=True)
class ProxyTrade:
    code: str
    signal_date: date
    status: str
    entry_date: date | None = None
    entry_price: float | None = None
    exit_date: date | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    gross_return: float | None = None
    net_return: float | None = None
    capital_allocated: float = 0.0
    quantity: float = 0.0


@dataclass(frozen=True)
class ProxyOpportunity:
    plan: TechnicalProxyPlan
    bars: tuple[SelectionBar, ...]


@dataclass(frozen=True)
class EquityPoint:
    trade_date: date
    equity: float


@dataclass(frozen=True)
class PortfolioBacktestResult:
    trades: tuple[ProxyTrade, ...]
    rejections: tuple[ProxyTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    initial_capital: float
    ending_capital: float
    max_drawdown: float


def _ceil_cent(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def _floor_cent(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_FLOOR))


def build_proxy_plan(
    signal: CandidateSignal,
    completed_bars: Sequence[SelectionBar],
) -> TechnicalProxyPlan:
    """Build structural proxy prices using only signal-date and earlier bars."""

    if len(completed_bars) < 10:
        raise ValueError("at least 10 completed bars are required")
    bars = tuple(sorted(completed_bars, key=lambda item: item.trade_date))
    signal_date = bars[-1].trade_date
    atr = float(signal.metrics["atr14"])
    atr_decimal = Decimal(str(atr))
    ma10 = float(signal.metrics["ma10"])
    if atr <= 0:
        raise ValueError("atr14 must be positive")

    if signal.candidate_type == "BREAKOUT":
        trigger = _ceil_cent(
            Decimal(str(signal.metrics["prior_high20"]))
            + Decimal("0.1") * atr_decimal
        )
        support = max(ma10, min(bar.low for bar in bars[-10:]))
    else:
        trigger = _ceil_cent(bars[-1].high)
        support_candidates = [value for value in (ma10, bars[-1].low) if value < trigger]
        if not support_candidates:
            raise ValueError("pullback support must be below trigger")
        support = max(support_candidates)

    trigger_decimal = Decimal(str(trigger))
    invalidation = _floor_cent(
        Decimal(str(support)) - Decimal("0.1") * atr_decimal
    )
    ceiling = _ceil_cent(
        min(
            trigger_decimal + Decimal("0.5") * atr_decimal,
            trigger_decimal * Decimal("1.015"),
        )
    )
    risk_distance = float(trigger_decimal - Decimal(str(invalidation)))
    risk_ratio = risk_distance / trigger
    target = _ceil_cent(
        trigger_decimal + Decimal("1.5") * Decimal(str(risk_distance))
    )
    status: PlanStatus = (
        "READY" if 0.015 <= risk_ratio <= 0.05 else "RISK_DISTANCE_OUT_OF_RANGE"
    )
    return TechnicalProxyPlan(
        code=signal.code,
        candidate_type=signal.candidate_type,
        signal_date=signal_date,
        trigger_price=trigger,
        entry_ceiling=ceiling,
        invalidation_price=invalidation,
        target_price=target,
        risk_distance=risk_distance,
        risk_ratio=risk_ratio,
        status=status,
    )


def _closed_trade(
    plan: TechnicalProxyPlan,
    *,
    entry_date: date,
    entry_price: float,
    exit_date: date,
    exit_price: float,
    exit_reason: str,
    commission_rate: float,
) -> ProxyTrade:
    gross_return = exit_price / entry_price - 1.0
    net_return = (
        exit_price * (1.0 - commission_rate)
        / (entry_price * (1.0 + commission_rate))
        - 1.0
    )
    return ProxyTrade(
        code=plan.code,
        signal_date=plan.signal_date,
        status="CLOSED",
        entry_date=entry_date,
        entry_price=entry_price,
        exit_date=exit_date,
        exit_price=exit_price,
        exit_reason=exit_reason,
        gross_return=gross_return,
        net_return=net_return,
    )


def simulate_proxy_trade(
    plan: TechnicalProxyPlan,
    subsequent_bars: Sequence[SelectionBar],
    *,
    commission_rate: float = 0.001,
    slippage_rate: float = 0.001,
    max_hold_sessions: int = 5,
) -> ProxyTrade:
    """Simulate one T+1 opportunity with conservative daily-bar ordering."""

    if plan.status != "READY":
        return ProxyTrade(plan.code, plan.signal_date, plan.status)
    if max_hold_sessions <= 0:
        raise ValueError("max_hold_sessions must be positive")
    if commission_rate < 0 or slippage_rate < 0:
        raise ValueError("cost rates must not be negative")
    bars = tuple(
        sorted(
            (bar for bar in subsequent_bars if bar.trade_date > plan.signal_date),
            key=lambda item: item.trade_date,
        )
    )
    if not bars:
        return ProxyTrade(plan.code, plan.signal_date, "NO_NEXT_SESSION")

    entry_bar = bars[0]
    if entry_bar.open > plan.entry_ceiling:
        return ProxyTrade(plan.code, plan.signal_date, "GAP_REJECTED")
    if entry_bar.high < plan.trigger_price:
        return ProxyTrade(plan.code, plan.signal_date, "UNTRIGGERED")
    raw_entry = entry_bar.open if entry_bar.open >= plan.trigger_price else plan.trigger_price
    entry_price = raw_entry * (1.0 + slippage_rate)

    for index, bar in enumerate(bars[:max_hold_sessions]):
        if bar.low <= plan.invalidation_price:
            raw_exit = min(bar.open, plan.invalidation_price)
            exit_price = raw_exit * (1.0 - slippage_rate)
            return _closed_trade(
                plan,
                entry_date=entry_bar.trade_date,
                entry_price=entry_price,
                exit_date=bar.trade_date,
                exit_price=exit_price,
                exit_reason="STOP",
                commission_rate=commission_rate,
            )
        if bar.high >= plan.target_price:
            raw_exit = max(bar.open, plan.target_price)
            exit_price = raw_exit * (1.0 - slippage_rate)
            return _closed_trade(
                plan,
                entry_date=entry_bar.trade_date,
                entry_price=entry_price,
                exit_date=bar.trade_date,
                exit_price=exit_price,
                exit_reason="TARGET",
                commission_rate=commission_rate,
            )
        if index == max_hold_sessions - 1:
            exit_price = bar.close * (1.0 - slippage_rate)
            return _closed_trade(
                plan,
                entry_date=entry_bar.trade_date,
                entry_price=entry_price,
                exit_date=bar.trade_date,
                exit_price=exit_price,
                exit_reason="TIME",
                commission_rate=commission_rate,
            )

    return ProxyTrade(
        code=plan.code,
        signal_date=plan.signal_date,
        status="OPEN",
        entry_date=entry_bar.trade_date,
        entry_price=entry_price,
    )


def _session_distance(start: date, end: date, market_dates: Sequence[date]) -> int:
    return sum(start < value <= end for value in market_dates)


def _max_drawdown(points: Sequence[EquityPoint]) -> float:
    peak = 0.0
    maximum = 0.0
    for point in points:
        peak = max(peak, point.equity)
        if peak > 0:
            maximum = max(maximum, (peak - point.equity) / peak)
    return maximum


def simulate_proxy_portfolio(
    opportunities: Sequence[ProxyOpportunity],
    *,
    market_dates: Sequence[date] | None = None,
    initial_capital: float = 100_000.0,
    commission_rate: float = 0.001,
    slippage_rate: float = 0.001,
    max_hold_sessions: int = 5,
    max_positions: int = 2,
    cooldown_sessions: int = 5,
) -> PortfolioBacktestResult:
    """Admit proxy trades to finite slots and mark a daily cash-plus-position NAV."""

    if initial_capital <= 0 or max_positions <= 0:
        raise ValueError("capital and max_positions must be positive")
    all_dates = tuple(
        sorted(
            set(market_dates or ())
            | {bar.trade_date for opportunity in opportunities for bar in opportunity.bars}
        )
    )
    simulated = [
        (
            opportunity,
            simulate_proxy_trade(
                opportunity.plan,
                opportunity.bars,
                commission_rate=commission_rate,
                slippage_rate=slippage_rate,
                max_hold_sessions=max_hold_sessions,
            ),
        )
        for opportunity in opportunities
    ]
    simulated.sort(
        key=lambda item: (
            item[1].entry_date or date.max,
            item[0].plan.signal_date,
            item[0].plan.code,
        )
    )

    admitted: list[tuple[ProxyOpportunity, ProxyTrade]] = []
    rejected: list[ProxyTrade] = []
    for opportunity, trade in simulated:
        if trade.status != "CLOSED" or trade.entry_date is None or trade.exit_date is None:
            rejected.append(trade)
            continue
        prior_same_code = [item for _, item in admitted if item.code == trade.code]
        if any(
            previous.entry_date <= trade.entry_date <= previous.exit_date
            for previous in prior_same_code
            if previous.entry_date is not None and previous.exit_date is not None
        ):
            rejected.append(replace(trade, status="OVERLAP_REJECTED"))
            continue
        latest_exit = max(
            (item.exit_date for item in prior_same_code if item.exit_date is not None),
            default=None,
        )
        if (
            latest_exit is not None
            and latest_exit < trade.entry_date
            and _session_distance(latest_exit, trade.entry_date, all_dates) <= cooldown_sessions
        ):
            rejected.append(replace(trade, status="COOLDOWN_REJECTED"))
            continue
        concurrent = sum(
            item.entry_date <= trade.entry_date <= item.exit_date
            for _, item in admitted
            if item.entry_date is not None and item.exit_date is not None
        )
        if concurrent >= max_positions:
            rejected.append(replace(trade, status="CAPACITY_REJECTED"))
            continue
        capital_allocated = initial_capital / max_positions
        quantity = capital_allocated / (trade.entry_price * (1.0 + commission_rate))
        admitted.append(
            (
                opportunity,
                replace(
                    trade,
                    capital_allocated=capital_allocated,
                    quantity=quantity,
                ),
            )
        )

    close_by_code_date = {
        (opportunity.plan.code, bar.trade_date): bar.close
        for opportunity in opportunities
        for bar in opportunity.bars
    }
    cash = initial_capital
    equity_curve: list[EquityPoint] = []
    last_close: dict[str, float] = {}
    for current_date in all_dates:
        for (code, bar_date), close in close_by_code_date.items():
            if bar_date == current_date:
                last_close[code] = close
        for _, trade in admitted:
            if trade.entry_date == current_date:
                cash -= trade.quantity * trade.entry_price * (1.0 + commission_rate)
        for _, trade in admitted:
            if trade.exit_date == current_date:
                cash += trade.quantity * trade.exit_price * (1.0 - commission_rate)
        marked_positions = sum(
            trade.quantity * last_close.get(trade.code, trade.entry_price)
            for _, trade in admitted
            if trade.entry_date <= current_date < trade.exit_date
        )
        equity_curve.append(EquityPoint(current_date, cash + marked_positions))

    ending_capital = equity_curve[-1].equity if equity_curve else initial_capital
    return PortfolioBacktestResult(
        trades=tuple(trade for _, trade in admitted),
        rejections=tuple(rejected),
        equity_curve=tuple(equity_curve),
        initial_capital=initial_capital,
        ending_capital=ending_capital,
        max_drawdown=_max_drawdown(equity_curve),
    )
