"""Pure, zero-share research for single-boundary setup relaxations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Callable, Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .case_review import CASE_RISK_BUDGET
from .gates import anti_chase_gate, base_gate, classify_market, sector_gate
from .historical_replay import second_trading_date_after
from .models import (
    BuyPointBar,
    DetectedSetup,
    MarketSnapshot,
    SelectionPolicy,
    SetupType,
)
from .patterns import (
    detect_first_launch_pullback,
    detect_pre_breakout,
    detect_trend_pullback,
)
from .recall_research import diagnose_setup_windows
from .planning import PricePlan, build_price_plan, nearest_resistance_above
from .reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
    membership_on,
    risk_flags_on,
)


@dataclass(frozen=True)
class ThresholdProfile:
    profile_id: str
    setup_type: SetupType
    policy_field: str
    direction: str
    relaxation_rate: Decimal
    formal_value: Decimal
    shadow_value: Decimal
    failure_reason: str
    metric_name: str


@dataclass(frozen=True)
class ThresholdShadowSetup:
    code: str
    signal_date: date
    profile: ThresholdProfile
    setup: DetectedSetup
    actual_deviation: Decimal
    executable_shares: int = 0


@dataclass(frozen=True)
class ThresholdShadowCandidate:
    code: str
    signal_date: date
    profile_id: str
    shadow_setup: ThresholdShadowSetup
    plan: PricePlan
    average_amount5_qian: Decimal
    two_r_space_buffer: Decimal
    executable_shares: int = 0
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"


@dataclass(frozen=True)
class ThresholdShadowRejection:
    code: str
    signal_date: date
    profile_id: str | None
    stage: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ThresholdShadowReplay:
    signal_dates: tuple[date, ...]
    incomplete_dates: tuple[date, ...]
    raw_setups: tuple[ThresholdShadowSetup, ...]
    candidates: tuple[ThresholdShadowCandidate, ...]
    rejections: tuple[ThresholdShadowRejection, ...]


_FIELD_SPECS = (
    (SetupType.PRE_BREAKOUT, "platform_width_max", "UPPER", "PLATFORM_WIDTH_WIDE", "platform_width"),
    (SetupType.PRE_BREAKOUT, "platform_near_top_max", "UPPER", "PLATFORM_NOT_NEAR_TOP", "distance_to_platform_top"),
    (SetupType.PRE_BREAKOUT, "platform_contraction_max", "UPPER", "PLATFORM_RANGE_NOT_CONTRACTED", "range_contraction_ratio"),
    (SetupType.PRE_BREAKOUT, "platform_amount_ratio_max", "UPPER", "PLATFORM_AMOUNT_NOT_CONTRACTED", "amount_contraction_ratio"),
    (SetupType.TREND_PULLBACK, "trend_return10_min", "LOWER", "TREND_RETURN_OUT_OF_RANGE", "trend_return10"),
    (SetupType.TREND_PULLBACK, "trend_return10_max", "UPPER", "TREND_RETURN_OUT_OF_RANGE", "trend_return10"),
    (SetupType.TREND_PULLBACK, "trend_drawdown_min", "LOWER", "TREND_DRAWDOWN_OUT_OF_RANGE", "pullback_drawdown"),
    (SetupType.TREND_PULLBACK, "trend_drawdown_max", "UPPER", "TREND_DRAWDOWN_OUT_OF_RANGE", "pullback_drawdown"),
    (SetupType.TREND_PULLBACK, "pullback_amount_ratio_max", "UPPER", "TREND_AMOUNT_NOT_CONTRACTED", "pullback_amount_ratio"),
    (SetupType.FIRST_LAUNCH_PULLBACK, "launch_gain_min", "LOWER", "LAUNCH_GAIN_OUT_OF_RANGE", "launch_gain_pct"),
    (SetupType.FIRST_LAUNCH_PULLBACK, "launch_gain_max", "UPPER", "LAUNCH_GAIN_OUT_OF_RANGE", "launch_gain_pct"),
    (SetupType.FIRST_LAUNCH_PULLBACK, "launch_amount_ratio_min", "LOWER", "LAUNCH_AMOUNT_OUT_OF_RANGE", "launch_amount_ratio"),
    (SetupType.FIRST_LAUNCH_PULLBACK, "launch_amount_ratio_max", "UPPER", "LAUNCH_AMOUNT_OUT_OF_RANGE", "launch_amount_ratio"),
    (SetupType.FIRST_LAUNCH_PULLBACK, "launch_close_location_min", "LOWER", "LAUNCH_CLOSE_LOCATION_LOW", "launch_close_location"),
    (SetupType.FIRST_LAUNCH_PULLBACK, "consolidation_gain_abs_max", "UPPER", "LAUNCH_QUIET_PRICE_LOUD", "quiet_max_abs_gain"),
    (SetupType.FIRST_LAUNCH_PULLBACK, "consolidation_amount_ratio_max", "UPPER", "LAUNCH_QUIET_AMOUNT_LOUD", "quiet_amount_ratio"),
)

_RELAXATION_RATES = (Decimal("0.10"), Decimal("0.25"), Decimal("0.50"))


def build_threshold_profiles(
    policy: SelectionPolicy | None = None,
) -> tuple[ThresholdProfile, ...]:
    resolved = policy or SelectionPolicy()
    profiles = []
    for setup_type, field, direction, failure, metric in _FIELD_SPECS:
        formal_value = Decimal(str(getattr(resolved, field)))
        for rate in _RELAXATION_RATES:
            factor = Decimal("1") + rate if direction == "UPPER" else Decimal("1") - rate
            profiles.append(
                ThresholdProfile(
                    f"{setup_type.value}:{field}:{direction}:{rate}",
                    setup_type,
                    field,
                    direction,
                    rate,
                    formal_value,
                    formal_value * factor,
                    failure,
                    metric,
                )
            )
    return tuple(profiles)


def profile_matrix_hash(profiles: tuple[ThresholdProfile, ...]) -> str:
    payload = [
        {
            "profile_id": value.profile_id,
            "setup_type": value.setup_type.value,
            "policy_field": value.policy_field,
            "direction": value.direction,
            "relaxation_rate": str(value.relaxation_rate),
            "formal_value": str(value.formal_value),
            "shadow_value": str(value.shadow_value),
            "failure_reason": value.failure_reason,
            "metric_name": value.metric_name,
        }
        for value in sorted(profiles, key=lambda item: item.profile_id)
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


_DETECTORS: dict[
    SetupType,
    Callable[[str, Sequence[BuyPointBar], SelectionPolicy], DetectedSetup | None],
] = {
    SetupType.PRE_BREAKOUT: detect_pre_breakout,
    SetupType.TREND_PULLBACK: detect_trend_pullback,
    SetupType.FIRST_LAUNCH_PULLBACK: detect_first_launch_pullback,
}


def _diagnostic_window(setup: DetectedSetup) -> int:
    if setup.setup_type == SetupType.PRE_BREAKOUT:
        return 30
    metric = (
        "pullback_sessions"
        if setup.setup_type == SetupType.TREND_PULLBACK
        else "quiet_sessions"
    )
    return int(setup.metrics[metric])


def _actual_deviation(profile: ThresholdProfile, actual: Decimal) -> Decimal:
    if profile.direction == "UPPER":
        return (actual - profile.formal_value) / profile.formal_value
    return (profile.formal_value - actual) / profile.formal_value


def generate_threshold_shadow_setups(
    code: str,
    signal_date: date,
    bars: Sequence[BuyPointBar],
    profiles: Sequence[ThresholdProfile],
    formal_policy: SelectionPolicy | None = None,
) -> tuple[ThresholdShadowSetup, ...]:
    policy = formal_policy or SelectionPolicy()
    allowed = {
        value.profile_id: value for value in build_threshold_profiles(policy)
    }
    if any(allowed.get(value.profile_id) != value for value in profiles):
        raise ValueError("unsupported threshold profile")
    bounded = tuple(
        sorted(
            (value for value in bars if value.trade_date <= signal_date),
            key=lambda value: value.trade_date,
        )[-120:]
    )
    diagnostics = diagnose_setup_windows(code, signal_date, bounded, policy)
    rows = []
    for profile in sorted(profiles, key=lambda value: value.profile_id):
        detector = _DETECTORS[profile.setup_type]
        if detector(code, bounded, policy) is not None:
            continue
        relaxed = replace(policy, **{profile.policy_field: profile.shadow_value})
        setup = detector(code, bounded, relaxed)
        if setup is None:
            continue
        diagnostic = next(
            (
                value
                for value in diagnostics
                if value.template == setup.setup_type.value
                and value.window_sessions == _diagnostic_window(setup)
            ),
            None,
        )
        if diagnostic is None or diagnostic.failures != (profile.failure_reason,):
            continue
        actual = diagnostic.metrics.get(profile.metric_name)
        if actual is None or not actual.is_finite():
            continue
        deviation = _actual_deviation(profile, actual)
        if not deviation.is_finite() or not Decimal("0") < deviation <= profile.relaxation_rate:
            continue
        rows.append(
            ThresholdShadowSetup(
                normalize_code6(code),
                signal_date,
                profile,
                setup,
                deviation,
            )
        )
    return tuple(rows)


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


def replay_threshold_shadows(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
    holding_codes_by_date: Mapping[date, frozenset[str]],
    profiles: Sequence[ThresholdProfile],
    formal_policy: SelectionPolicy | None = None,
    setup_generator: Callable[
        [
            str,
            date,
            Sequence[BuyPointBar],
            Sequence[ThresholdProfile],
            SelectionPolicy,
        ],
        tuple[ThresholdShadowSetup, ...],
    ] = generate_threshold_shadow_setups,
) -> ThresholdShadowReplay:
    policy = formal_policy or SelectionPolicy()
    dated_signal_dates = tuple(sorted(set(signal_dates)))
    raw_setups = []
    candidates = []
    rejections = []
    incomplete_dates = []
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
        dated_flags = risk_flags_on(risk_flags, signal_date)
        dated_memberships = membership_on(memberships, signal_date)
        from .historical_replay_runtime import _sector_snapshots

        sectors = _sector_snapshots(panel, dated_memberships, policy)
        market = classify_market(market_snapshot)
        for code, bars in sorted(panel.items()):
            if not bars or bars[-1].trade_date != signal_date:
                rejections.append(
                    ThresholdShadowRejection(
                        code, signal_date, None, "LATEST_BAR", ("LATEST_BAR_MISSING",)
                    )
                )
                continue
            base = base_gate(
                code,
                bars,
                set(holding_codes_by_date.get(signal_date, frozenset())),
                dated_flags,
                policy,
            )
            if not base.passed:
                rejections.append(
                    ThresholdShadowRejection(
                        code, signal_date, None, "BASE", base.reasons
                    )
                )
                continue
            setups = setup_generator(code, signal_date, bars, profiles, policy)
            if any(value.executable_shares != 0 for value in setups):
                raise ValueError("shadow setup must be zero-share")
            raw_setups.extend(setups)
            for shadow in setups:
                if not market.passed:
                    rejections.append(
                        ThresholdShadowRejection(
                            code,
                            signal_date,
                            shadow.profile.profile_id,
                            "MARKET",
                            market.reasons,
                        )
                    )
                    continue
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
                        ThresholdShadowRejection(
                            code,
                            signal_date,
                            shadow.profile.profile_id,
                            "ANTI_CHASE",
                            anti.reasons,
                        )
                    )
                    continue
                membership = dated_memberships.get(code)
                if membership is None or membership.sector_code not in sectors:
                    rejections.append(
                        ThresholdShadowRejection(
                            code,
                            signal_date,
                            shadow.profile.profile_id,
                            "SECTOR",
                            ("SECTOR_MISSING",),
                        )
                    )
                    continue
                sector = sector_gate(sectors[membership.sector_code], policy)
                if not sector.passed:
                    rejections.append(
                        ThresholdShadowRejection(
                            code,
                            signal_date,
                            shadow.profile.profile_id,
                            "SECTOR",
                            sector.reasons,
                        )
                    )
                    continue
                decision = build_price_plan(
                    shadow.setup,
                    bars,
                    CASE_RISK_BUDGET,
                    market.status,
                    policy,
                    valid_through_trade_date=second_trading_date_after(
                        trading_dates, signal_date
                    ),
                )
                if decision.plan is None:
                    rejections.append(
                        ThresholdShadowRejection(
                            code,
                            signal_date,
                            shadow.profile.profile_id,
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
                    ThresholdShadowCandidate(
                        code,
                        signal_date,
                        shadow.profile.profile_id,
                        shadow,
                        decision.plan,
                        average_amount5,
                        resistance - decision.plan.target_2r,
                    )
                )
    return ThresholdShadowReplay(
        dated_signal_dates,
        tuple(sorted(set(incomplete_dates))),
        tuple(
            sorted(
                raw_setups,
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
                    value.signal_date,
                    value.code,
                    value.profile_id,
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
