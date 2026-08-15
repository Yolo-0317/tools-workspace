"""Pure, zero-share research for isolated market and sector gate failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Sequence

from .models import DetectedSetup
from .planning import PricePlan


@dataclass(frozen=True)
class GateShadowProfile:
    profile_id: str
    gate: str
    failure_reason: str
    mode: str
    freeze_eligible: bool


@dataclass(frozen=True)
class GateShadowHit:
    code: str
    signal_date: date
    profile: GateShadowProfile
    setup: DetectedSetup
    market_status: str
    sector_code: str
    executable_shares: int = 0


@dataclass(frozen=True)
class GateShadowCandidate:
    hit: GateShadowHit
    plan: PricePlan
    average_amount5_qian: Decimal
    two_r_space_buffer: Decimal
    executable_shares: int = 0
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"


@dataclass(frozen=True)
class GateShadowRejection:
    code: str
    signal_date: date
    profile_id: str | None
    stage: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class GateShadowReplay:
    signal_dates: tuple[date, ...]
    incomplete_dates: tuple[date, ...]
    raw_hits: tuple[GateShadowHit, ...]
    candidates: tuple[GateShadowCandidate, ...]
    rejections: tuple[GateShadowRejection, ...]


_PROFILE_SPECS = (
    ("MARKET", "AMOUNT_AND_BREADTH_WEAK", "DIAGNOSTIC", False),
    ("MARKET", "INDEX_AND_BREADTH_WEAK", "DIAGNOSTIC", False),
    ("SECTOR", "SECTOR_AMOUNT_WEAK", "BYPASS", True),
    ("SECTOR", "SECTOR_BREADTH_WEAK", "BYPASS", True),
    ("SECTOR", "SECTOR_NOT_RESONATING", "BYPASS", True),
    ("SECTOR", "SECTOR_RELATIVE_STRENGTH_WEAK", "BYPASS", True),
)


def build_gate_shadow_profiles() -> tuple[GateShadowProfile, ...]:
    return tuple(
        GateShadowProfile(
            f"{gate}:{reason}:{mode}", gate, reason, mode, freeze_eligible
        )
        for gate, reason, mode, freeze_eligible in _PROFILE_SPECS
    )


def validate_gate_shadow_profiles(
    profiles: Sequence[GateShadowProfile],
) -> None:
    if tuple(profiles) != build_gate_shadow_profiles():
        raise ValueError("unsupported gate profile matrix")


def gate_profile_matrix_hash(
    profiles: Sequence[GateShadowProfile],
) -> str:
    validate_gate_shadow_profiles(profiles)
    payload = [
        {
            "profile_id": value.profile_id,
            "gate": value.gate,
            "failure_reason": value.failure_reason,
            "mode": value.mode,
            "freeze_eligible": value.freeze_eligible,
        }
        for value in profiles
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def matching_gate_profile(
    gate: str,
    reasons: Sequence[str],
    profiles: Sequence[GateShadowProfile],
) -> GateShadowProfile | None:
    validate_gate_shadow_profiles(profiles)
    if len(reasons) != 1:
        return None
    return next(
        (
            value
            for value in profiles
            if value.gate == gate and value.failure_reason == reasons[0]
        ),
        None,
    )
