from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Mapping


class RotationState(str, Enum):
    LATENT = "LATENT"
    STARTING = "STARTING"
    CONFIRMED = "CONFIRMED"
    OVERHEATED = "OVERHEATED"
    FADING = "FADING"


class RotationBucket(str, Enum):
    STRONG = "STRONG"
    STRENGTHENING = "STRENGTHENING"
    PULLBACK = "PULLBACK"


class CandidateRole(str, Enum):
    LEADER = "LEADER"
    FOLLOWER = "FOLLOWER"
    CATCH_UP = "CATCH_UP"
    PULLBACK = "PULLBACK"


@dataclass(frozen=True)
class RotationPolicy:
    version: str = "sector-rotation-1.0.0"
    strongest_count: int = 3
    strengthening_count: int = 2
    pullback_count: int = 1
    observation_limit: int = 10
    formal_limit: int = 3
    latent_score_min: Decimal = Decimal("45")
    starting_score_min: Decimal = Decimal("60")
    confirm_snapshots: int = 2
    fading_score_drop: Decimal = Decimal("15")
    signal_day_overheat_pct: Decimal = Decimal("7")
    return5_overheat_pct: Decimal = Decimal("15")
    ma5_distance_overheat_pct: Decimal = Decimal("5")
    coexistence_overlap_max: Decimal = Decimal("0.30")


@dataclass(frozen=True)
class RawSectorRow:
    board_code: str
    sector_name: str
    rank: int
    change_pct: Decimal | float
    leader_code: str
    leader_name: str
    leader_change_pct: Decimal | float


@dataclass(frozen=True)
class ChainRule:
    chain_code: str
    chain_name: str
    parent_code: str
    aliases: tuple[str, ...]
    keywords: tuple[str, ...]
    excludes: tuple[str, ...]
    priority: int
    coexistence_codes: tuple[str, ...]


@dataclass(frozen=True)
class NormalizedChain:
    chain_code: str
    chain_name: str
    parent_code: str
    raw_sector_codes: tuple[str, ...]
    raw_sector_names: tuple[str, ...]
    best_rank: int
    raw_change_pct: Decimal


@dataclass(frozen=True)
class MemberSnapshot:
    code: str
    name: str
    price: Decimal
    change_pct: Decimal
    return5_pct: Decimal
    amount_ratio: Decimal
    ma5: Decimal
    ma10: Decimal
    ma20: Decimal
    ma5_distance_pct: Decimal
    high20: Decimal
    low20: Decimal
    atr14: Decimal
    liquid: bool
    risk_veto: bool
    held: bool
    data_complete: bool


@dataclass(frozen=True)
class ChainMetrics:
    return_percentile: Decimal
    rank_improvement: Decimal
    breadth_ratio: Decimal
    above_ma5_ratio: Decimal
    above_ma20_ratio: Decimal
    strengthening_count: int
    liquid_count: int
    amount_ratio: Decimal
    advancing_amount_ratio: Decimal
    persistence_count: int
    leader_concentration: Decimal
    data_complete: bool


@dataclass(frozen=True)
class ChainScore:
    total: Decimal
    strength_score: Decimal
    breadth_score: Decimal
    amount_score: Decimal
    persistence_score: Decimal
    structure_score: Decimal
    overheat_penalty: Decimal
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ScoredChain:
    chain_code: str
    chain_name: str
    parent_code: str
    raw_sector_codes: tuple[str, ...]
    raw_sector_names: tuple[str, ...]
    best_rank: int
    raw_change_pct: Decimal
    metrics: ChainMetrics
    score: ChainScore
    state: RotationState | None
    previous_state: RotationState | None
    state_reasons: tuple[str, ...]
    coexistence_codes: tuple[str, ...]
    member_codes: tuple[str, ...]


@dataclass(frozen=True)
class SelectedChain(ScoredChain):
    bucket: RotationBucket


@dataclass(frozen=True)
class PriceLevels:
    watch_price: Decimal
    trigger_price: Decimal
    no_chase_price: Decimal
    invalidation_price: Decimal


@dataclass(frozen=True)
class RotationCandidate:
    chain_code: str
    code: str
    name: str
    role: CandidateRole
    pool_rank: int
    formal_eligible: bool
    held: bool
    metrics: Mapping[str, Decimal | int | bool | str]
    levels: PriceLevels | None
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RotationRunResult:
    run_id: str
    observed_at: datetime
    trade_date: date
    edition: str
    policy_version: str
    chains: tuple[NormalizedChain, ...]
    candidates: tuple[RotationCandidate, ...]
    warnings: tuple[str, ...]
    report_path: Path | None
