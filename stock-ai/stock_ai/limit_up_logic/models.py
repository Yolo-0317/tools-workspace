from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal


LimitUpGene = Literal["STRONG", "MEDIUM", "WEAK", "UNKNOWN"]
LimitUpIdentity = Literal[
    "DATA_INSUFFICIENT",
    "RISK_VETOED",
    "RELAY_FAILED",
    "SECOND_WAVE_CANDIDATE",
    "POST_LIMIT_HOLDING",
    "FIRST_BOARD_SETUP",
    "NORMAL_TREND",
]


@dataclass(frozen=True)
class LimitUpBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    pct_chg: float
    amount: float
    pre_close: float | None = None
    turnover_rate: float | None = None


@dataclass(frozen=True)
class LimitUpContext:
    concepts: tuple[str, ...] = ()
    active_themes: tuple[str, ...] = ()
    sector_change_pct: float | None = None
    sector_limit_up_count: int | None = None
    sector_leader_strength: str = "unknown"
    main_net_inflow_ratio: float | None = None
    consecutive_inflow_days: int | None = None
    material_risk: bool = False
    material_risk_reasons: tuple[str, ...] = ()
    auction_strength: str = "unknown"
    seal_quality: str = "unknown"
    reopen_count: int | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True)
class LimitUpFeatures:
    bar_count: int
    data_sufficient: bool
    trend_complete: bool
    limit_up_gene: LimitUpGene
    recent_limit_up_count: int
    recent_limit_up_indices: tuple[int, ...]
    days_since_last_limit_up: int | None
    last_limit_up_date: date | None
    last_limit_up_close: float | None
    last_limit_up_low: float | None
    post_limit_retention: bool
    post_limit_support_broken: bool
    post_limit_volume_breakdown: bool
    post_limit_holding_days: int
    post_limit_shrink: bool
    ma5: float | None
    ma10: float | None
    ma20: float | None
    amount_ratio5: float | None
    amount_ratio20: float | None
    close_location: float | None
    upper_shadow_ratio: float | None
    return5: float | None
    distance_from_last_limit_close: float | None
    distance_from_prior_high20: float | None
    latest_pct_chg: float | None
    latest_trade_date: date | None
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class LimitUpScoreBreakdown:
    gene: int
    price_volume: int
    theme_sector: int
    fund_flow: int

    @property
    def total(self) -> int:
        return self.gene + self.price_volume + self.theme_sector + self.fund_flow


@dataclass(frozen=True)
class LimitUpPaths:
    acceleration: int
    continuation: int
    failure: int

    def as_tuple(self) -> tuple[int, int, int]:
        return self.acceleration, self.continuation, self.failure


@dataclass(frozen=True)
class LimitUpResult:
    code: str
    name: str
    identity: LimitUpIdentity
    gene: LimitUpGene
    score: LimitUpScoreBreakdown
    paths: LimitUpPaths
    drivers: tuple[str, ...]
    prerequisites: tuple[str, ...]
    suppressors: tuple[str, ...]
    missing_fields: tuple[str, ...]
    data_cutoff: datetime | date | None
    new_risk_forbidden: bool = False

