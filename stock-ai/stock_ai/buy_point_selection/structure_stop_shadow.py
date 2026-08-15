"""Pure, zero-share stop-anchor shadows for buy-point case research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Sequence

from stock_ai.market_codes import normalize_code6

from .models import BuyPointBar, DetectedSetup, SelectionPolicy, SetupType
from .planning import (
    PlanDecision,
    PricePlan,
    RiskBudget,
    _ceil_cent,
    _floor_board_lot,
    _floor_cent,
    _second_weekday_after,
    atr14,
    nearest_resistance_above,
    structure_id,
)


@dataclass(frozen=True)
class StructureStopProfile:
    profile_id: str
    anchor_kind: str
    uses_atr_buffer: bool


@dataclass(frozen=True)
class StructureStopAnchor:
    profile: StructureStopProfile
    code: str
    signal_date: date
    anchor_price: Decimal | None
    invalidation_price: Decimal | None
    reasons: tuple[str, ...]
    executable_shares: int = 0


_PROFILE_SPECS = (
    ("STRUCTURE_STOP:RECENT_SETUP_LOW", "RECENT_SETUP_LOW", True),
    ("STRUCTURE_STOP:DYNAMIC_SUPPORT", "DYNAMIC_SUPPORT", True),
    ("STRUCTURE_STOP:ATR_1_5", "ATR_1_5", False),
)


def build_structure_stop_profiles() -> tuple[StructureStopProfile, ...]:
    return tuple(StructureStopProfile(*value) for value in _PROFILE_SPECS)


def validate_structure_stop_profiles(
    profiles: Sequence[StructureStopProfile],
) -> None:
    if tuple(profiles) != build_structure_stop_profiles():
        raise ValueError("unsupported structure stop profile matrix")


def structure_stop_profile_hash(
    profiles: Sequence[StructureStopProfile],
) -> str:
    validate_structure_stop_profiles(profiles)
    payload = [
        {
            "profile_id": value.profile_id,
            "anchor_kind": value.anchor_kind,
            "uses_atr_buffer": value.uses_atr_buffer,
        }
        for value in profiles
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _bounded_bars(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
) -> tuple[BuyPointBar, ...]:
    bounded = tuple(
        sorted(
            (value for value in bars if value.trade_date <= setup.analysis_date),
            key=lambda value: value.trade_date,
        )
    )
    if (
        not bounded
        or bounded[-1].trade_date != setup.analysis_date
        or len({value.trade_date for value in bounded}) != len(bounded)
    ):
        return ()
    return bounded


def _session_count(setup: DetectedSetup, key: str) -> int | None:
    raw = setup.metrics.get(key)
    if raw is None or not raw.is_finite() or raw != raw.to_integral_value():
        return None
    value = int(raw)
    return value if value > 0 else None


def recent_setup_low(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
) -> Decimal | None:
    bounded = _bounded_bars(setup, bars)
    if not bounded:
        return None
    if setup.setup_type is SetupType.PRE_BREAKOUT:
        sessions = 10
    elif setup.setup_type is SetupType.TREND_PULLBACK:
        sessions = _session_count(setup, "pullback_sessions")
    elif setup.setup_type is SetupType.FIRST_LAUNCH_PULLBACK:
        sessions = _session_count(setup, "quiet_sessions")
    else:
        return None
    if sessions is None or sessions > len(bounded):
        return None
    result = min(value.low for value in bounded[-sessions:])
    if not result.is_finite() or result <= 0:
        return None
    return result


def _moving_average(
    bars: Sequence[BuyPointBar], period: int
) -> Decimal | None:
    if len(bars) < period:
        return None
    values = tuple(value.close for value in bars[-period:])
    if any(not value.is_finite() or value <= 0 for value in values):
        return None
    return sum(values, Decimal("0")) / Decimal(period)


def dynamic_support_anchor(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
) -> Decimal | None:
    bounded = _bounded_bars(setup, bars)
    if not bounded:
        return None
    candidates = (
        _moving_average(bounded, 10),
        _moving_average(bounded, 20),
        recent_setup_low(setup, bounded),
    )
    signal_low = bounded[-1].low
    valid = tuple(
        value
        for value in candidates
        if value is not None
        and value.is_finite()
        and value > 0
        and value <= signal_low
    )
    return max(valid) if valid else None


def build_structure_stop_anchor(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
    profile: StructureStopProfile,
) -> StructureStopAnchor:
    if profile not in build_structure_stop_profiles():
        raise ValueError("unsupported structure stop profile")
    bounded = _bounded_bars(setup, bars)
    if not bounded:
        return StructureStopAnchor(
            profile,
            normalize_code6(setup.code),
            setup.analysis_date,
            None,
            None,
            ("PRICE_HISTORY_MISSING",),
        )
    volatility = atr14(bounded)
    if not volatility.is_finite() or volatility <= 0:
        return StructureStopAnchor(
            profile,
            normalize_code6(setup.code),
            setup.analysis_date,
            None,
            None,
            ("ATR_UNAVAILABLE",),
        )
    trigger = _ceil_cent(setup.structure_high + Decimal("0.01"))
    if profile.anchor_kind == "ATR_1_5":
        invalidation = _floor_cent(trigger - Decimal("1.5") * volatility)
        anchor_price = invalidation
    elif profile.anchor_kind == "RECENT_SETUP_LOW":
        anchor_price = recent_setup_low(setup, bounded)
        if anchor_price is None:
            return StructureStopAnchor(
                profile,
                normalize_code6(setup.code),
                setup.analysis_date,
                None,
                None,
                ("RECENT_SETUP_LOW_UNAVAILABLE",),
            )
        invalidation = _floor_cent(
            anchor_price - Decimal("0.2") * volatility
        )
    else:
        anchor_price = dynamic_support_anchor(setup, bounded)
        if anchor_price is None:
            return StructureStopAnchor(
                profile,
                normalize_code6(setup.code),
                setup.analysis_date,
                None,
                None,
                ("SUPPORT_ANCHOR_UNAVAILABLE",),
            )
        invalidation = _floor_cent(
            anchor_price - Decimal("0.2") * volatility
        )
    if anchor_price > bounded[-1].low:
        return StructureStopAnchor(
            profile,
            normalize_code6(setup.code),
            setup.analysis_date,
            anchor_price,
            invalidation,
            ("ANCHOR_ABOVE_SIGNAL_LOW",),
        )
    return StructureStopAnchor(
        profile,
        normalize_code6(setup.code),
        setup.analysis_date,
        anchor_price,
        invalidation,
        (),
    )


def build_structure_stop_plan(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
    budget: RiskBudget,
    market_status: str,
    profile: StructureStopProfile,
    policy: SelectionPolicy | None = None,
    *,
    valid_through_trade_date: date | None = None,
) -> PlanDecision:
    resolved = policy or SelectionPolicy()
    if market_status == "FREEZE":
        return PlanDecision(None, ("MARKET_FREEZE",))
    if market_status not in {"ALLOW", "LIMITED"}:
        return PlanDecision(None, ("UNKNOWN_MARKET_STATUS",))
    bounded = _bounded_bars(setup, bars)
    if not bounded:
        return PlanDecision(None, ("PRICE_HISTORY_MISSING",))
    volatility = atr14(bounded)
    if not volatility.is_finite() or volatility <= 0:
        return PlanDecision(None, ("ATR_UNAVAILABLE",))
    anchor = build_structure_stop_anchor(setup, bounded, profile)
    if anchor.reasons or anchor.invalidation_price is None:
        return PlanDecision(None, anchor.reasons)
    trigger = _ceil_cent(setup.structure_high + Decimal("0.01"))
    risk = trigger - anchor.invalidation_price
    if risk <= 0:
        return PlanDecision(None, ("RISK_DISTANCE_OUT_OF_RANGE",))
    risk_fraction = risk / trigger
    minimum_risk_fraction = max(
        Decimal("0.015"), Decimal("0.8") * volatility / trigger
    )
    if not minimum_risk_fraction <= risk_fraction <= Decimal("0.05"):
        return PlanDecision(None, ("RISK_DISTANCE_OUT_OF_RANGE",))
    target = _ceil_cent(trigger + Decimal("2") * risk)
    if nearest_resistance_above(trigger, bounded) < target:
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
            structure_id(setup.code, setup, resolved.rule_version),
            normalize_code6(setup.code),
            setup.setup_type,
            setup.analysis_date,
            bounded[-1].close,
            trigger,
            anchor.invalidation_price,
            target,
            risk,
            Decimal("2"),
            shares,
            (
                valid_through_trade_date
                if valid_through_trade_date is not None
                else _second_weekday_after(setup.analysis_date)
            ),
        ),
        (),
    )
