"""Pure, zero-share research for single-boundary setup relaxations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Callable, Sequence

from stock_ai.market_codes import normalize_code6

from .models import BuyPointBar, DetectedSetup, SelectionPolicy, SetupType
from .patterns import (
    detect_first_launch_pullback,
    detect_pre_breakout,
    detect_trend_pullback,
)
from .recall_research import diagnose_setup_windows


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
