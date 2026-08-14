"""Pure diagnostic models for short-window buy-point case reviews."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping

from stock_ai.market_codes import normalize_code6


ALLOWED_SOFT_REASONS = frozenset(
    {
        "SECTOR_RELATIVE_STRENGTH_WEAK",
        "SECTOR_BREADTH_WEAK",
        "SECTOR_NOT_RESONATING",
        "SECTOR_AMOUNT_WEAK",
        "INSUFFICIENT_TWO_R_SPACE",
        "RISK_DISTANCE_OUT_OF_RANGE",
    }
)


@dataclass(frozen=True)
class GateTrace:
    code: str
    signal_date: date
    failed_reasons: tuple[str, ...]
    passed_stages: tuple[str, ...]
    metrics: Mapping[str, Decimal]

    @property
    def first_rejection(self) -> str | None:
        return self.failed_reasons[0] if self.failed_reasons else None


@dataclass(frozen=True)
class NearMissDecision:
    admitted: bool
    soft_reason: str | None
    ranking_key: tuple[Decimal | str, ...] | None


def classify_near_miss(
    trace: GateTrace,
    *,
    setup_quality: Decimal,
    average_amount5_qian: Decimal,
) -> NearMissDecision:
    """Admit only one explicitly approved soft-gate failure."""
    reasons = tuple(dict.fromkeys(trace.failed_reasons))
    if len(reasons) != 1 or reasons[0] not in ALLOWED_SOFT_REASONS:
        return NearMissDecision(False, None, None)
    deviation = Decimal(str(trace.metrics.get("boundary_deviation", Decimal("1"))))
    return NearMissDecision(
        admitted=True,
        soft_reason=reasons[0],
        ranking_key=(
            deviation,
            -setup_quality,
            -average_amount5_qian,
            normalize_code6(trace.code),
        ),
    )
