"""Pure diagnostic models for short-window buy-point case reviews."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from bisect import bisect_right
from typing import Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .gates import anti_chase_gate, base_gate, classify_market, sector_gate
from .historical_replay import second_trading_date_after
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
class CaseSignalReplay:
    traces: Mapping[tuple[date, str], GateTrace]
    incomplete_dates: tuple[date, ...]
    strict_shadow: tuple[CaseCandidate, ...] = ()
    near_misses: tuple[CaseCandidate, ...] = ()


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
