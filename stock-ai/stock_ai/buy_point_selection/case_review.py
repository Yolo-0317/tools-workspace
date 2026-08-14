"""Pure diagnostic models for short-window buy-point case reviews."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from bisect import bisect_right
import hashlib
from typing import TYPE_CHECKING, Mapping, Sequence

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6

from .gates import anti_chase_gate, base_gate, classify_market, sector_gate
from .historical_replay import second_trading_date_after
from .execution import ExecutionCosts, simulate_plan
from .models import BuyPointBar, DetectedSetup, MarketSnapshot, SelectionPolicy
from .patterns import detect_setups
from .planning import (
    PricePlan,
    RiskBudget,
    atr14,
    build_price_plan,
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

if TYPE_CHECKING:
    from .resistance_research import SignificantResistanceProfile


ALLOWED_SOFT_REASONS = frozenset(
    {
        "SECTOR_RELATIVE_STRENGTH_WEAK",
        "SECTOR_BREADTH_WEAK",
        "SECTOR_NOT_RESONATING",
        "SECTOR_AMOUNT_WEAK",
        "INSUFFICIENT_TWO_R_SPACE",
        "RISK_DISTANCE_OUT_OF_RANGE",
    }
)
CASE_RISK_BUDGET = RiskBudget(
    loss_budget=Decimal("500"),
    ticket_limit=Decimal("4000"),
    remaining_exposure=Decimal("40000"),
)


@dataclass(frozen=True)
class GateTrace:
    code: str
    signal_date: date
    failed_reasons: tuple[str, ...]
    passed_stages: tuple[str, ...]
    metrics: Mapping[str, Decimal]
    analysis_bar_date: date | None = None
    consumed_bar_dates: tuple[date, ...] = ()

    @property
    def first_rejection(self) -> str | None:
        return self.failed_reasons[0] if self.failed_reasons else None


@dataclass(frozen=True)
class NearMissDecision:
    admitted: bool
    soft_reason: str | None
    ranking_key: tuple[Decimal | str, ...] | None


@dataclass(frozen=True)
class ConditionalShadowDecision:
    admitted: bool
    tier: str | None
    effective_resistance_r: Decimal | None


@dataclass(frozen=True)
class CaseCandidate:
    code: str
    signal_date: date
    setup: DetectedSetup
    plan: PricePlan
    tier: str
    soft_reason: str | None
    ranking_key: tuple[Decimal | str, ...]
    executable_shares: int = 0


@dataclass(frozen=True)
class OpportunityEpisode:
    episode_id: str
    representative: CaseCandidate
    member_signal_dates: tuple[date, ...]
    member_tiers: tuple[str, ...]


@dataclass(frozen=True)
class ConditionalShadowOpportunity:
    episode_id: str
    candidate: CaseCandidate
    effective_resistance_r: Decimal


def classify_conditional_two_r_shadow(
    candidate: CaseCandidate,
    trace: GateTrace,
) -> ConditionalShadowDecision:
    """Admit only zero-share 2R near misses with at least 1.5R room."""
    reasons = tuple(dict.fromkeys(trace.failed_reasons))
    if (
        candidate.tier != "NEAR_MISS"
        or candidate.soft_reason != "INSUFFICIENT_TWO_R_SPACE"
        or candidate.executable_shares != 0
        or reasons != ("INSUFFICIENT_TWO_R_SPACE",)
    ):
        return ConditionalShadowDecision(False, None, None)
    try:
        resistance = Decimal(str(trace.metrics["nearest_resistance"]))
    except (InvalidOperation, KeyError, TypeError, ValueError):
        return ConditionalShadowDecision(False, None, None)
    risk = candidate.plan.risk_distance
    if not resistance.is_finite() or not risk.is_finite() or risk <= 0:
        return ConditionalShadowDecision(False, None, None)
    effective_r = (resistance - candidate.plan.trigger_price) / risk
    if not effective_r.is_finite():
        return ConditionalShadowDecision(False, None, None)
    admitted = Decimal("1.5") <= effective_r < Decimal("2")
    return ConditionalShadowDecision(
        admitted,
        "TWO_R_CONDITIONAL_SHADOW" if admitted else None,
        effective_r,
    )


def _episode_id(representative: CaseCandidate) -> str:
    payload = ":".join(
        (
            normalize_code6(representative.code),
            representative.signal_date.isoformat(),
            representative.plan.structure_id,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_opportunity_episodes(
    candidates: Sequence[CaseCandidate],
) -> tuple[OpportunityEpisode, ...]:
    """Merge same-code signals while the earliest plan remains active."""
    ordered = sorted(
        candidates,
        key=lambda value: (
            value.signal_date,
            normalize_code6(value.code),
            value.ranking_key,
            value.tier,
            value.plan.structure_id,
        ),
    )
    episodes: list[OpportunityEpisode] = []
    latest_by_code: dict[str, int] = {}
    for candidate in ordered:
        code = normalize_code6(candidate.code)
        episode_index = latest_by_code.get(code)
        if episode_index is not None:
            episode = episodes[episode_index]
            if (
                candidate.signal_date
                <= episode.representative.plan.valid_through_trade_date
            ):
                episodes[episode_index] = replace(
                    episode,
                    member_signal_dates=tuple(
                        sorted(
                            set(episode.member_signal_dates)
                            | {candidate.signal_date}
                        )
                    ),
                    member_tiers=tuple(
                        dict.fromkeys((*episode.member_tiers, candidate.tier))
                    ),
                )
                continue
        latest_by_code[code] = len(episodes)
        episodes.append(
            OpportunityEpisode(
                _episode_id(candidate),
                candidate,
                (candidate.signal_date,),
                (candidate.tier,),
            )
        )
    return tuple(episodes)


def build_conditional_two_r_shadow(
    episodes: Sequence[OpportunityEpisode],
    traces: Mapping[tuple[date, str], GateTrace],
) -> tuple[ConditionalShadowOpportunity, ...]:
    """Classify episode representatives without consulting outcomes."""
    cohort: list[ConditionalShadowOpportunity] = []
    for episode in episodes:
        candidate = episode.representative
        trace = traces.get((candidate.signal_date, normalize_code6(candidate.code)))
        if trace is None:
            continue
        decision = classify_conditional_two_r_shadow(candidate, trace)
        if not decision.admitted or decision.effective_resistance_r is None:
            continue
        cohort.append(
            ConditionalShadowOpportunity(
                episode.episode_id,
                candidate,
                decision.effective_resistance_r,
            )
        )
    return tuple(sorted(cohort, key=lambda value: value.episode_id))


@dataclass(frozen=True)
class CaseSignalReplay:
    traces: Mapping[tuple[date, str], GateTrace]
    incomplete_dates: tuple[date, ...]
    strict_shadow: tuple[CaseCandidate, ...] = ()
    near_misses: tuple[CaseCandidate, ...] = ()


@dataclass(frozen=True)
class CaseOutcome:
    code: str
    signal_date: date
    tier: str
    status: str
    mfe: Decimal | None
    mae: Decimal | None
    trigger_date: date | None = None
    entry_price: Decimal | None = None
    net_return: Decimal | None = None
    close_return: Decimal | None = None
    stop_first: bool = False
    intraday_order_ambiguous: bool = False
    structure_id: str = ""

    @property
    def success(self) -> bool | None:
        return classify_case_success(
            triggered=self.mfe is not None and self.mae is not None,
            pending=self.status == "PENDING",
            mfe=self.mfe,
            mae=self.mae,
        )


@dataclass(frozen=True)
class CaseOutcomeSummary:
    total: int
    pending: int
    resolved: int
    successes: int
    failures: int


@dataclass(frozen=True)
class BuyableWinner:
    code: str
    signal_date: date
    maximum_gain: Decimal
    first_buyable_date: date
    captured_tiers: tuple[str, ...] = ()
    first_rejection: str | None = None


@dataclass(frozen=True)
class CaseReview:
    signal_dates: tuple[date, ...]
    outcome_cutoff: date
    rule_version: str
    policy_hash: str
    replay: CaseSignalReplay
    outcomes: tuple[CaseOutcome, ...]
    winners: tuple[BuyableWinner, ...]
    risk_coverage_complete: bool
    episodes: tuple[OpportunityEpisode, ...] = ()
    conditional_two_r_shadow: tuple[ConditionalShadowOpportunity, ...] = ()
    resistance_profiles: tuple[SignificantResistanceProfile, ...] = ()


def classify_near_miss(
    trace: GateTrace,
    *,
    setup_quality: Decimal,
    average_amount5_qian: Decimal,
) -> NearMissDecision:
    """Admit only one explicitly approved soft-gate failure."""
    reasons = tuple(dict.fromkeys(trace.failed_reasons))
    if len(reasons) != 1 or reasons[0] not in ALLOWED_SOFT_REASONS:
        return NearMissDecision(False, None, None)
    deviation = Decimal(str(trace.metrics.get("boundary_deviation", Decimal("1"))))
    return NearMissDecision(
        admitted=True,
        soft_reason=reasons[0],
        ranking_key=(
            deviation,
            -setup_quality,
            -average_amount5_qian,
            normalize_code6(trace.code),
        ),
    )


def classify_case_success(
    *,
    triggered: bool,
    pending: bool,
    mfe: Decimal | None,
    mae: Decimal | None,
) -> bool | None:
    if pending:
        return None
    if not triggered or mfe is None or mae is None:
        return False
    return mfe >= Decimal("0.05") and mae <= Decimal("0.03")


def summarize_case_outcomes(
    outcomes: Sequence[CaseOutcome],
) -> CaseOutcomeSummary:
    pending = sum(value.success is None for value in outcomes)
    successes = sum(value.success is True for value in outcomes)
    resolved = len(outcomes) - pending
    return CaseOutcomeSummary(
        total=len(outcomes),
        pending=pending,
        resolved=resolved,
        successes=successes,
        failures=resolved - successes,
    )


def evaluate_case_plan(
    candidate: CaseCandidate,
    bars: Sequence[BuyPointBar],
    *,
    outcome_cutoff: date,
    costs: ExecutionCosts | None = None,
) -> CaseOutcome:
    """Evaluate a frozen case plan only through the requested complete cutoff."""
    bounded = tuple(
        sorted(
            (
                value
                for value in bars
                if candidate.signal_date < value.trade_date <= outcome_cutoff
            ),
            key=lambda value: value.trade_date,
        )
    )
    trade = simulate_plan(
        candidate.plan,
        bounded,
        costs,
        sector_code="",
    )
    status = "PENDING" if trade.outcome.value == "PENDING" else trade.status
    close_return = None
    if trade.entry_price is not None and bounded:
        close_return = bounded[-1].close / trade.entry_price - Decimal("1")
    return CaseOutcome(
        code=candidate.code,
        signal_date=candidate.signal_date,
        tier=candidate.tier,
        status=status,
        mfe=trade.mfe,
        mae=trade.mae,
        trigger_date=trade.entry_date,
        entry_price=trade.entry_price,
        net_return=trade.net_return,
        close_return=close_return,
        stop_first=trade.outcome.value == "STOP_FIRST",
        intraday_order_ambiguous=trade.intraday_order_ambiguous,
        structure_id=candidate.plan.structure_id,
    )


def find_buyable_winners(
    *,
    signal_date: date,
    outcome_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    risk_flags: Sequence[RiskFlag],
    holding_codes: frozenset[str],
    policy: SelectionPolicy | None = None,
) -> tuple[BuyableWinner, ...]:
    """Find hindsight winners that still offered a normal, compliant entry."""
    resolved = policy or SelectionPolicy()
    dated_flags = risk_flags_on(risk_flags, signal_date)
    vetoed = {
        code
        for code, flags in dated_flags.items()
        if any(value.severity == "VETO" for value in flags)
    }
    held = {normalize_code6(value) for value in holding_codes}
    outcome_set = frozenset(outcome_dates)
    winners: list[BuyableWinner] = []
    for raw_code, values in sorted(bars_by_code.items()):
        code = normalize_code6(raw_code)
        if not is_sh_sz_main_board_code(code) or code in vetoed or code in held:
            continue
        ordered = tuple(sorted(values, key=lambda value: value.trade_date))
        history = tuple(value for value in ordered if value.trade_date <= signal_date)
        if len(history) < 5 or history[-1].trade_date != signal_date:
            continue
        average_amount5 = _average([value.amount_qian for value in history[-5:]])
        if average_amount5 < resolved.min_average_amount5_qian:
            continue
        outcome = tuple(value for value in ordered if value.trade_date in outcome_set)
        if not outcome:
            continue
        maximum_gain = max(value.high for value in outcome) / history[-1].close - Decimal("1")
        if maximum_gain < Decimal("0.05"):
            continue
        previous_close = history[-1].close
        first_buyable_date: date | None = None
        for value in outcome:
            locked_limit_up = (
                value.open == value.high == value.low == value.close
                and value.pct_chg >= Decimal("9.5")
            )
            gap = value.open / previous_close - Decimal("1")
            if not locked_limit_up and gap <= Decimal("0.03"):
                first_buyable_date = value.trade_date
                break
            previous_close = value.close
        if first_buyable_date is None:
            continue
        winners.append(
            BuyableWinner(code, signal_date, maximum_gain, first_buyable_date)
        )
    return tuple(sorted(winners, key=lambda value: value.code))


def attribute_buyable_winners(
    winners: Sequence[BuyableWinner],
    replay: CaseSignalReplay,
) -> tuple[BuyableWinner, ...]:
    """Join hindsight winners to frozen candidate tiers and signal-date traces."""
    candidates = (*replay.strict_shadow, *replay.near_misses)
    attributed: list[BuyableWinner] = []
    for winner in winners:
        tiers = tuple(
            sorted(
                {
                    value.tier
                    for value in candidates
                    if value.code == winner.code
                }
            )
        )
        trace = replay.traces.get((winner.signal_date, winner.code))
        attributed.append(
            replace(
                winner,
                captured_tiers=tiers,
                first_rejection=(
                    None if tiers or trace is None else trace.first_rejection
                ),
            )
        )
    return tuple(sorted(attributed, key=lambda value: value.code))


def _bars_on_or_before(
    bars: Sequence[BuyPointBar], analysis_date: date
) -> tuple[BuyPointBar, ...]:
    ordered = tuple(sorted(bars, key=lambda value: value.trade_date))
    dates = tuple(value.trade_date for value in ordered)
    stop = bisect_right(dates, analysis_date)
    return ordered[max(0, stop - 120) : stop]


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _cumulative_return_pct(bars: Sequence[BuyPointBar], sessions: int) -> Decimal:
    return (bars[-1].close / bars[-sessions - 1].close - Decimal("1")) * Decimal("100")


def _sector_boundary_deviation(
    reason: str,
    sector: object,
    policy: SelectionPolicy,
) -> Decimal:
    actual_and_minimum = {
        "SECTOR_RELATIVE_STRENGTH_WEAK": (
            Decimal(str(getattr(sector, "return_percentile"))),
            Decimal(str(policy.sector_return_percentile_min)),
        ),
        "SECTOR_NOT_RESONATING": (
            Decimal(str(getattr(sector, "strengthening_member_count"))),
            Decimal(str(policy.sector_strengthening_members_min)),
        ),
        "SECTOR_BREADTH_WEAK": (
            Decimal(str(getattr(sector, "breadth_ratio"))),
            Decimal(str(policy.sector_breadth_min)),
        ),
        "SECTOR_AMOUNT_WEAK": (
            Decimal(str(getattr(sector, "amount_ratio"))),
            Decimal(str(policy.sector_amount_ratio_min)),
        ),
    }
    actual, minimum = actual_and_minimum.get(reason, (Decimal("0"), Decimal("1")))
    if minimum <= 0:
        return Decimal("0")
    return max(Decimal("0"), (minimum - actual) / minimum)


def _diagnostic_price_plan(
    setup: DetectedSetup,
    bars: Sequence[BuyPointBar],
    budget: RiskBudget,
    market_status: str,
    policy: SelectionPolicy,
    valid_through_trade_date: date,
) -> tuple[PricePlan | None, tuple[str, ...], Mapping[str, Decimal]]:
    """Build a zero-share case plan while exposing all approved soft failures."""
    if market_status not in {"ALLOW", "LIMITED"} or not bars:
        return None, ("MARKET_FREEZE",), {}
    volatility = atr14(bars)
    if not volatility.is_finite() or volatility <= 0:
        return None, ("ATR_UNAVAILABLE",), {}
    cent = Decimal("0.01")
    trigger = (setup.structure_high + cent).quantize(cent, rounding=ROUND_CEILING)
    invalidation = (
        setup.structure_low - Decimal("0.2") * volatility
    ).quantize(cent, rounding=ROUND_FLOOR)
    risk = trigger - invalidation
    if risk <= 0:
        return None, ("RISK_DISTANCE_OUT_OF_RANGE",), {
            "boundary_deviation": Decimal("1")
        }
    risk_pct = risk / trigger
    minimum_risk_pct = max(Decimal("0.015"), Decimal("0.8") * volatility / trigger)
    reasons: list[str] = []
    metrics: dict[str, Decimal] = {"risk_fraction": risk_pct}
    if not minimum_risk_pct <= risk_pct <= Decimal("0.05"):
        reasons.append("RISK_DISTANCE_OUT_OF_RANGE")
        if risk_pct < minimum_risk_pct:
            metrics["boundary_deviation"] = (
                minimum_risk_pct - risk_pct
            ) / minimum_risk_pct
        else:
            metrics["boundary_deviation"] = (
                risk_pct - Decimal("0.05")
            ) / Decimal("0.05")
    target = (trigger + Decimal("2") * risk).quantize(
        cent, rounding=ROUND_CEILING
    )
    resistance = nearest_resistance_above(trigger, bars)
    if resistance < target:
        reasons.append("INSUFFICIENT_TWO_R_SPACE")
        metrics["nearest_resistance"] = resistance
        metrics["boundary_deviation"] = (target - resistance) / (
            target - trigger
        )
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
    shares = int(
        (maximum_value / Decimal("100")).to_integral_value(
            rounding=ROUND_FLOOR
        )
        * Decimal("100")
    )
    if shares < 100:
        return None, tuple(reasons) + ("POSITION_BELOW_BOARD_LOT",), metrics
    return (
        PricePlan(
            structure_id=structure_id(setup.code, setup, policy.rule_version),
            code=normalize_code6(setup.code),
            setup_type=setup.setup_type,
            signal_date=setup.analysis_date,
            signal_close=bars[-1].close,
            trigger_price=trigger,
            invalidation_price=invalidation,
            target_2r=target,
            risk_distance=risk,
            risk_reward_ratio=Decimal("2"),
            maximum_shares=shares,
            valid_through_trade_date=valid_through_trade_date,
        ),
        tuple(reasons),
        metrics,
    )


def replay_case_signals(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
    holding_codes_by_date: Mapping[date, frozenset[str]] | None = None,
    policy: SelectionPolicy | None = None,
) -> CaseSignalReplay:
    """Replay the initial point-in-time gates without reading future bars."""
    resolved = policy or SelectionPolicy()
    traces: dict[tuple[date, str], GateTrace] = {}
    incomplete_dates: list[date] = []
    strict_shadow: list[CaseCandidate] = []
    near_misses: list[CaseCandidate] = []
    holdings = holding_codes_by_date or {}
    for signal_date in sorted(set(signal_dates)):
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
        market = classify_market(market_snapshot)
        dated_flags = risk_flags_on(risk_flags, signal_date)
        dated_memberships = membership_on(memberships, signal_date)
        panel = {
            normalize_code6(raw_code): _bars_on_or_before(all_bars, signal_date)
            for raw_code, all_bars in bars_by_code.items()
        }
        from .historical_replay_runtime import _sector_snapshots

        sectors = _sector_snapshots(panel, dated_memberships, resolved)
        for code, bars in sorted(panel.items()):
            consumed_dates = tuple(value.trade_date for value in bars)
            if not bars or bars[-1].trade_date != signal_date:
                traces[(signal_date, code)] = GateTrace(
                    code,
                    signal_date,
                    ("LATEST_BAR_MISSING",),
                    (),
                    {},
                    bars[-1].trade_date if bars else None,
                    consumed_dates,
                )
                continue
            if not market.passed:
                traces[(signal_date, code)] = GateTrace(
                    code,
                    signal_date,
                    market.reasons,
                    ("LATEST_BAR",),
                    {},
                    bars[-1].trade_date,
                    consumed_dates,
                )
                continue
            base = base_gate(
                code,
                bars,
                set(holdings.get(signal_date, frozenset())),
                dated_flags,
                resolved,
            )
            if not base.passed:
                traces[(signal_date, code)] = GateTrace(
                    code,
                    signal_date,
                    base.reasons,
                    ("LATEST_BAR", "MARKET"),
                    {},
                    bars[-1].trade_date,
                    consumed_dates,
                )
                continue
            setups = detect_setups(code, bars, resolved)
            if not setups:
                traces[(signal_date, code)] = GateTrace(
                    code,
                    signal_date,
                    ("NO_BUY_POINT_SETUP",),
                    ("LATEST_BAR", "MARKET", "BASE"),
                    {},
                    bars[-1].trade_date,
                    consumed_dates,
                )
                continue
            setup = max(setups, key=lambda value: (value.quality, value.setup_type.value))
            ma5 = _average([value.close for value in bars[-5:]])
            ma20 = _average([value.close for value in bars[-20:]])
            anti = anti_chase_gate(
                bars[-1].pct_chg,
                _cumulative_return_pct(bars, 3),
                _cumulative_return_pct(bars, 5),
                (bars[-1].close / ma5 - Decimal("1")) * Decimal("100"),
                (bars[-1].close / ma20 - Decimal("1")) * Decimal("100"),
                resolved,
            )
            if not anti.passed:
                traces[(signal_date, code)] = GateTrace(
                    code,
                    signal_date,
                    anti.reasons,
                    ("LATEST_BAR", "MARKET", "BASE", "SETUP"),
                    {"setup_quality": setup.quality},
                    bars[-1].trade_date,
                    consumed_dates,
                )
                continue
            membership = dated_memberships.get(code)
            if membership is None or membership.sector_code not in sectors:
                traces[(signal_date, code)] = GateTrace(
                    code,
                    signal_date,
                    ("SECTOR_MISSING",),
                    ("LATEST_BAR", "MARKET", "BASE", "SETUP", "ANTI_CHASE"),
                    {"setup_quality": setup.quality},
                    bars[-1].trade_date,
                    consumed_dates,
                )
                continue
            sector = sector_gate(sectors[membership.sector_code], resolved)
            common_passed = (
                "LATEST_BAR",
                "MARKET",
                "BASE",
                "SETUP",
                "ANTI_CHASE",
            )
            average_amount5 = _average([value.amount_qian for value in bars[-5:]])
            if not sector.passed:
                metrics = {
                    "setup_quality": setup.quality,
                    "average_amount5_qian": average_amount5,
                }
                if len(sector.reasons) == 1:
                    metrics["boundary_deviation"] = _sector_boundary_deviation(
                        sector.reasons[0],
                        sectors[membership.sector_code],
                        resolved,
                    )
                trace = GateTrace(
                    code,
                    signal_date,
                    sector.reasons,
                    common_passed,
                    metrics,
                    bars[-1].trade_date,
                    consumed_dates,
                )
                traces[(signal_date, code)] = trace
                decision = classify_near_miss(
                    trace,
                    setup_quality=setup.quality,
                    average_amount5_qian=average_amount5,
                )
                if decision.admitted and decision.ranking_key is not None:
                    plan = build_price_plan(
                        setup,
                        bars,
                        CASE_RISK_BUDGET,
                        market.status,
                        resolved,
                        valid_through_trade_date=second_trading_date_after(
                            trading_dates, signal_date
                        ),
                    )
                    if plan.plan is not None:
                        near_misses.append(
                            CaseCandidate(
                                code,
                                signal_date,
                                setup,
                                plan.plan,
                                "NEAR_MISS",
                                decision.soft_reason,
                                decision.ranking_key,
                            )
                        )
                continue
            plan = build_price_plan(
                setup,
                bars,
                CASE_RISK_BUDGET,
                market.status,
                resolved,
                valid_through_trade_date=second_trading_date_after(
                    trading_dates, signal_date
                ),
            )
            failed = plan.reasons
            passed = common_passed + ("SECTOR",) + (("PRICE_PLAN",) if plan.plan else ())
            diagnostic_plan = plan.plan
            diagnostic_metrics: Mapping[str, Decimal] = {}
            if plan.plan is None:
                diagnostic_plan, failed, diagnostic_metrics = _diagnostic_price_plan(
                    setup,
                    bars,
                    CASE_RISK_BUDGET,
                    market.status,
                    resolved,
                    second_trading_date_after(trading_dates, signal_date),
                )
            traces[(signal_date, code)] = GateTrace(
                code,
                signal_date,
                failed,
                passed,
                {
                    "setup_quality": setup.quality,
                    "average_amount5_qian": average_amount5,
                    **diagnostic_metrics,
                },
                bars[-1].trade_date,
                consumed_dates,
            )
            if plan.plan is not None:
                strict_shadow.append(
                    CaseCandidate(
                        code,
                        signal_date,
                        setup,
                        plan.plan,
                        "STRICT_SHADOW",
                        None,
                        (
                            -setup.quality,
                            -average_amount5,
                            code,
                        ),
                    )
                )
            elif diagnostic_plan is not None:
                trace = traces[(signal_date, code)]
                decision = classify_near_miss(
                    trace,
                    setup_quality=setup.quality,
                    average_amount5_qian=average_amount5,
                )
                if decision.admitted and decision.ranking_key is not None:
                    near_misses.append(
                        CaseCandidate(
                            code,
                            signal_date,
                            setup,
                            diagnostic_plan,
                            "NEAR_MISS",
                            decision.soft_reason,
                            decision.ranking_key,
                        )
                    )
    capped_near_misses: list[CaseCandidate] = []
    for signal_date in sorted(set(signal_dates)):
        dated = sorted(
            (value for value in near_misses if value.signal_date == signal_date),
            key=lambda value: value.ranking_key,
        )
        capped_near_misses.extend(dated[:10])
    return CaseSignalReplay(
        traces,
        tuple(sorted(incomplete_dates)),
        tuple(
            sorted(
                strict_shadow,
                key=lambda value: (value.signal_date, value.ranking_key),
            )
        ),
        tuple(capped_near_misses),
    )
