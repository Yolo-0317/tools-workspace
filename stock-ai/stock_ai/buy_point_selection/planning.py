"""Price-plan math and stable buy-point structure identity."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Sequence

from stock_ai.market_codes import normalize_code6

from .models import BuyPointBar, DetectedSetup, SelectionPolicy, SetupType


CENT = Decimal("0.01")
BOARD_LOT = Decimal("100")


@dataclass(frozen=True)
class RiskBudget:
    loss_budget: Decimal
    ticket_limit: Decimal
    remaining_exposure: Decimal


@dataclass(frozen=True)
class PricePlan:
    structure_id: str
    code: str
    setup_type: SetupType
    signal_date: date
    signal_close: Decimal
    trigger_price: Decimal
    invalidation_price: Decimal
    target_2r: Decimal
    risk_distance: Decimal
    risk_reward_ratio: Decimal
    maximum_shares: int
    valid_through_trade_date: date


@dataclass(frozen=True)
class PlanDecision:
    plan: PricePlan | None
    reasons: tuple[str, ...]


def _ceil_cent(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_CEILING)


def _floor_cent(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_FLOOR)


def _floor_board_lot(value: Decimal) -> int:
    lots = (value / BOARD_LOT).to_integral_value(rounding=ROUND_FLOOR)
    return int(lots * BOARD_LOT)


def _second_weekday_after(value: date) -> date:
    current = value
    remaining = 2
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def atr14(bars: Sequence[BuyPointBar]) -> Decimal:
    ordered = tuple(sorted(bars, key=lambda value: value.trade_date))
    if len(ordered) < 14:
        return Decimal("NaN")
    true_ranges: list[Decimal] = []
    start = len(ordered) - 14
    for index in range(start, len(ordered)):
        value = ordered[index]
        previous_close = ordered[index - 1].close if index else value.close
        true_ranges.append(
            max(
                value.high - value.low,
                abs(value.high - previous_close),
                abs(value.low - previous_close),
            )
        )
    return sum(true_ranges, Decimal("0")) / Decimal("14")


def nearest_resistance_above(trigger: Decimal, bars: Sequence[BuyPointBar]) -> Decimal:
    levels = [value.high for value in bars[-60:] if value.high > trigger]
    return min(levels) if levels else Decimal("Infinity")


def structure_id(code: str, setup: DetectedSetup, rule_version: str) -> str:
    payload = ":".join(
        (
            normalize_code6(code),
            setup.setup_type.value,
            setup.structure_start.isoformat(),
            f"{setup.structure_high:.2f}",
            f"{setup.structure_low:.2f}",
            rule_version,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def build_price_plan(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
    budget: RiskBudget,
    market_status: str,
    policy: SelectionPolicy | None = None,
    *,
    valid_through_trade_date: date | None = None,
) -> PlanDecision:
    resolved = policy or SelectionPolicy()
    ordered = tuple(sorted(bars, key=lambda value: value.trade_date))
    if market_status == "FREEZE":
        return PlanDecision(None, ("MARKET_FREEZE",))
    if market_status not in {"ALLOW", "LIMITED"}:
        return PlanDecision(None, ("UNKNOWN_MARKET_STATUS",))
    if not ordered:
        return PlanDecision(None, ("PRICE_HISTORY_MISSING",))

    volatility = atr14(ordered)
    if not volatility.is_finite() or volatility <= 0:
        return PlanDecision(None, ("ATR_UNAVAILABLE",))
    trigger = _ceil_cent(setup.structure_high + CENT)
    invalidation = _floor_cent(setup.structure_low - Decimal("0.2") * volatility)
    risk = trigger - invalidation
    risk_pct = risk / trigger
    minimum_risk_pct = max(Decimal("0.015"), Decimal("0.8") * volatility / trigger)
    if not minimum_risk_pct <= risk_pct <= Decimal("0.05"):
        return PlanDecision(None, ("RISK_DISTANCE_OUT_OF_RANGE",))

    target = _ceil_cent(trigger + Decimal("2") * risk)
    if nearest_resistance_above(trigger, ordered) < target:
        return PlanDecision(None, ("INSUFFICIENT_TWO_R_SPACE",))

    loss_budget = budget.loss_budget
    ticket_limit = budget.ticket_limit
    if market_status == "LIMITED":
        loss_budget /= Decimal("2")
        ticket_limit /= Decimal("2")
    maximum_value = min(
        ticket_limit / trigger,
        loss_budget / risk,
        budget.remaining_exposure / trigger,
    )
    shares = _floor_board_lot(maximum_value)
    if shares < 100:
        return PlanDecision(None, ("POSITION_BELOW_BOARD_LOT",))

    return PlanDecision(
        PricePlan(
            structure_id=structure_id(setup.code, setup, resolved.rule_version),
            code=normalize_code6(setup.code),
            setup_type=setup.setup_type,
            signal_date=setup.analysis_date,
            signal_close=ordered[-1].close,
            trigger_price=trigger,
            invalidation_price=invalidation,
            target_2r=target,
            risk_distance=risk,
            risk_reward_ratio=(target - trigger) / risk,
            maximum_shares=shares,
            valid_through_trade_date=(
                valid_through_trade_date
                if valid_through_trade_date is not None
                else _second_weekday_after(setup.analysis_date)
            ),
        ),
        (),
    )
