"""Buy-point-first selection domain."""

from .gates import anti_chase_gate, base_gate, classify_market, sector_gate
from .models import (
    BuyPointBar,
    CandidateTier,
    GateDecision,
    MarketSnapshot,
    PlanState,
    SectorSnapshot,
    SelectionPolicy,
    SetupType,
)

from .reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
    classify_announcement_title,
    membership_on,
    normalize_announcement_flags,
    normalize_sector_memberships,
    normalize_st_flags,
    risk_flags_on,
    sync_reference_data,
)

__all__ = [
    "BuyPointBar",
    "CandidateTier",
    "GateDecision",
    "MarketSnapshot",
    "PlanState",
    "ReferenceCoverage",
    "RiskFlag",
    "SectorMembership",
    "SectorSnapshot",
    "SelectionPolicy",
    "SetupType",
    "anti_chase_gate",
    "base_gate",
    "classify_announcement_title",
    "classify_market",
    "membership_on",
    "normalize_announcement_flags",
    "normalize_sector_memberships",
    "normalize_st_flags",
    "risk_flags_on",
    "sector_gate",
    "sync_reference_data",
]
