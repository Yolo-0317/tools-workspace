"""Pure signal-time resistance profiles for case-analysis shadows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from .case_review import CaseCandidate, OpportunityEpisode
from .models import BuyPointBar
from .planning import atr14, nearest_resistance_above


LEGACY_ANY_HIGH = "LEGACY_ANY_HIGH"
LOCAL_PIVOT_HIGH = "LOCAL_PIVOT_HIGH"
REPEATED_PIVOT_CLUSTER = "REPEATED_PIVOT_CLUSTER"
VARIANT_ORDER = (
    LEGACY_ANY_HIGH,
    LOCAL_PIVOT_HIGH,
    REPEATED_PIVOT_CLUSTER,
)


@dataclass(frozen=True)
class ResistanceVariantProfile:
    variant: str
    level: Decimal | None
    effective_resistance_r: Decimal | None
    passes_two_r: bool
    touch_count: int


@dataclass(frozen=True)
class SignificantResistanceProfile:
    episode_id: str
    code: str
    signal_date: date
    structure_id: str
    setup_type: str
    atr14: Decimal
    tolerance: Decimal
    complete: bool
    variants: tuple[ResistanceVariantProfile, ...]


def _closed_variants() -> tuple[ResistanceVariantProfile, ...]:
    return tuple(
        ResistanceVariantProfile(variant, None, None, False, 0)
        for variant in VARIANT_ORDER
    )


def _incomplete_profile(
    episode: OpportunityEpisode,
) -> SignificantResistanceProfile:
    candidate = episode.representative
    return SignificantResistanceProfile(
        episode.episode_id,
        candidate.code,
        candidate.signal_date,
        candidate.plan.structure_id,
        candidate.setup.setup_type.value,
        Decimal("NaN"),
        Decimal("NaN"),
        False,
        _closed_variants(),
    )


def _valid_input(
    candidate: CaseCandidate,
    bars: Sequence[BuyPointBar],
) -> bool:
    if len(bars) != 60:
        return False
    if bars[-1].trade_date != candidate.signal_date:
        return False
    if len({value.trade_date for value in bars}) != len(bars):
        return False
    prices = tuple(
        price
        for value in bars
        for price in (value.open, value.high, value.low, value.close)
    )
    if any(not value.is_finite() or value <= 0 for value in prices):
        return False
    trigger = candidate.plan.trigger_price
    risk = candidate.plan.risk_distance
    return (
        trigger.is_finite()
        and trigger > 0
        and risk.is_finite()
        and risk > 0
    )


def _variant(
    variant: str,
    level: Decimal | None,
    candidate: CaseCandidate,
    touches: int,
) -> ResistanceVariantProfile:
    if level is None:
        return ResistanceVariantProfile(variant, None, None, True, 0)
    effective_r = (
        level - candidate.plan.trigger_price
    ) / candidate.plan.risk_distance
    return ResistanceVariantProfile(
        variant,
        level,
        effective_r,
        level >= candidate.plan.target_2r,
        touches,
    )


def _local_pivots(bars: Sequence[BuyPointBar]) -> tuple[tuple[int, date, Decimal], ...]:
    pivots = []
    for index in range(2, len(bars) - 2):
        current = bars[index].high
        left = (bars[index - 2].high, bars[index - 1].high)
        right = (bars[index + 1].high, bars[index + 2].high)
        if (
            all(current >= value for value in (*left, *right))
            and any(current > value for value in left)
            and any(current > value for value in right)
        ):
            pivots.append((index, bars[index].trade_date, current))
    return tuple(pivots)


def _repeated_pivot_cluster(
    pivots: Sequence[tuple[int, date, Decimal]],
    tolerance: Decimal,
) -> tuple[Decimal | None, int]:
    ordered = tuple(sorted(pivots, key=lambda value: (value[2], value[1], value[0])))
    windows: list[tuple[tuple[int, date, Decimal], ...]] = []
    for start in range(len(ordered)):
        for stop in range(start + 2, len(ordered) + 1):
            members = ordered[start:stop]
            if members[-1][2] - members[0][2] > tolerance:
                break
            indexes = tuple(value[0] for value in members)
            if all(
                abs(left - right) >= 3
                for position, left in enumerate(indexes)
                for right in indexes[position + 1 :]
            ):
                windows.append(members)
    maximal = tuple(
        members
        for members in windows
        if not any(
            set(members) < set(other)
            for other in windows
        )
    )
    if not maximal:
        return None, 0
    selected = min(
        maximal,
        key=lambda members: (
            sum((value[2] for value in members), Decimal("0")) / len(members),
            tuple(value[1] for value in members),
        ),
    )
    level = sum((value[2] for value in selected), Decimal("0")) / len(selected)
    return level, len(selected)


def analyze_significant_resistance(
    episode: OpportunityEpisode,
    bars: Sequence[BuyPointBar],
) -> SignificantResistanceProfile:
    candidate = episode.representative
    bounded = tuple(
        sorted(
            (value for value in bars if value.trade_date <= candidate.signal_date),
            key=lambda value: value.trade_date,
        )[-60:]
    )
    if not _valid_input(candidate, bounded):
        return _incomplete_profile(episode)
    volatility = atr14(bounded)
    if not volatility.is_finite() or volatility <= 0:
        return _incomplete_profile(episode)
    tolerance = max(
        Decimal("0.5") * volatility,
        Decimal("0.005") * candidate.plan.trigger_price,
    )
    legacy = nearest_resistance_above(candidate.plan.trigger_price, bounded)
    legacy_level = None if not legacy.is_finite() else legacy
    pivots = tuple(
        value
        for value in _local_pivots(bounded)
        if value[2] > candidate.plan.trigger_price
    )
    pivot_level = min((value[2] for value in pivots), default=None)
    pivot_touches = sum(value[2] == pivot_level for value in pivots)
    cluster_level, cluster_touches = _repeated_pivot_cluster(pivots, tolerance)
    return SignificantResistanceProfile(
        episode.episode_id,
        candidate.code,
        candidate.signal_date,
        candidate.plan.structure_id,
        candidate.setup.setup_type.value,
        volatility,
        tolerance,
        True,
        (
            _variant(LEGACY_ANY_HIGH, legacy_level, candidate, 1),
            _variant(LOCAL_PIVOT_HIGH, pivot_level, candidate, pivot_touches),
            _variant(
                REPEATED_PIVOT_CLUSTER,
                cluster_level,
                candidate,
                cluster_touches,
            ),
        ),
    )
