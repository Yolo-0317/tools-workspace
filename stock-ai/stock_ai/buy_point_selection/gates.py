"""Fail-closed market, universe, overheat, and sector gates."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6

from .models import (
    BuyPointBar,
    GateDecision,
    MarketSnapshot,
    SectorSnapshot,
    SelectionPolicy,
)
from .reference_data import RiskFlag


def classify_market(value: MarketSnapshot) -> GateDecision:
    if not value.complete:
        return GateDecision(False, "FREEZE", ("MARKET_DATA_INCOMPLETE",))
    if value.indexes_above_ma20 <= 1 and value.breadth_pct < 40:
        return GateDecision(False, "FREEZE", ("INDEX_AND_BREADTH_WEAK",))
    if value.amount_ratio < 0.75 and value.breadth_pct < 45:
        return GateDecision(False, "FREEZE", ("AMOUNT_AND_BREADTH_WEAK",))
    if (
        value.indexes_above_ma20 >= 2
        and value.breadth_pct >= 50
        and value.amount_ratio >= 0.90
    ):
        return GateDecision(True, "ALLOW", ())
    return GateDecision(True, "LIMITED", ("MARKET_LIMITED",))


def base_gate(
    code: str,
    bars: Sequence[BuyPointBar],
    holding_codes: set[str],
    risk_flags_by_code: Mapping[str, Sequence[RiskFlag]],
    policy: SelectionPolicy,
) -> GateDecision:
    normalized = normalize_code6(code)
    reasons: list[str] = []
    if not is_sh_sz_main_board_code(normalized):
        reasons.append("NON_MAIN_BOARD")
    if normalized in {normalize_code6(value) for value in holding_codes}:
        reasons.append("EXISTING_HOLDING")
    if any(flag.severity == "VETO" for flag in risk_flags_by_code.get(normalized, ())):
        reasons.append("POINT_IN_TIME_RISK_VETO")
    ordered = tuple(sorted(bars, key=lambda item: item.trade_date))
    if len(ordered) < policy.min_history:
        reasons.append("HISTORY_TOO_SHORT")
    if len({bar.trade_date for bar in ordered}) != len(ordered):
        reasons.append("DUPLICATE_TRADE_DATE")
    recent = ordered[-20:]
    if any(
        bar.amount_qian <= 0
        or bar.open <= 0
        or bar.high <= 0
        or bar.low <= 0
        or bar.close <= 0
        or bar.high < bar.low
        for bar in recent
    ):
        reasons.append("INVALID_OR_SUSPENDED_BAR")
    if len(ordered) >= 5:
        average_amount5 = sum((bar.amount_qian for bar in ordered[-5:]), Decimal("0")) / Decimal("5")
        if average_amount5 < policy.min_average_amount5_qian:
            reasons.append("LIQUIDITY_TOO_LOW")
    return GateDecision(not reasons, "PASS" if not reasons else "REJECT", tuple(reasons))


def anti_chase_gate(
    signal_gain_pct: float | Decimal,
    return3_pct: float | Decimal,
    return5_pct: float | Decimal,
    ma5_distance_pct: float | Decimal,
    ma20_distance_pct: float | Decimal,
    policy: SelectionPolicy,
) -> GateDecision:
    values = (
        (Decimal(str(signal_gain_pct)), policy.max_signal_gain_pct, "SIGNAL_DAY_OVERHEATED"),
        (Decimal(str(return3_pct)), policy.max_return3_pct, "RETURN_3D_OVERHEATED"),
        (Decimal(str(return5_pct)), policy.max_return5_pct, "RETURN_5D_OVERHEATED"),
        (Decimal(str(ma5_distance_pct)), policy.max_ma5_distance_pct, "MA5_DISTANCE_OVERHEATED"),
        (Decimal(str(ma20_distance_pct)), policy.max_ma20_distance_pct, "MA20_DISTANCE_OVERHEATED"),
    )
    reasons = tuple(reason for value, maximum, reason in values if value > maximum)
    return GateDecision(not reasons, "PASS" if not reasons else "REJECT", reasons)


def sector_gate(value: SectorSnapshot, policy: SelectionPolicy | None = None) -> GateDecision:
    resolved = policy or SelectionPolicy()
    reasons: list[str] = []
    if not value.membership_complete:
        reasons.append("SECTOR_MEMBERSHIP_INCOMPLETE")
    if value.liquid_member_count < resolved.sector_liquid_members_min:
        reasons.append("SECTOR_SAMPLE_TOO_SMALL")
    if value.return_percentile < resolved.sector_return_percentile_min:
        reasons.append("SECTOR_RELATIVE_STRENGTH_WEAK")
    if value.strengthening_member_count < resolved.sector_strengthening_members_min:
        reasons.append("SECTOR_NOT_RESONATING")
    if value.breadth_ratio < resolved.sector_breadth_min:
        reasons.append("SECTOR_BREADTH_WEAK")
    if value.amount_ratio < resolved.sector_amount_ratio_min:
        reasons.append("SECTOR_AMOUNT_WEAK")
    return GateDecision(not reasons, "PASS" if not reasons else "REJECT", tuple(reasons))
