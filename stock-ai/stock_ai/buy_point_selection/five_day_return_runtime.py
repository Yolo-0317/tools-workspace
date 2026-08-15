"""Point-in-time discovery for isolated five-day return shadow plans."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
from typing import Callable, Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .five_day_return_profiles import (
    FIVE_DAY_RULE_VERSION,
    FiveDayReturnProfile,
    build_five_day_return_profiles,
    resolve_profile_stop,
    structure_atr_stop,
    validate_five_day_return_profiles,
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
)
from .patterns import detect_setups
from .planning import _ceil_cent
from .reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
    membership_on,
    risk_flags_on,
)
from .resistance_research import repeated_pivot_resistance


SetupDetector = Callable[
    [str, Sequence[BuyPointBar], SelectionPolicy],
    Sequence[DetectedSetup],
]
SectorSnapshotBuilder = Callable[
    [
        Mapping[str, Sequence[BuyPointBar]],
        Mapping[str, SectorMembership],
        SelectionPolicy,
    ],
    Mapping[str, SectorSnapshot],
]


@dataclass(frozen=True)
class FiveDaySignalCandidate:
    code: str
    signal_date: date
    setup: DetectedSetup
    market_status: str
    sector_code: str
    sector_resonating: bool
    anti_chase_passed: bool
    average_amount5_qian: Decimal
    valid_through_trade_date: date
    executable_shares: int = 0


@dataclass(frozen=True)
class FiveDaySignalPlan:
    candidate: FiveDaySignalCandidate
    profile: FiveDayReturnProfile
    structure_id: str
    signal_close: Decimal
    breakout_trigger: Decimal
    structure_stop: Decimal | None
    reference_entry: Decimal
    resistance_basis: str
    resistance_effective_r: Decimal | None
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"
    executable_shares: int = 0


@dataclass(frozen=True)
class FiveDayDiscovery:
    signal_dates: tuple[date, ...]
    plans: tuple[FiveDaySignalPlan, ...]
    rejection_counts: Mapping[str, int]
    incomplete_dates: tuple[date, ...]


@dataclass(frozen=True)
class FiveDayRejection:
    signal_date: date
    code: str
    profile_id: str | None
    stage: str
    reasons: tuple[str, ...]


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


def _five_day_structure_id(
    code: str,
    setup: DetectedSetup,
    profile: FiveDayReturnProfile,
) -> str:
    payload = ":".join(
        (
            normalize_code6(code),
            setup.setup_type.value,
            setup.structure_start.isoformat(),
            f"{setup.structure_high:.2f}",
            f"{setup.structure_low:.2f}",
            FIVE_DAY_RULE_VERSION,
            profile.profile_id,
        )
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _resistance_features(
    profile: FiveDayReturnProfile,
    reference_entry: Decimal,
    structure_stop: Decimal | None,
    signal_date: date,
    bars: Sequence[BuyPointBar],
) -> tuple[str, Decimal | None]:
    evidence = repeated_pivot_resistance(
        reference_entry,
        signal_date,
        bars,
    )
    if not evidence.complete:
        return "INCOMPLETE", None
    if evidence.level is None:
        return "NO_RELIABLE_LEVEL", None
    if profile.stop_kind == "FIXED_3_PERCENT":
        stop = resolve_profile_stop(profile, reference_entry, None).stop_price
    else:
        stop = structure_stop
    if stop is None or not stop.is_finite() or stop <= 0 or stop >= reference_entry:
        return "INCOMPLETE", None
    effective_r = (evidence.level - reference_entry) / (
        reference_entry - stop
    )
    if effective_r >= Decimal("2"):
        return "LEVEL_AT_OR_ABOVE_2R", effective_r
    return "LEVEL_BELOW_2R", effective_r


def discover_five_day_signal_plans(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
    profiles: Sequence[FiveDayReturnProfile] | None = None,
    formal_policy: SelectionPolicy | None = None,
    setup_detector: SetupDetector = detect_setups,
    sector_snapshot_builder: SectorSnapshotBuilder = _sector_snapshots,
) -> FiveDayDiscovery:
    resolved_profiles = tuple(
        build_five_day_return_profiles() if profiles is None else profiles
    )
    validate_five_day_return_profiles(resolved_profiles)
    policy = formal_policy or SelectionPolicy()
    dated_signal_dates = tuple(sorted(set(signal_dates)))
    profile_rank = {
        value.profile_id: index for index, value in enumerate(resolved_profiles)
    }
    plans: list[FiveDaySignalPlan] = []
    rejections: list[FiveDayRejection] = []
    incomplete_dates: list[date] = []

    for signal_date in dated_signal_dates:
        coverage = coverage_by_date.get(signal_date)
        if coverage is None or not coverage.complete:
            incomplete_dates.append(signal_date)
            rejections.append(
                FiveDayRejection(
                    signal_date,
                    "",
                    None,
                    "COVERAGE",
                    ("POINT_IN_TIME_COVERAGE_INCOMPLETE",),
                )
            )
            continue
        market_snapshot = market_snapshots.get(signal_date)
        market = classify_market(
            market_snapshot
            if market_snapshot is not None
            else MarketSnapshot(0, 0.0, 0.0, False)
        )
        if market.status == "FREEZE":
            if market_snapshot is None or not market_snapshot.complete:
                incomplete_dates.append(signal_date)
            rejections.append(
                FiveDayRejection(
                    signal_date,
                    "",
                    None,
                    "MARKET",
                    ("MARKET_FREEZE",),
                )
            )
            continue

        panel = {
            normalize_code6(code): _signal_bars(values, signal_date)
            for code, values in bars_by_code.items()
        }
        dated_memberships = membership_on(memberships, signal_date)
        dated_flags = risk_flags_on(risk_flags, signal_date)
        sectors = sector_snapshot_builder(panel, dated_memberships, policy)
        valid_through = second_trading_date_after(trading_dates, signal_date)

        for code, bars in sorted(panel.items()):
            if not bars or bars[-1].trade_date != signal_date:
                rejections.append(
                    FiveDayRejection(
                        signal_date,
                        code,
                        None,
                        "LATEST_BAR",
                        ("LATEST_BAR_MISSING",),
                    )
                )
                continue
            base = base_gate(code, bars, set(), dated_flags, policy)
            if not base.passed:
                rejections.append(
                    FiveDayRejection(
                        signal_date,
                        code,
                        None,
                        "BASE",
                        base.reasons,
                    )
                )
                continue
            setups = tuple(setup_detector(code, bars, policy))
            if not setups:
                rejections.append(
                    FiveDayRejection(
                        signal_date,
                        code,
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
            membership = dated_memberships.get(code)
            if membership is None or membership.sector_code not in sectors:
                rejections.append(
                    FiveDayRejection(
                        signal_date,
                        code,
                        None,
                        "SECTOR",
                        ("SECTOR_MISSING",),
                    )
                )
                continue
            sector_resonating = sector_gate(
                sectors[membership.sector_code], policy
            ).passed
            candidate = FiveDaySignalCandidate(
                code=code,
                signal_date=signal_date,
                setup=setup,
                market_status=market.status,
                sector_code=membership.sector_code,
                sector_resonating=sector_resonating,
                anti_chase_passed=anti.passed,
                average_amount5_qian=_average(
                    [value.amount_qian for value in bars[-5:]]
                ),
                valid_through_trade_date=valid_through,
            )
            signal_close = bars[-1].close
            breakout_trigger = _ceil_cent(
                setup.structure_high + Decimal("0.01")
            )
            frozen_structure_stop = structure_atr_stop(setup, bars)
            for profile in resolved_profiles:
                if (
                    profile.stop_kind == "STRUCTURE_ATR"
                    and frozen_structure_stop is None
                ):
                    rejections.append(
                        FiveDayRejection(
                            signal_date,
                            code,
                            profile.profile_id,
                            "STOP",
                            ("STRUCTURE_STOP_UNAVAILABLE",),
                        )
                    )
                    continue
                reference_entry = (
                    breakout_trigger
                    if profile.entry_kind == "BREAKOUT_TRIGGER"
                    else signal_close
                )
                resistance_basis, effective_r = _resistance_features(
                    profile,
                    reference_entry,
                    frozen_structure_stop,
                    signal_date,
                    bars,
                )
                plans.append(
                    FiveDaySignalPlan(
                        candidate=candidate,
                        profile=profile,
                        structure_id=_five_day_structure_id(
                            code, setup, profile
                        ),
                        signal_close=signal_close,
                        breakout_trigger=breakout_trigger,
                        structure_stop=frozen_structure_stop,
                        reference_entry=reference_entry,
                        resistance_basis=resistance_basis,
                        resistance_effective_r=effective_r,
                    )
                )

    rejection_counts = Counter(
        reason for value in rejections for reason in value.reasons
    )
    return FiveDayDiscovery(
        signal_dates=dated_signal_dates,
        plans=tuple(
            sorted(
                plans,
                key=lambda value: (
                    value.candidate.signal_date,
                    value.candidate.code,
                    profile_rank[value.profile.profile_id],
                ),
            )
        ),
        rejection_counts=dict(sorted(rejection_counts.items())),
        incomplete_dates=tuple(sorted(set(incomplete_dates))),
    )


def entry_blockers_by_date(
    code: str,
    entry_dates: Sequence[date],
    *,
    coverage_by_date: Mapping[date, ReferenceCoverage],
    risk_flags: Sequence[RiskFlag],
    market_snapshots: Mapping[date, MarketSnapshot],
) -> dict[date, tuple[str, ...]]:
    normalized = normalize_code6(code)
    result: dict[date, tuple[str, ...]] = {}
    for entry_date in sorted(set(entry_dates)):
        reasons: set[str] = set()
        coverage = coverage_by_date.get(entry_date)
        if coverage is None or not coverage.complete:
            reasons.add("POINT_IN_TIME_COVERAGE_INCOMPLETE")
        dated_flags = risk_flags_on(risk_flags, entry_date)
        if any(
            value.severity == "VETO"
            for value in dated_flags.get(normalized, ())
        ):
            reasons.add("POINT_IN_TIME_RISK_VETO")
        snapshot = market_snapshots.get(
            entry_date,
            MarketSnapshot(0, 0.0, 0.0, False),
        )
        if classify_market(snapshot).status == "FREEZE":
            reasons.add("MARKET_FREEZE")
        result[entry_date] = tuple(sorted(reasons))
    return result
