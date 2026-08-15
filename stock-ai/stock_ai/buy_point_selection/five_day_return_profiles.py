"""Immutable entry/stop profiles for five-day return shadow research."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
from typing import Sequence

from .models import BuyPointBar, DetectedSetup
from .planning import _floor_cent, atr14


FIVE_DAY_RULE_VERSION = "five-day-return-shadow-1.0.0"
SIZING_VERSION = "target-notional-10000-board-lot-100-v1"


@dataclass(frozen=True)
class FiveDayReturnProfile:
    profile_id: str
    entry_kind: str
    stop_kind: str


@dataclass(frozen=True)
class EvaluationSizing:
    target_notional: Decimal = Decimal("10000")
    board_lot: int = 100
    version: str = SIZING_VERSION


@dataclass(frozen=True)
class EvaluationPosition:
    evaluation_target_notional: Decimal
    evaluation_shares: int
    evaluation_notional: Decimal
    minimum_lot_exceeds_target: bool
    executable_shares: int = 0


@dataclass(frozen=True)
class StopDecision:
    stop_price: Decimal | None
    risk_fraction: Decimal | None
    reasons: tuple[str, ...]


_PROFILE_SPECS = (
    ("BREAKOUT_TRIGGER", "FIXED_3_PERCENT"),
    ("BREAKOUT_TRIGGER", "STRUCTURE_ATR"),
    ("PULLBACK_RECLAIM", "FIXED_3_PERCENT"),
    ("PULLBACK_RECLAIM", "STRUCTURE_ATR"),
)


def build_five_day_return_profiles() -> tuple[FiveDayReturnProfile, ...]:
    return tuple(
        FiveDayReturnProfile(
            profile_id=f"{entry_kind}__{stop_kind}",
            entry_kind=entry_kind,
            stop_kind=stop_kind,
        )
        for entry_kind, stop_kind in _PROFILE_SPECS
    )


def validate_five_day_return_profiles(
    profiles: Sequence[FiveDayReturnProfile],
) -> None:
    if tuple(profiles) != build_five_day_return_profiles():
        raise ValueError("unsupported five-day return profile matrix")


def five_day_profile_hash(profiles: Sequence[FiveDayReturnProfile]) -> str:
    validate_five_day_return_profiles(profiles)
    payload = [
        {
            "entry_kind": value.entry_kind,
            "profile_id": value.profile_id,
            "stop_kind": value.stop_kind,
        }
        for value in profiles
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def evaluation_position(
    entry_price: Decimal,
    sizing: EvaluationSizing | None = None,
) -> EvaluationPosition:
    if not entry_price.is_finite() or entry_price <= 0:
        raise ValueError("entry price must be finite and positive")
    resolved = sizing or EvaluationSizing()
    lots = (
        resolved.target_notional / entry_price / Decimal(resolved.board_lot)
    ).to_integral_value(rounding=ROUND_FLOOR)
    shares = max(resolved.board_lot, int(lots) * resolved.board_lot)
    notional = entry_price * Decimal(shares)
    return EvaluationPosition(
        evaluation_target_notional=resolved.target_notional,
        evaluation_shares=shares,
        evaluation_notional=notional,
        minimum_lot_exceeds_target=notional > resolved.target_notional,
    )


def structure_atr_stop(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
) -> Decimal | None:
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
        return None
    volatility = atr14(bounded)
    if not volatility.is_finite() or volatility <= 0:
        return None
    result = _floor_cent(
        setup.structure_low - Decimal("0.2") * volatility
    )
    if not result.is_finite() or result <= 0:
        return None
    return result


def resolve_profile_stop(
    profile: FiveDayReturnProfile,
    entry_price: Decimal,
    structure_stop: Decimal | None,
) -> StopDecision:
    if profile not in build_five_day_return_profiles():
        raise ValueError("unsupported five-day return profile")
    if not entry_price.is_finite() or entry_price <= 0:
        raise ValueError("entry price must be finite and positive")

    if profile.stop_kind == "FIXED_3_PERCENT":
        stop_price = _floor_cent(entry_price * Decimal("0.97"))
    else:
        if (
            structure_stop is None
            or not structure_stop.is_finite()
            or structure_stop <= 0
        ):
            return StopDecision(None, None, ("STRUCTURE_STOP_UNAVAILABLE",))
        stop_price = structure_stop

    risk_fraction = (entry_price - stop_price) / entry_price
    if profile.stop_kind == "STRUCTURE_ATR" and not (
        Decimal("0.015") <= risk_fraction <= Decimal("0.05")
    ):
        return StopDecision(
            None,
            risk_fraction,
            ("RISK_DISTANCE_OUT_OF_RANGE",),
        )
    return StopDecision(stop_price, risk_fraction, ())
