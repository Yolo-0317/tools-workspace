from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

from stock_ai.buy_point_selection.models import BuyPointBar

from .models import CandidateRole, MemberSnapshot, PriceLevels, RotationCandidate, RotationPolicy

_CENT = Decimal("0.01")


def _price(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def calculate_price_levels(
    candidate: RotationCandidate,
    member: MemberSnapshot,
    bars: Sequence[BuyPointBar],
    policy: RotationPolicy,
) -> PriceLevels | None:
    del policy
    if (
        len(bars) < 20
        or not candidate.formal_eligible
        or not member.data_complete
        or member.atr14 <= 0
        or member.ma5 <= 0
        or member.ma10 <= 0
        or member.ma20 <= 0
    ):
        return None

    recent = tuple(bars[-20:])
    structure_high = max(value.high for value in recent)
    structure_low = min(value.low for value in recent)
    if abs(structure_high - member.high20) > _CENT or abs(structure_low - member.low20) > _CENT:
        return None

    if candidate.role in {CandidateRole.LEADER, CandidateRole.CATCH_UP}:
        platform_support = max(value.low for value in recent[-5:])
        watch = max(member.ma5, platform_support)
        trigger = structure_high + Decimal("0.10") * member.atr14
        relevant_low = structure_low
    elif candidate.role is CandidateRole.PULLBACK:
        watch = (member.ma5 + member.ma10) / Decimal("2")
        reversal_high = max(value.high for value in recent[-5:])
        trigger = reversal_high + Decimal("0.05") * member.atr14
        relevant_low = min(value.low for value in recent[-10:])
    else:
        return None

    invalidation = min(
        relevant_low - Decimal("0.10") * member.atr14,
        member.ma20,
    )
    no_chase = min(trigger * Decimal("1.05"), member.ma5 * Decimal("1.05"))
    levels = PriceLevels(
        watch_price=_price(watch),
        trigger_price=_price(trigger),
        no_chase_price=_price(no_chase),
        invalidation_price=_price(invalidation),
    )
    if not (
        levels.invalidation_price
        < levels.watch_price
        <= levels.trigger_price
        < levels.no_chase_price
    ):
        return None
    return levels
