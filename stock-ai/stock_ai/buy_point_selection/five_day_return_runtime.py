"""Point-in-time discovery for isolated five-day return shadow plans."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
import os
from typing import TYPE_CHECKING, Callable, Mapping, Sequence

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

if TYPE_CHECKING:
    from .five_day_return_validation import (
        FiveDayCalibration,
        FiveDayFreeze,
        FiveDayObservation,
        FiveDayPortfolioMetrics,
        FiveDaySegmentMetrics,
        FiveDayTestAssessment,
    )
    from .validation import ChronologicalSplit


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


@dataclass(frozen=True)
class FiveDayRuntimeInputs:
    signal_dates: tuple[date, ...]
    trading_dates: tuple[date, ...]
    bars_by_code: Mapping[str, tuple[BuyPointBar, ...]]
    memberships: tuple[SectorMembership, ...]
    risk_flags: tuple[RiskFlag, ...]
    coverage_by_date: Mapping[date, ReferenceCoverage]
    market_snapshots: Mapping[date, MarketSnapshot]
    input_fingerprint: str


@dataclass(frozen=True)
class FiveDayResearchReview:
    split: ChronologicalSplit
    input_fingerprint: str
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    sizing_version: str
    evaluator_version: str
    cost_version: str
    observations: tuple[FiveDayObservation, ...]
    train_calibrations: Mapping[str, FiveDayCalibration]
    validation_metrics: tuple[FiveDaySegmentMetrics, ...]
    validation_portfolio: FiveDayPortfolioMetrics
    point_in_time_complete: bool
    test_outcomes_read: bool = False


@dataclass(frozen=True)
class FiveDayTestReview:
    signal_dates: tuple[date, ...]
    research_identity: str
    freeze_hash: str
    input_fingerprint: str
    observations: tuple[FiveDayObservation, ...]
    assessment: FiveDayTestAssessment
    sizing_version: str
    evaluator_version: str
    cost_version: str


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


FiveDayInputLoader = Callable[
    [Sequence[date], date, date, date], FiveDayRuntimeInputs
]
FiveDayDiscoveryBuilder = Callable[..., FiveDayDiscovery]
FiveDayPlanSimulator = Callable[..., object]


def build_five_day_research_review(
    signal_dates: Sequence[date],
    *,
    input_loader: FiveDayInputLoader | None = None,
    formal_policy: SelectionPolicy | None = None,
    discovery_builder: FiveDayDiscoveryBuilder = discover_five_day_signal_plans,
    plan_simulator: FiveDayPlanSimulator | None = None,
) -> FiveDayResearchReview:
    """Build train/validation-only research without consuming test outcomes."""
    from .five_day_return_execution import (
        COST_VERSION,
        EVALUATOR_VERSION,
        FiveDayTrade,
        simulate_five_day_plan,
    )
    from .five_day_return_profiles import (
        SIZING_VERSION,
        build_five_day_return_profiles,
        five_day_profile_hash,
    )
    from .five_day_return_validation import (
        FiveDayObservation,
        _resolved_count,
        _segment_metrics_from_observations,
        build_five_day_calibrations,
        build_five_day_portfolio_metrics,
    )
    from .validation import chronological_split, policy_hash

    split = chronological_split(tuple(signal_dates))
    outcome_cutoff = split.test[9]
    loader = input_loader or load_mysql_five_day_inputs
    inputs = loader(
        tuple(signal_dates),
        split.train[0] - timedelta(days=180),
        split.validation[-1],
        outcome_cutoff,
    )
    if tuple(inputs.signal_dates) != tuple(signal_dates):
        raise ValueError("runtime signal dates do not match requested calendar")
    policy = formal_policy or SelectionPolicy()
    profiles = build_five_day_return_profiles()
    research_dates = (*split.train, *split.validation)
    research_date_set = frozenset(research_dates)
    discovery = discovery_builder(
        signal_dates=research_dates,
        trading_dates=inputs.trading_dates,
        bars_by_code=inputs.bars_by_code,
        memberships=inputs.memberships,
        risk_flags=inputs.risk_flags,
        coverage_by_date=inputs.coverage_by_date,
        market_snapshots=inputs.market_snapshots,
        profiles=profiles,
        formal_policy=policy,
    )
    simulate = plan_simulator or simulate_five_day_plan
    observations: list[FiveDayObservation] = []
    for plan in discovery.plans:
        if plan.candidate.signal_date not in research_date_set:
            raise ValueError("discovery returned a test or out-of-window plan")
        entry_dates = tuple(
            value
            for value in inputs.trading_dates
            if plan.candidate.signal_date < value
            <= plan.candidate.valid_through_trade_date
        )
        blockers = entry_blockers_by_date(
            plan.candidate.code,
            entry_dates,
            coverage_by_date=inputs.coverage_by_date,
            risk_flags=inputs.risk_flags,
            market_snapshots=inputs.market_snapshots,
        )
        trade = simulate(
            plan,
            inputs.bars_by_code.get(normalize_code6(plan.candidate.code), ()),
            inputs.trading_dates,
            entry_blockers=blockers,
        )
        if not isinstance(trade, FiveDayTrade):
            raise TypeError("plan simulator must return FiveDayTrade")
        resolution_date = (
            trade.exit.actual_exit_date
            if trade.exit is not None
            else (
                plan.candidate.valid_through_trade_date
                if trade.status in {"NOT_TRIGGERED", "CANCELLED"}
                else outcome_cutoff
            )
        )
        observations.append(FiveDayObservation(plan, trade, resolution_date))
    ordered_observations = tuple(
        sorted(
            observations,
            key=lambda value: (
                value.plan.candidate.signal_date,
                normalize_code6(value.plan.candidate.code),
                value.plan.profile.profile_id,
            ),
        )
    )
    train_set = frozenset(split.train)
    validation_set = frozenset(split.validation)
    train_values = tuple(
        value
        for value in ordered_observations
        if value.plan.candidate.signal_date in train_set
    )
    validation_values = tuple(
        value
        for value in ordered_observations
        if value.plan.candidate.signal_date in validation_set
    )
    train_calibrations = build_five_day_calibrations(
        train_values,
        trading_dates=split.train,
    )
    validation_metrics = tuple(
        _segment_metrics_from_observations(
            profile_id=profile.profile_id,
            segment="validation",
            observations=validation_values,
            trading_dates=split.validation,
            ranking_calibrations=train_calibrations,
            cumulative_samples=_resolved_count(
                ordered_observations,
                profile.profile_id,
                data_end=split.validation[-1],
            ),
            required_cumulative_samples=70,
        )
        for profile in profiles
    )
    qualified_ids = frozenset(
        value.profile_id for value in validation_metrics if value.qualifies
    )
    combined_values = tuple(
        value
        for value in validation_values
        if value.plan.profile.profile_id in qualified_ids
        and value.resolution_date <= split.validation[-1]
    )
    validation_portfolio = build_five_day_portfolio_metrics(
        tuple(value.plan for value in combined_values),
        combined_values,
        train_calibrations,
    )
    return FiveDayResearchReview(
        split=split,
        input_fingerprint=inputs.input_fingerprint,
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=five_day_profile_hash(profiles),
        sizing_version=SIZING_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        cost_version=COST_VERSION,
        observations=ordered_observations,
        train_calibrations=train_calibrations,
        validation_metrics=validation_metrics,
        validation_portfolio=validation_portfolio,
        point_in_time_complete=(
            not discovery.incomplete_dates
            and all(value.trade.status != "PENDING" for value in ordered_observations)
        ),
        test_outcomes_read=False,
    )


def build_five_day_test_review(
    freeze: FiveDayFreeze | None,
    research: FiveDayResearchReview,
    inputs: FiveDayRuntimeInputs,
    *,
    discovery_builder: FiveDayDiscoveryBuilder = discover_five_day_signal_plans,
    plan_simulator: FiveDayPlanSimulator | None = None,
) -> FiveDayTestReview:
    """Evaluate the exact held-out dates without changing frozen evidence."""
    from .five_day_return_execution import FiveDayTrade, simulate_five_day_plan
    from .five_day_return_profiles import (
        build_five_day_return_profiles,
        five_day_profile_hash,
    )
    from .five_day_return_report import five_day_research_payload
    from .five_day_return_validation import (
        FiveDayObservation,
        evaluate_frozen_test,
        evaluate_validation_freeze,
        rank_five_day_plans,
    )
    from .validation import policy_hash

    lineage_error = "frozen five-day test lineage is invalid"
    try:
        if freeze is None:
            raise ValueError(lineage_error)
        test_dates = tuple(research.split.test)
        if (
            not research.point_in_time_complete
            or research.test_outcomes_read
            or tuple(inputs.signal_dates) != test_dates
            or not inputs.trading_dates
            or test_dates[-1] not in frozenset(inputs.trading_dates)
            or not inputs.input_fingerprint.startswith(
                f"{research.input_fingerprint}:"
            )
        ):
            raise ValueError(lineage_error)
        policy = SelectionPolicy()
        profiles = build_five_day_return_profiles()
        if (
            research.formal_rule_version != policy.rule_version
            or research.formal_policy_hash != policy_hash(policy)
            or research.profile_matrix_hash != five_day_profile_hash(profiles)
        ):
            raise ValueError(lineage_error)
        research_identity = str(
            five_day_research_payload(research)["artifact_identity"]
        )
        expected_freeze = evaluate_validation_freeze(
            research.observations,
            train_dates=research.split.train,
            validation_dates=research.split.validation,
            profile_matrix_hash=research.profile_matrix_hash,
            research_identity=research_identity,
        )
        if freeze != expected_freeze:
            raise ValueError(lineage_error)
        frozen_ids = frozenset(value.profile_id for value in freeze.profiles)
        if not frozen_ids.issubset(value.profile_id for value in profiles):
            raise ValueError(lineage_error)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc) == lineage_error:
            raise
        raise ValueError(lineage_error) from exc

    discovery = discovery_builder(
        signal_dates=test_dates,
        trading_dates=inputs.trading_dates,
        bars_by_code=inputs.bars_by_code,
        memberships=inputs.memberships,
        risk_flags=inputs.risk_flags,
        coverage_by_date=inputs.coverage_by_date,
        market_snapshots=inputs.market_snapshots,
        profiles=profiles,
        formal_policy=policy,
    )
    if tuple(discovery.signal_dates) != test_dates or discovery.incomplete_dates:
        raise ValueError("frozen five-day test inputs are incomplete")
    simulate = plan_simulator or simulate_five_day_plan
    test_set = frozenset(test_dates)
    outcome_cutoff = inputs.trading_dates[-1]
    observations: list[FiveDayObservation] = []
    frozen_plans = tuple(
        plan
        for plan in discovery.plans
        if plan.profile.profile_id in frozen_ids
    )
    ranked_plans = rank_five_day_plans(
        frozen_plans,
        freeze.calibrations,
    ).plans
    for plan in ranked_plans:
        if plan.candidate.signal_date not in test_set:
            raise ValueError("frozen five-day test discovery is out of window")
        entry_dates = tuple(
            value
            for value in inputs.trading_dates
            if plan.candidate.signal_date < value
            <= plan.candidate.valid_through_trade_date
        )
        blockers = entry_blockers_by_date(
            plan.candidate.code,
            entry_dates,
            coverage_by_date=inputs.coverage_by_date,
            risk_flags=inputs.risk_flags,
            market_snapshots=inputs.market_snapshots,
        )
        trade = simulate(
            plan,
            inputs.bars_by_code.get(normalize_code6(plan.candidate.code), ()),
            inputs.trading_dates,
            entry_blockers=blockers,
        )
        if not isinstance(trade, FiveDayTrade):
            raise TypeError("plan simulator must return FiveDayTrade")
        resolution_date = (
            trade.exit.actual_exit_date
            if trade.exit is not None
            else (
                plan.candidate.valid_through_trade_date
                if trade.status in {"NOT_TRIGGERED", "CANCELLED"}
                else outcome_cutoff
            )
        )
        observations.append(FiveDayObservation(plan, trade, resolution_date))
    ordered_observations = tuple(
        sorted(
            observations,
            key=lambda value: (
                value.plan.candidate.signal_date,
                normalize_code6(value.plan.candidate.code),
                value.plan.profile.profile_id,
            ),
        )
    )
    if any(value.trade.status == "PENDING" for value in ordered_observations):
        raise ValueError("frozen five-day test inputs are incomplete")
    assessment = evaluate_frozen_test(
        freeze,
        ordered_observations,
        test_dates=test_dates,
    )
    return FiveDayTestReview(
        signal_dates=test_dates,
        research_identity=research_identity,
        freeze_hash=freeze.freeze_hash,
        input_fingerprint=inputs.input_fingerprint,
        observations=ordered_observations,
        assessment=assessment,
        sizing_version=freeze.sizing_version,
        evaluator_version=freeze.evaluator_version,
        cost_version=freeze.cost_version,
    )


def load_mysql_five_day_inputs(
    signal_dates: Sequence[date],
    history_start: date,
    signal_end: date,
    outcome_cutoff: date,
    *,
    mysql_url: str | None = None,
    engine_factory: Callable[..., object] | None = None,
    trade_dates_loader: Callable[..., Sequence[date]] | None = None,
    bars_loader: Callable[..., Mapping[str, Sequence[BuyPointBar]]] | None = None,
    repository_factory: Callable[[object], object] | None = None,
    aggregate_loader: Callable[..., Mapping[date, object]] | None = None,
    benchmark_loader: Callable[[date, date], Mapping[str, Sequence[object]]]
    | None = None,
    market_snapshot_builder: Callable[..., Mapping[date, MarketSnapshot]]
    | None = None,
) -> FiveDayRuntimeInputs:
    """Load a bounded read-only research input bundle from configured stores."""
    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    from .historical_replay_runtime import (
        BENCHMARK_INDEX_CODES,
        _load_daily_bars,
        _load_market_aggregates,
        _trade_dates,
        build_historical_market_snapshots,
    )
    from .reference_baostock import BaoStockReferenceProvider
    from .reference_data import SQLReferenceRepository

    ordered_signals = tuple(signal_dates)
    if not ordered_signals or any(
        current <= previous
        for previous, current in zip(ordered_signals, ordered_signals[1:])
    ):
        raise ValueError("signal dates must be unique and strictly increasing")
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    load_dotenv(os.path.join(root, ".env"), override=False)
    resolved_url = (mysql_url or os.environ.get("MYSQL_URL", "")).replace(
        "host.docker.internal", "127.0.0.1"
    )
    if not resolved_url:
        raise RuntimeError("MYSQL_URL is not configured")
    create = engine_factory or create_engine
    engine = create(resolved_url, pool_pre_ping=True)
    load_dates = trade_dates_loader or _trade_dates
    load_bars = bars_loader or _load_daily_bars
    build_repository = repository_factory or SQLReferenceRepository
    load_aggregates = aggregate_loader or _load_market_aggregates
    build_markets = market_snapshot_builder or build_historical_market_snapshots

    runtime_dates = tuple(load_dates(engine, history_start, outcome_cutoff))
    required_signal_dates = tuple(
        value for value in ordered_signals if value <= signal_end
    )
    if (
        outcome_cutoff not in frozenset(runtime_dates)
        or not frozenset(required_signal_dates).issubset(runtime_dates)
    ):
        raise RuntimeError("bounded daily-bar calendar is incomplete")
    bars_by_code = {
        normalize_code6(code): tuple(values)
        for code, values in load_bars(
            engine, history_start, outcome_cutoff
        ).items()
    }
    repository = build_repository(engine)
    coverage_dates = tuple(
        value
        for value in runtime_dates
        if ordered_signals[0] <= value <= outcome_cutoff
    )
    coverage = repository.coverage_between(coverage_dates)
    memberships = tuple(
        repository.memberships_between(history_start, signal_end)
    )
    risk_flags = tuple(
        repository.risk_flags_between(ordered_signals[0], outcome_cutoff)
    )
    aggregates = load_aggregates(engine, history_start, outcome_cutoff)
    if benchmark_loader is None:
        provider = BaoStockReferenceProvider()
        with provider.session():
            benchmarks = {
                code: tuple(
                    provider.fetch_index_bars(
                        code, history_start, outcome_cutoff
                    )
                )
                for code in BENCHMARK_INDEX_CODES
            }
    else:
        benchmarks = {
            code: tuple(values)
            for code, values in benchmark_loader(
                history_start, outcome_cutoff
            ).items()
        }
    market_snapshots = dict(
        build_markets(
            runtime_dates,
            bars_by_code,
            benchmarks,
            market_aggregates_by_date=aggregates,
        )
    )
    fingerprint = _five_day_input_fingerprint(
        signal_dates=ordered_signals,
        trading_dates=runtime_dates,
        bars_by_code=bars_by_code,
        memberships=memberships,
        risk_flags=risk_flags,
        coverage_by_date=coverage,
        market_snapshots=market_snapshots,
    )
    return FiveDayRuntimeInputs(
        signal_dates=ordered_signals,
        trading_dates=runtime_dates,
        bars_by_code=bars_by_code,
        memberships=memberships,
        risk_flags=risk_flags,
        coverage_by_date=dict(coverage),
        market_snapshots=market_snapshots,
        input_fingerprint=fingerprint,
    )


def _five_day_input_fingerprint(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
) -> str:
    payload = {
        "signal_dates": [value.isoformat() for value in signal_dates],
        "trading_dates": [value.isoformat() for value in trading_dates],
        "bars": [
            {
                "code": normalize_code6(code),
                "rows": [
                    [
                        row.trade_date.isoformat(),
                        str(row.open),
                        str(row.high),
                        str(row.low),
                        str(row.close),
                        str(row.pct_chg),
                        str(row.amount_qian),
                    ]
                    for row in sorted(values, key=lambda item: item.trade_date)
                ],
            }
            for code, values in sorted(bars_by_code.items())
        ],
        "memberships": [
            [
                value.code,
                value.sector_code,
                value.sector_name,
                value.valid_from.isoformat(),
                None if value.valid_to is None else value.valid_to.isoformat(),
                value.source,
            ]
            for value in sorted(
                memberships,
                key=lambda item: (
                    item.code,
                    item.valid_from,
                    item.sector_code,
                ),
            )
        ],
        "risk_flags": [
            [
                value.code,
                value.flag_type,
                value.severity,
                value.effective_from.isoformat(),
                None
                if value.effective_to is None
                else value.effective_to.isoformat(),
                value.source,
                value.evidence_ref,
            ]
            for value in sorted(
                risk_flags,
                key=lambda item: (
                    item.code,
                    item.effective_from,
                    item.flag_type,
                ),
            )
        ],
        "coverage": [
            [
                day.isoformat(),
                value.sector_complete,
                value.st_complete,
                value.announcement_complete,
            ]
            for day, value in sorted(coverage_by_date.items())
        ],
        "markets": [
            [
                day.isoformat(),
                value.indexes_above_ma20,
                str(value.breadth_pct),
                str(value.amount_ratio),
                value.complete,
            ]
            for day, value in sorted(market_snapshots.items())
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
