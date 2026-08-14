"""Immutable domain models for buy-point-first selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Mapping


class SetupType(str, Enum):
    PRE_BREAKOUT = "PRE_BREAKOUT"
    TREND_PULLBACK = "TREND_PULLBACK"
    FIRST_LAUNCH_PULLBACK = "FIRST_LAUNCH_PULLBACK"


class CandidateTier(str, Enum):
    FORMAL = "FORMAL"
    OBSERVE = "OBSERVE"
    SHADOW = "SHADOW"


class PlanState(str, Enum):
    PREPARED = "PREPARED"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class BuyPointBar:
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    pct_chg: Decimal
    amount_qian: Decimal


@dataclass(frozen=True)
class MarketSnapshot:
    indexes_above_ma20: int
    breadth_pct: float
    amount_ratio: float
    complete: bool


@dataclass(frozen=True)
class SectorSnapshot:
    sector_code: str
    sector_name: str
    return_percentile: float
    liquid_member_count: int
    strengthening_member_count: int
    breadth_ratio: float
    amount_ratio: float
    membership_complete: bool


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    status: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DetectedSetup:
    code: str
    setup_type: SetupType
    analysis_date: date
    structure_start: date
    structure_high: Decimal
    structure_low: Decimal
    quality: Decimal
    reasons: tuple[str, ...]
    metrics: Mapping[str, Decimal]


@dataclass(frozen=True)
class SelectionPolicy:
    rule_version: str = "buy-point-selection-3.0.0"
    min_history: int = 60
    min_average_amount5_qian: Decimal = Decimal("100000")
    max_signal_gain_pct: Decimal = Decimal("5")
    max_return3_pct: Decimal = Decimal("8")
    max_return5_pct: Decimal = Decimal("12")
    max_ma5_distance_pct: Decimal = Decimal("5")
    max_ma20_distance_pct: Decimal = Decimal("12")
    sector_return_percentile_min: float = 0.70
    sector_liquid_members_min: int = 5
    sector_strengthening_members_min: int = 2
    sector_breadth_min: float = 0.50
    sector_amount_ratio_min: float = 0.80
    platform_window: int = 30
    platform_width_max: Decimal = Decimal("0.12")
    platform_near_top_max: Decimal = Decimal("0.03")
    platform_contraction_max: Decimal = Decimal("0.80")
    platform_amount_ratio_max: Decimal = Decimal("0.80")
    trend_return10_min: Decimal = Decimal("0.05")
    trend_return10_max: Decimal = Decimal("0.18")
    trend_drawdown_min: Decimal = Decimal("0.02")
    trend_drawdown_max: Decimal = Decimal("0.08")
    pullback_amount_ratio_max: Decimal = Decimal("0.80")
    launch_gain_min: Decimal = Decimal("0.02")
    launch_gain_max: Decimal = Decimal("0.05")
    launch_amount_ratio_min: Decimal = Decimal("1.30")
    launch_amount_ratio_max: Decimal = Decimal("2.20")
    launch_close_location_min: Decimal = Decimal("0.70")
    consolidation_gain_abs_max: Decimal = Decimal("0.02")
    consolidation_amount_ratio_max: Decimal = Decimal("0.80")
    max_gap_pct: Decimal = Decimal("3")
    max_trigger_gain_pct: Decimal = Decimal("5")
    max_formal_candidates: int = 3
    limited_candidates: int = 1
