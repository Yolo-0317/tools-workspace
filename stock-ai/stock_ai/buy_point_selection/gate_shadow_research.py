"""Pure, zero-share research for isolated market and sector gate failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Callable, Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .case_review import CASE_RISK_BUDGET
from .gates import anti_chase_gate, base_gate, classify_market, sector_gate
from .historical_replay import second_trading_date_after
from .historical_replay_runtime import _sector_snapshots
from .models import (
    BuyPointBar,
    DetectedSetup,
    MarketSnapshot,
    SectorSnapshot,
    SelectionPolicy,
)
from .patterns import detect_setups
from .planning import PricePlan, build_price_plan, nearest_resistance_above
from .reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
    membership_on,
    risk_flags_on,
)


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


def _bars_on_or_before(
    bars: Sequence[BuyPointBar], signal_date: date
) -> tuple[BuyPointBar, ...]:
    return tuple(
        sorted(
            (value for value in bars if value.trade_date <= signal_date),
            key=lambda value: value.trade_date,
        )[-120:]
    )


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _cumulative_return_pct(
    bars: Sequence[BuyPointBar], sessions: int
) -> Decimal:
    return (
        bars[-1].close / bars[-sessions - 1].close - Decimal("1")
    ) * Decimal("100")


def replay_gate_shadows(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
    holding_codes_by_date: Mapping[date, frozenset[str]],
    profiles: Sequence[GateShadowProfile],
    formal_policy: SelectionPolicy | None = None,
    setup_detector: Callable[
        [str, Sequence[BuyPointBar], SelectionPolicy],
        Sequence[DetectedSetup],
    ] = detect_setups,
    sector_snapshot_builder: Callable[
        [
            Mapping[str, Sequence[BuyPointBar]],
            Mapping[str, SectorMembership],
            SelectionPolicy,
        ],
        Mapping[str, SectorSnapshot],
    ] = _sector_snapshots,
) -> GateShadowReplay:
    validate_gate_shadow_profiles(profiles)
    policy = formal_policy or SelectionPolicy()
    dated_signal_dates = tuple(sorted(set(signal_dates)))
    raw_hits: list[GateShadowHit] = []
    candidates: list[GateShadowCandidate] = []
    rejections: list[GateShadowRejection] = []
    incomplete_dates: list[date] = []
    for signal_date in dated_signal_dates:
        coverage = coverage_by_date.get(signal_date)
        market_snapshot = market_snapshots.get(signal_date)
        if (
            coverage is None
            or not coverage.sector_complete
            or not coverage.st_complete
            or market_snapshot is None
            or not market_snapshot.complete
        ):
            incomplete_dates.append(signal_date)
            continue
        panel = {
            normalize_code6(code): _bars_on_or_before(values, signal_date)
            for code, values in bars_by_code.items()
        }
        dated_memberships = membership_on(memberships, signal_date)
        dated_flags = risk_flags_on(risk_flags, signal_date)
        sectors = sector_snapshot_builder(panel, dated_memberships, policy)
        market = classify_market(market_snapshot)
        holdings = set(holding_codes_by_date.get(signal_date, frozenset()))
        for code, bars in sorted(panel.items()):
            if not bars or bars[-1].trade_date != signal_date:
                rejections.append(
                    GateShadowRejection(
                        code, signal_date, None, "LATEST_BAR", ("LATEST_BAR_MISSING",)
                    )
                )
                continue
            base = base_gate(code, bars, holdings, dated_flags, policy)
            if not base.passed:
                rejections.append(
                    GateShadowRejection(code, signal_date, None, "BASE", base.reasons)
                )
                continue
            setups = tuple(setup_detector(code, bars, policy))
            if not setups:
                rejections.append(
                    GateShadowRejection(
                        code, signal_date, None, "SETUP", ("NO_BUY_POINT_SETUP",)
                    )
                )
                continue
            setup = max(
                setups,
                key=lambda value: (value.quality, value.setup_type.value),
            )
            ma5 = _average([value.close for value in bars[-5:]])
            ma20 = _average([value.close for value in bars[-20:]])
            anti = anti_chase_gate(
                bars[-1].pct_chg,
                _cumulative_return_pct(bars, 3),
                _cumulative_return_pct(bars, 5),
                (bars[-1].close / ma5 - Decimal("1")) * Decimal("100"),
                (bars[-1].close / ma20 - Decimal("1")) * Decimal("100"),
                policy,
            )
            if not anti.passed:
                rejections.append(
                    GateShadowRejection(
                        code, signal_date, None, "ANTI_CHASE", anti.reasons
                    )
                )
                continue
            membership = dated_memberships.get(code)
            if membership is None or membership.sector_code not in sectors:
                rejections.append(
                    GateShadowRejection(
                        code, signal_date, None, "SECTOR", ("SECTOR_MISSING",)
                    )
                )
                continue
            sector = sector_gate(sectors[membership.sector_code], policy)
            profile: GateShadowProfile | None
            planner_market_status: str
            if not market.passed:
                profile = matching_gate_profile("MARKET", market.reasons, profiles)
                if profile is None:
                    rejections.append(
                        GateShadowRejection(
                            code, signal_date, None, "MARKET", market.reasons
                        )
                    )
                    continue
                if not sector.passed:
                    rejections.append(
                        GateShadowRejection(
                            code,
                            signal_date,
                            profile.profile_id,
                            "SECTOR",
                            sector.reasons,
                        )
                    )
                    continue
                planner_market_status = "LIMITED"
            else:
                if sector.passed:
                    rejections.append(
                        GateShadowRejection(
                            code,
                            signal_date,
                            None,
                            "PROFILE",
                            ("NO_SUPPORTED_GATE_FAILURE",),
                        )
                    )
                    continue
                profile = matching_gate_profile("SECTOR", sector.reasons, profiles)
                if profile is None:
                    rejections.append(
                        GateShadowRejection(
                            code, signal_date, None, "SECTOR", sector.reasons
                        )
                    )
                    continue
                planner_market_status = market.status
            hit = GateShadowHit(
                code,
                signal_date,
                profile,
                setup,
                market.status,
                membership.sector_code,
            )
            raw_hits.append(hit)
            decision = build_price_plan(
                setup,
                bars,
                CASE_RISK_BUDGET,
                planner_market_status,
                policy,
                valid_through_trade_date=second_trading_date_after(
                    trading_dates, signal_date
                ),
            )
            if decision.plan is None:
                rejections.append(
                    GateShadowRejection(
                        code,
                        signal_date,
                        profile.profile_id,
                        "PRICE_PLAN",
                        decision.reasons,
                    )
                )
                continue
            average_amount5 = _average(
                [value.amount_qian for value in bars[-5:]]
            )
            resistance = nearest_resistance_above(
                decision.plan.trigger_price, bars
            )
            candidates.append(
                GateShadowCandidate(
                    hit,
                    decision.plan,
                    average_amount5,
                    resistance - decision.plan.target_2r,
                )
            )
    return GateShadowReplay(
        dated_signal_dates,
        tuple(sorted(set(incomplete_dates))),
        tuple(
            sorted(
                raw_hits,
                key=lambda value: (
                    value.signal_date,
                    value.code,
                    value.profile.profile_id,
                ),
            )
        ),
        tuple(
            sorted(
                candidates,
                key=lambda value: (
                    value.hit.signal_date,
                    value.hit.code,
                    value.hit.profile.profile_id,
                ),
            )
        ),
        tuple(
            sorted(
                rejections,
                key=lambda value: (
                    value.signal_date,
                    value.code,
                    value.profile_id or "",
                    value.stage,
                    value.reasons,
                ),
            )
        ),
    )
