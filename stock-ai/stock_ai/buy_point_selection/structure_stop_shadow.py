"""Pure, zero-share stop-anchor shadows for buy-point case research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Callable, Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .case_review import CASE_RISK_BUDGET, _diagnostic_price_plan
from .gate_shadow_research import (
    build_gate_shadow_profiles,
    matching_gate_profile,
)
from .gates import anti_chase_gate, base_gate, classify_market, sector_gate
from .historical_replay import second_trading_date_after
from .historical_replay_runtime import _sector_snapshots
from .models import (
    BuyPointBar,
    DetectedSetup,
    MarketSnapshot,
    SectorSnapshot,
    SelectionPolicy,
    SetupType,
)
from .patterns import detect_setups
from .planning import (
    PlanDecision,
    PricePlan,
    RiskBudget,
    _ceil_cent,
    _floor_board_lot,
    _floor_cent,
    _second_weekday_after,
    atr14,
    nearest_resistance_above,
    structure_id,
)
from .reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
    membership_on,
    risk_flags_on,
)


@dataclass(frozen=True)
class StructureStopProfile:
    profile_id: str
    anchor_kind: str
    uses_atr_buffer: bool


@dataclass(frozen=True)
class StructureStopAnchor:
    profile: StructureStopProfile
    code: str
    signal_date: date
    anchor_price: Decimal | None
    invalidation_price: Decimal | None
    reasons: tuple[str, ...]
    executable_shares: int = 0


@dataclass(frozen=True)
class StructureStopBaselineHit:
    code: str
    signal_date: date
    setup: DetectedSetup
    market_status: str
    sector_code: str
    baseline_reasons: tuple[str, ...]
    executable_shares: int = 0


@dataclass(frozen=True)
class StructureStopCandidate:
    hit: StructureStopBaselineHit
    profile: StructureStopProfile
    anchor: StructureStopAnchor
    plan: PricePlan
    average_amount5_qian: Decimal
    two_r_space_buffer: Decimal
    executable_shares: int = 0
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"


@dataclass(frozen=True)
class StructureStopDiagnostic:
    code: str
    signal_date: date
    gate: str
    gate_reason: str
    baseline_reason: str
    label: str = "DIAGNOSTIC_ONLY_COMBINED_FAILURE"
    executable_shares: int = 0


@dataclass(frozen=True)
class StructureStopRejection:
    code: str
    signal_date: date
    profile_id: str | None
    stage: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class StructureStopReplay:
    signal_dates: tuple[date, ...]
    incomplete_dates: tuple[date, ...]
    baseline_hits: tuple[StructureStopBaselineHit, ...]
    candidates: tuple[StructureStopCandidate, ...]
    diagnostics: tuple[StructureStopDiagnostic, ...]
    rejections: tuple[StructureStopRejection, ...]


_PROFILE_SPECS = (
    ("STRUCTURE_STOP:RECENT_SETUP_LOW", "RECENT_SETUP_LOW", True),
    ("STRUCTURE_STOP:DYNAMIC_SUPPORT", "DYNAMIC_SUPPORT", True),
    ("STRUCTURE_STOP:ATR_1_5", "ATR_1_5", False),
)


def build_structure_stop_profiles() -> tuple[StructureStopProfile, ...]:
    return tuple(StructureStopProfile(*value) for value in _PROFILE_SPECS)


def validate_structure_stop_profiles(
    profiles: Sequence[StructureStopProfile],
) -> None:
    if tuple(profiles) != build_structure_stop_profiles():
        raise ValueError("unsupported structure stop profile matrix")


def structure_stop_profile_hash(
    profiles: Sequence[StructureStopProfile],
) -> str:
    validate_structure_stop_profiles(profiles)
    payload = [
        {
            "profile_id": value.profile_id,
            "anchor_kind": value.anchor_kind,
            "uses_atr_buffer": value.uses_atr_buffer,
        }
        for value in profiles
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _bounded_bars(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
) -> tuple[BuyPointBar, ...]:
    bounded = tuple(
        sorted(
            (value for value in bars if value.trade_date <= setup.analysis_date),
            key=lambda value: value.trade_date,
        )
    )
    if (
        not bounded
        or bounded[-1].trade_date != setup.analysis_date
        or len({value.trade_date for value in bounded}) != len(bounded)
    ):
        return ()
    return bounded


def _session_count(setup: DetectedSetup, key: str) -> int | None:
    raw = setup.metrics.get(key)
    if raw is None or not raw.is_finite() or raw != raw.to_integral_value():
        return None
    value = int(raw)
    return value if value > 0 else None


def recent_setup_low(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
) -> Decimal | None:
    bounded = _bounded_bars(setup, bars)
    if not bounded:
        return None
    if setup.setup_type is SetupType.PRE_BREAKOUT:
        sessions = 10
    elif setup.setup_type is SetupType.TREND_PULLBACK:
        sessions = _session_count(setup, "pullback_sessions")
    elif setup.setup_type is SetupType.FIRST_LAUNCH_PULLBACK:
        sessions = _session_count(setup, "quiet_sessions")
    else:
        return None
    if sessions is None or sessions > len(bounded):
        return None
    result = min(value.low for value in bounded[-sessions:])
    if not result.is_finite() or result <= 0:
        return None
    return result


def _moving_average(
    bars: Sequence[BuyPointBar], period: int
) -> Decimal | None:
    if len(bars) < period:
        return None
    values = tuple(value.close for value in bars[-period:])
    if any(not value.is_finite() or value <= 0 for value in values):
        return None
    return sum(values, Decimal("0")) / Decimal(period)


def dynamic_support_anchor(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
) -> Decimal | None:
    bounded = _bounded_bars(setup, bars)
    if not bounded:
        return None
    candidates = (
        _moving_average(bounded, 10),
        _moving_average(bounded, 20),
        recent_setup_low(setup, bounded),
    )
    signal_low = bounded[-1].low
    valid = tuple(
        value
        for value in candidates
        if value is not None
        and value.is_finite()
        and value > 0
        and value <= signal_low
    )
    return max(valid) if valid else None


def build_structure_stop_anchor(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
    profile: StructureStopProfile,
) -> StructureStopAnchor:
    if profile not in build_structure_stop_profiles():
        raise ValueError("unsupported structure stop profile")
    bounded = _bounded_bars(setup, bars)
    if not bounded:
        return StructureStopAnchor(
            profile,
            normalize_code6(setup.code),
            setup.analysis_date,
            None,
            None,
            ("PRICE_HISTORY_MISSING",),
        )
    volatility = atr14(bounded)
    if not volatility.is_finite() or volatility <= 0:
        return StructureStopAnchor(
            profile,
            normalize_code6(setup.code),
            setup.analysis_date,
            None,
            None,
            ("ATR_UNAVAILABLE",),
        )
    trigger = _ceil_cent(setup.structure_high + Decimal("0.01"))
    if profile.anchor_kind == "ATR_1_5":
        invalidation = _floor_cent(trigger - Decimal("1.5") * volatility)
        anchor_price = invalidation
    elif profile.anchor_kind == "RECENT_SETUP_LOW":
        anchor_price = recent_setup_low(setup, bounded)
        if anchor_price is None:
            return StructureStopAnchor(
                profile,
                normalize_code6(setup.code),
                setup.analysis_date,
                None,
                None,
                ("RECENT_SETUP_LOW_UNAVAILABLE",),
            )
        invalidation = _floor_cent(
            anchor_price - Decimal("0.2") * volatility
        )
    else:
        anchor_price = dynamic_support_anchor(setup, bounded)
        if anchor_price is None:
            return StructureStopAnchor(
                profile,
                normalize_code6(setup.code),
                setup.analysis_date,
                None,
                None,
                ("SUPPORT_ANCHOR_UNAVAILABLE",),
            )
        invalidation = _floor_cent(
            anchor_price - Decimal("0.2") * volatility
        )
    if anchor_price > bounded[-1].low:
        return StructureStopAnchor(
            profile,
            normalize_code6(setup.code),
            setup.analysis_date,
            anchor_price,
            invalidation,
            ("ANCHOR_ABOVE_SIGNAL_LOW",),
        )
    return StructureStopAnchor(
        profile,
        normalize_code6(setup.code),
        setup.analysis_date,
        anchor_price,
        invalidation,
        (),
    )


def build_structure_stop_plan(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
    budget: RiskBudget,
    market_status: str,
    profile: StructureStopProfile,
    policy: SelectionPolicy | None = None,
    *,
    valid_through_trade_date: date | None = None,
) -> PlanDecision:
    resolved = policy or SelectionPolicy()
    if market_status == "FREEZE":
        return PlanDecision(None, ("MARKET_FREEZE",))
    if market_status not in {"ALLOW", "LIMITED"}:
        return PlanDecision(None, ("UNKNOWN_MARKET_STATUS",))
    bounded = _bounded_bars(setup, bars)
    if not bounded:
        return PlanDecision(None, ("PRICE_HISTORY_MISSING",))
    volatility = atr14(bounded)
    if not volatility.is_finite() or volatility <= 0:
        return PlanDecision(None, ("ATR_UNAVAILABLE",))
    anchor = build_structure_stop_anchor(setup, bounded, profile)
    if anchor.reasons or anchor.invalidation_price is None:
        return PlanDecision(None, anchor.reasons)
    trigger = _ceil_cent(setup.structure_high + Decimal("0.01"))
    risk = trigger - anchor.invalidation_price
    if risk <= 0:
        return PlanDecision(None, ("RISK_DISTANCE_OUT_OF_RANGE",))
    risk_fraction = risk / trigger
    minimum_risk_fraction = max(
        Decimal("0.015"), Decimal("0.8") * volatility / trigger
    )
    if not minimum_risk_fraction <= risk_fraction <= Decimal("0.05"):
        return PlanDecision(None, ("RISK_DISTANCE_OUT_OF_RANGE",))
    target = _ceil_cent(trigger + Decimal("2") * risk)
    if nearest_resistance_above(trigger, bounded) < target:
        return PlanDecision(None, ("INSUFFICIENT_TWO_R_SPACE",))
    loss_budget = budget.loss_budget
    ticket_limit = budget.ticket_limit
    if market_status == "LIMITED":
        loss_budget /= Decimal("2")
        ticket_limit /= Decimal("2")
    maximum_value = min(
        ticket_limit / trigger,
        loss_budget / risk,
        budget.remaining_exposure / trigger,
    )
    shares = _floor_board_lot(maximum_value)
    if shares < 100:
        return PlanDecision(None, ("POSITION_BELOW_BOARD_LOT",))
    return PlanDecision(
        PricePlan(
            structure_id(setup.code, setup, resolved.rule_version),
            normalize_code6(setup.code),
            setup.setup_type,
            setup.analysis_date,
            bounded[-1].close,
            trigger,
            anchor.invalidation_price,
            target,
            risk,
            Decimal("2"),
            shares,
            (
                valid_through_trade_date
                if valid_through_trade_date is not None
                else _second_weekday_after(setup.analysis_date)
            ),
        ),
        (),
    )


def _signal_bars(
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


def replay_structure_stop_shadows(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
    holding_codes_by_date: Mapping[date, frozenset[str]],
    profiles: Sequence[StructureStopProfile],
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
) -> StructureStopReplay:
    validate_structure_stop_profiles(profiles)
    policy = formal_policy or SelectionPolicy()
    profile_rank = {
        value.profile_id: index for index, value in enumerate(profiles)
    }
    gate_profiles = build_gate_shadow_profiles()
    dated_signal_dates = tuple(sorted(set(signal_dates)))
    baseline_hits: list[StructureStopBaselineHit] = []
    candidates: list[StructureStopCandidate] = []
    diagnostics: list[StructureStopDiagnostic] = []
    rejections: list[StructureStopRejection] = []
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
            or signal_date not in holding_codes_by_date
        ):
            incomplete_dates.append(signal_date)
            continue
        panel = {
            normalize_code6(code): _signal_bars(values, signal_date)
            for code, values in bars_by_code.items()
        }
        dated_memberships = membership_on(memberships, signal_date)
        dated_flags = risk_flags_on(risk_flags, signal_date)
        sectors = sector_snapshot_builder(panel, dated_memberships, policy)
        market = classify_market(market_snapshot)
        holdings = set(holding_codes_by_date[signal_date])
        valid_through = second_trading_date_after(trading_dates, signal_date)
        for code, bars in sorted(panel.items()):
            if not bars or bars[-1].trade_date != signal_date:
                rejections.append(
                    StructureStopRejection(
                        code,
                        signal_date,
                        None,
                        "LATEST_BAR",
                        ("LATEST_BAR_MISSING",),
                    )
                )
                continue
            market_profile = None
            if not market.passed:
                market_profile = matching_gate_profile(
                    "MARKET", market.reasons, gate_profiles
                )
                if market_profile is None:
                    rejections.append(
                        StructureStopRejection(
                            code,
                            signal_date,
                            None,
                            "MARKET",
                            market.reasons,
                        )
                    )
                    continue
            base = base_gate(code, bars, holdings, dated_flags, policy)
            if not base.passed:
                rejections.append(
                    StructureStopRejection(
                        code, signal_date, None, "BASE", base.reasons
                    )
                )
                continue
            setups = tuple(setup_detector(code, bars, policy))
            if not setups:
                rejections.append(
                    StructureStopRejection(
                        code,
                        signal_date,
                        None,
                        "SETUP",
                        ("NO_BUY_POINT_SETUP",),
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
                    StructureStopRejection(
                        code,
                        signal_date,
                        None,
                        "ANTI_CHASE",
                        anti.reasons,
                    )
                )
                continue
            membership = dated_memberships.get(code)
            if membership is None or membership.sector_code not in sectors:
                rejections.append(
                    StructureStopRejection(
                        code,
                        signal_date,
                        None,
                        "SECTOR",
                        ("SECTOR_MISSING",),
                    )
                )
                continue
            sector = sector_gate(sectors[membership.sector_code], policy)
            diagnostic_gate: tuple[str, str] | None = None
            planner_market_status = market.status
            if market_profile is not None:
                if not sector.passed:
                    rejections.append(
                        StructureStopRejection(
                            code,
                            signal_date,
                            None,
                            "SECTOR",
                            sector.reasons,
                        )
                    )
                    continue
                diagnostic_gate = ("MARKET", market_profile.failure_reason)
                planner_market_status = "LIMITED"
            elif not sector.passed:
                sector_profile = matching_gate_profile(
                    "SECTOR", sector.reasons, gate_profiles
                )
                if sector_profile is None:
                    rejections.append(
                        StructureStopRejection(
                            code,
                            signal_date,
                            None,
                            "SECTOR",
                            sector.reasons,
                        )
                    )
                    continue
                diagnostic_gate = ("SECTOR", sector_profile.failure_reason)
            _, baseline_reasons, _ = _diagnostic_price_plan(
                setup,
                bars,
                CASE_RISK_BUDGET,
                planner_market_status,
                policy,
                valid_through,
            )
            if diagnostic_gate is not None:
                if baseline_reasons == ("RISK_DISTANCE_OUT_OF_RANGE",):
                    diagnostics.append(
                        StructureStopDiagnostic(
                            code,
                            signal_date,
                            diagnostic_gate[0],
                            diagnostic_gate[1],
                            baseline_reasons[0],
                        )
                    )
                else:
                    rejections.append(
                        StructureStopRejection(
                            code,
                            signal_date,
                            None,
                            "PRICE_PLAN",
                            baseline_reasons
                            or ("BASELINE_NOT_RISK_ONLY",),
                        )
                    )
                continue
            if baseline_reasons != ("RISK_DISTANCE_OUT_OF_RANGE",):
                rejections.append(
                    StructureStopRejection(
                        code,
                        signal_date,
                        None,
                        "PRICE_PLAN",
                        baseline_reasons or ("BASELINE_NOT_RISK_ONLY",),
                    )
                )
                continue
            hit = StructureStopBaselineHit(
                code,
                signal_date,
                setup,
                market.status,
                membership.sector_code,
                baseline_reasons,
            )
            baseline_hits.append(hit)
            average_amount5 = _average(
                [value.amount_qian for value in bars[-5:]]
            )
            for profile in profiles:
                anchor = build_structure_stop_anchor(setup, bars, profile)
                decision = build_structure_stop_plan(
                    setup,
                    bars,
                    CASE_RISK_BUDGET,
                    market.status,
                    profile,
                    policy,
                    valid_through_trade_date=valid_through,
                )
                if decision.plan is None:
                    rejections.append(
                        StructureStopRejection(
                            code,
                            signal_date,
                            profile.profile_id,
                            "PRICE_PLAN",
                            decision.reasons,
                        )
                    )
                    continue
                resistance = nearest_resistance_above(
                    decision.plan.trigger_price, bars
                )
                candidates.append(
                    StructureStopCandidate(
                        hit,
                        profile,
                        anchor,
                        decision.plan,
                        average_amount5,
                        resistance - decision.plan.target_2r,
                    )
                )
    return StructureStopReplay(
        dated_signal_dates,
        tuple(sorted(set(incomplete_dates))),
        tuple(
            sorted(
                baseline_hits,
                key=lambda value: (value.signal_date, value.code),
            )
        ),
        tuple(
            sorted(
                candidates,
                key=lambda value: (
                    value.hit.signal_date,
                    value.hit.code,
                    profile_rank[value.profile.profile_id],
                ),
            )
        ),
        tuple(
            sorted(
                diagnostics,
                key=lambda value: (
                    value.signal_date,
                    value.code,
                    value.gate,
                    value.gate_reason,
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
