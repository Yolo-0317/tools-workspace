"""Runtime evidence, release, and state gates for buy-point plans."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

from stock_ai.buy_point_selection.execution import simulate_plan
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    CandidateTier,
    SetupType,
)
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.service import BuyPointSelectionResult, SelectionItem
from stock_ai.buy_point_selection.validation import HistoricalRelease

from .contracts import CandidateV3, ForwardSelectionRunV1, PlanEventV1, TradePlanV3
from .repositories.planning import ForwardGateSummary


@dataclass(frozen=True)
class ChipEvidence:
    code: str
    trade_date: date
    cost_90_high: Decimal


@dataclass(frozen=True)
class AccountEvidence:
    captured_at: datetime
    available_cash: Decimal
    total_exposure: Decimal
    sector_exposure: Mapping[str, Decimal]
    maximum_total_exposure: Decimal = Decimal("40000")


@dataclass(frozen=True)
class MaterializationDependencies:
    chips_by_code: Mapping[str, ChipEvidence]
    account: AccountEvidence | None
    historical_release: HistoricalRelease
    forward_gate: ForwardGateSummary
    evidence_refs_by_code: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class MaterializationRequest:
    analysis_date: date
    trading_date: date
    as_of: datetime
    market_status: str
    request_live: bool
    rule_version: str


@dataclass(frozen=True)
class BuyPointRuntimeItem:
    code: str
    name: str
    tier: CandidateTier
    setup_type: SetupType | None
    reason_code: str
    missing_fields: tuple[str, ...]
    plan: TradePlanV3 | None
    maximum_shares: int | None


@dataclass(frozen=True)
class BuyPointRuntimeReport:
    analysis_date: date
    trading_date: date
    rule_version: str
    release_mode: str
    formal: tuple[BuyPointRuntimeItem, ...]
    observe: tuple[BuyPointRuntimeItem, ...]
    shadow: tuple[BuyPointRuntimeItem, ...]
    rejection_counts: Mapping[str, int]


def _uuid(kind: str, identity: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"buy-point-v3:{kind}:{identity}"))


def _trade_plan_v3(
    item: SelectionItem,
    tier: CandidateTier,
    shares: int,
    evidence_refs: tuple[str, ...],
    request: MaterializationRequest,
) -> TradePlanV3:
    if item.plan is None:
        raise ValueError("runtime materialization requires the frozen Task 4 price plan")
    plan = item.plan
    return TradePlanV3(
        plan_id=_uuid("plan", plan.structure_id),
        candidate_id=_uuid("candidate", plan.structure_id),
        analysis_date=request.analysis_date,
        trading_date=request.trading_date,
        code=item.code,
        structure_id=plan.structure_id,
        selection_tier=tier.value,
        plan_state="PREPARED",
        signal_close=plan.signal_close,
        trigger_price=plan.trigger_price,
        invalidation_price=plan.invalidation_price,
        target_2r=plan.target_2r,
        risk_distance=plan.risk_distance,
        risk_reward_ratio=plan.risk_reward_ratio,
        maximum_shares=shares,
        market_status=request.market_status,
        valid_through_trade_date=plan.valid_through_trade_date,
        valid_session_count=2,
        rule_version=request.rule_version,
        evidence_refs=evidence_refs,
        as_of=request.as_of,
        source="buy-point-selection",
        data_status="VALID",
    )


def _downgrade_reason(
    item: SelectionItem,
    dependencies: MaterializationDependencies,
    request: MaterializationRequest,
    *,
    available_cash: Decimal,
    total_exposure: Decimal,
    sector_exposure: Mapping[str, Decimal],
) -> tuple[str | None, tuple[str, ...]]:
    if request.market_status == "FREEZE":
        return "MARKET_FREEZE", ()
    chip = dependencies.chips_by_code.get(item.code)
    if chip is None:
        return "CHIP_MISSING", ("CHIP",)
    if chip.trade_date != request.analysis_date:
        return "CHIP_DATE_MISMATCH", ("CHIP_DATE",)
    if item.plan is None:
        return "PRICE_PLAN_MISSING", ("PRICE_PLAN",)
    if item.plan.trigger_price < chip.cost_90_high < item.plan.target_2r:
        return "CHIP_RESISTANCE_BEFORE_2R", ()
    account = dependencies.account
    if account is None:
        return "ACCOUNT_MISSING", ("ACCOUNT",)
    if account.captured_at.date() != request.analysis_date:
        return "ACCOUNT_STALE", ("ACCOUNT_FRESHNESS",)
    nominal = item.plan.trigger_price * Decimal(item.plan.maximum_shares)
    if available_cash < nominal:
        return "INSUFFICIENT_CASH", ()
    if total_exposure + nominal > account.maximum_total_exposure:
        return "TOTAL_EXPOSURE", ()
    if item.sector_code and sector_exposure.get(item.sector_code, Decimal("0")) > 0:
        return "SECTOR_EXPOSURE", ()
    if not dependencies.evidence_refs_by_code.get(item.code):
        return "EVIDENCE_MISSING", ("EVIDENCE",)
    return None, ()


def materialize_buy_point_selection(
    result: BuyPointSelectionResult,
    dependencies: MaterializationDependencies,
    request: MaterializationRequest,
) -> BuyPointRuntimeReport:
    release_live = (
        request.request_live
        and dependencies.historical_release.live_eligible
        and dependencies.forward_gate.eligible
    )
    formal: list[BuyPointRuntimeItem] = []
    observe: list[BuyPointRuntimeItem] = []
    shadow: list[BuyPointRuntimeItem] = []
    account = dependencies.account
    available_cash = account.available_cash if account else Decimal("0")
    total_exposure = account.total_exposure if account else Decimal("0")
    sector_exposure = dict(account.sector_exposure) if account else {}

    for item in result.qualified:
        evidence_refs = dependencies.evidence_refs_by_code.get(item.code, ())
        if not release_live:
            if dependencies.historical_release.live_eligible:
                reason = "FORWARD_GATE_NOT_READY" if request.request_live else "SHADOW_REQUESTED"
            else:
                reason = "HISTORICAL_PROMOTION_FAILED"
            plan = (
                _trade_plan_v3(item, CandidateTier.SHADOW, 0, evidence_refs, request)
                if evidence_refs
                else None
            )
            shadow.append(
                BuyPointRuntimeItem(
                    item.code,
                    item.name,
                    CandidateTier.SHADOW,
                    item.setup.setup_type,
                    reason,
                    (),
                    plan,
                    0,
                )
            )
            continue

        reason, missing = _downgrade_reason(
            item,
            dependencies,
            request,
            available_cash=available_cash,
            total_exposure=total_exposure,
            sector_exposure=sector_exposure,
        )
        if reason is not None:
            plan = (
                _trade_plan_v3(item, CandidateTier.OBSERVE, 0, evidence_refs, request)
                if evidence_refs
                else None
            )
            observe.append(
                BuyPointRuntimeItem(
                    item.code,
                    item.name,
                    CandidateTier.OBSERVE,
                    item.setup.setup_type,
                    reason,
                    missing,
                    plan,
                    None,
                )
            )
            continue

        if item.plan is None:
            raise ValueError("qualified item has no price plan")
        plan = _trade_plan_v3(
            item,
            CandidateTier.FORMAL,
            item.plan.maximum_shares,
            evidence_refs,
            request,
        )
        formal.append(
            BuyPointRuntimeItem(
                item.code,
                item.name,
                CandidateTier.FORMAL,
                item.setup.setup_type,
                "ALL_GATES_PASSED",
                (),
                plan,
                item.plan.maximum_shares,
            )
        )
        nominal = item.plan.trigger_price * Decimal(item.plan.maximum_shares)
        available_cash -= nominal
        total_exposure += nominal
        if item.sector_code:
            sector_exposure[item.sector_code] = sector_exposure.get(
                item.sector_code, Decimal("0")
            ) + nominal

    for item in result.observe:
        observe.append(
            BuyPointRuntimeItem(
                item.code,
                item.name,
                CandidateTier.OBSERVE,
                item.setup.setup_type,
                item.reasons[0] if item.reasons else "TECHNICAL_OBSERVE",
                item.missing_fields,
                None,
                None,
            )
        )
    for item in result.shadow:
        shadow.append(
            BuyPointRuntimeItem(
                item.code,
                item.name,
                CandidateTier.SHADOW,
                None,
                item.reasons[0] if item.reasons else "RESEARCH_ONLY",
                (),
                None,
                0,
            )
        )
    return BuyPointRuntimeReport(
        analysis_date=request.analysis_date,
        trading_date=request.trading_date,
        rule_version=request.rule_version,
        release_mode="LIVE" if release_live else "SHADOW",
        formal=tuple(formal),
        observe=tuple(observe),
        shadow=tuple(shadow),
        rejection_counts=result.rejection_counts,
    )


def render_buy_point_runtime_report(report: BuyPointRuntimeReport) -> str:
    lines = [f"发布模式: {report.release_mode}", "正式候选"]
    lines.extend(
        f"{item.code} {item.name} 触发价 {item.plan.trigger_price:.2f} 最大股数 {item.maximum_shares}"
        for item in report.formal
        if item.plan is not None
    )
    if not report.formal:
        lines.append("无")
    lines.append("准备中观察")
    lines.extend(
        f"{item.code} {item.name} 无交易资格 {item.reason_code}"
        for item in report.observe
    )
    if not report.observe:
        lines.append("无")
    lines.append("影子研究")
    lines.extend(
        f"{item.code} {item.name} 无交易资格 {item.reason_code}"
        for item in report.shadow
    )
    if not report.shadow:
        lines.append("无")
    lines.append("拒绝统计")
    lines.extend(f"{reason}: {count}" for reason, count in report.rejection_counts.items())
    if not report.rejection_counts:
        lines.append("无")
    return "\n".join(lines)


def _initial_event(plan: TradePlanV3, observed_at: datetime) -> PlanEventV1:
    fingerprint = hashlib.sha256(
        f"{plan.plan_id}:NONE:PREPARED:PLAN_CREATED".encode("utf-8")
    ).hexdigest()
    return PlanEventV1(
        event_id=_uuid("event", fingerprint),
        plan_id=plan.plan_id,
        structure_id=plan.structure_id,
        previous_state=None,
        new_state="PREPARED",
        reason_code="PLAN_CREATED",
        evidence_refs=plan.evidence_refs,
        observed_at=observed_at,
        event_fingerprint=fingerprint,
        as_of=observed_at,
        source="buy-point-selection",
        data_status="VALID",
    )


def persist_buy_point_runtime(
    report: BuyPointRuntimeReport,
    result: BuyPointSelectionResult,
    dependencies: MaterializationDependencies,
    request: MaterializationRequest,
    repository,
    *,
    resolved_count: int = 0,
    duplicate_count: int = 0,
    integrity_violations: Sequence[str] = (),
) -> None:
    runtime_items = {
        item.code: item
        for item in (*report.formal, *report.observe, *report.shadow)
        if item.setup_type is not None
    }
    source_items = {item.code: item for item in (*result.qualified, *result.observe)}
    rows: list[tuple[CandidateV3, TradePlanV3 | None, PlanEventV1 | None]] = []
    violations = list(integrity_violations)
    for code, source in source_items.items():
        runtime = runtime_items.get(code)
        if runtime is None:
            continue
        evidence_refs = dependencies.evidence_refs_by_code.get(code, ())
        if not evidence_refs and runtime.tier is CandidateTier.FORMAL:
            violations.append(f"EVIDENCE_MISSING:{code}")
            continue
        candidate = CandidateV3(
            candidate_id=(
                runtime.plan.candidate_id
                if runtime.plan is not None
                else _uuid("candidate", source.setup.code + source.setup.structure_start.isoformat())
            ),
            analysis_date=request.analysis_date,
            trading_date=request.trading_date,
            code=code,
            name=source.name,
            candidate_type=source.setup.setup_type.value,
            selection_tier=runtime.tier.value,
            executable_status=(
                "EXECUTABLE" if runtime.tier is CandidateTier.FORMAL else "OBSERVE"
            ),
            structure_id=(
                runtime.plan.structure_id
                if runtime.plan is not None
                else _uuid("structure", code + source.setup.structure_start.isoformat()).replace("-", "")
            ),
            pattern_quality=source.setup.quality,
            sector=source.sector_code,
            sector_metrics={
                "percentile": str(source.sector_percentile)
                if source.sector_percentile is not None
                else None
            },
            missing_fields=runtime.missing_fields,
            rejected_reasons=(
                () if runtime.tier is CandidateTier.FORMAL else (runtime.reason_code,)
            ),
            rule_version=request.rule_version,
            evidence_refs=evidence_refs,
            as_of=request.as_of,
            source="buy-point-selection",
            data_status="VALID",
        )
        event = _initial_event(runtime.plan, request.as_of) if runtime.plan else None
        rows.append((candidate, runtime.plan, event))

    forward_run = ForwardSelectionRunV1(
        run_id=_uuid("forward-run", f"{request.analysis_date}:{request.rule_version}"),
        analysis_date=request.analysis_date,
        rule_version=request.rule_version,
        formal_count=len(report.formal),
        observe_count=len(report.observe),
        shadow_count=len(report.shadow),
        resolved_count=resolved_count,
        duplicate_count=duplicate_count,
        integrity_violations=tuple(dict.fromkeys(violations)),
        release_mode=report.release_mode,
        as_of=request.as_of,
        source="buy-point-selection",
        data_status="VALID",
    )
    repository.save_buy_point_run(tuple(rows), forward_run)


def _event_for(plan: TradePlanV3, new_state: str, reason_code: str, observed_at: datetime) -> PlanEventV1:
    fingerprint = hashlib.sha256(
        ":".join(
            (
                plan.plan_id,
                "PREPARED",
                new_state,
                reason_code,
                observed_at.isoformat(),
            )
        ).encode("utf-8")
    ).hexdigest()
    return PlanEventV1(
        event_id=_uuid("event", fingerprint),
        plan_id=plan.plan_id,
        structure_id=plan.structure_id,
        previous_state="PREPARED",
        new_state=new_state,
        reason_code=reason_code,
        evidence_refs=plan.evidence_refs,
        observed_at=observed_at,
        event_fingerprint=fingerprint,
        as_of=observed_at,
        source="buy-point-state-advance",
        data_status="VALID",
    )


def advance_buy_point_plan_states(
    open_plans: Sequence[TradePlanV3],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    market_state: str,
    risk_flags: Mapping[str, Sequence[object]],
) -> tuple[PlanEventV1, ...]:
    events: list[PlanEventV1] = []
    for plan in open_plans:
        if plan.plan_state != "PREPARED":
            continue
        bars = tuple(sorted(bars_by_code.get(plan.code, ()), key=lambda value: value.trade_date))
        observed_date = bars[-1].trade_date if bars else plan.analysis_date
        observed_at = datetime.combine(observed_date, time(7, 0), tzinfo=timezone.utc)
        if market_state == "FREEZE":
            events.append(_event_for(plan, "INVALIDATED", "MARKET_FREEZE", observed_at))
            continue
        if any(getattr(value, "severity", None) == "VETO" for value in risk_flags.get(plan.code, ())):
            events.append(_event_for(plan, "INVALIDATED", "POINT_IN_TIME_RISK_VETO", observed_at))
            continue
        if bars and any(
            value.low <= plan.invalidation_price and value.high < plan.trigger_price
            for value in bars[:2]
        ):
            events.append(_event_for(plan, "INVALIDATED", "STRUCTURE_BROKEN", observed_at))
            continue
        price_plan = PricePlan(
            structure_id=plan.structure_id,
            code=plan.code,
            setup_type=SetupType.PRE_BREAKOUT,
            signal_date=plan.analysis_date,
            signal_close=plan.signal_close,
            trigger_price=plan.trigger_price,
            invalidation_price=plan.invalidation_price,
            target_2r=plan.target_2r,
            risk_distance=plan.risk_distance,
            risk_reward_ratio=plan.risk_reward_ratio,
            maximum_shares=plan.maximum_shares or 0,
            valid_through_trade_date=plan.valid_through_trade_date,
        )
        simulated = simulate_plan(price_plan, bars, sector_code="")
        if simulated.entry_date is not None:
            events.append(
                _event_for(plan, "TRIGGERED", "PRICE_TRIGGER_SIMULATED", observed_at)
            )
        elif simulated.status == "EXPIRED":
            events.append(_event_for(plan, "EXPIRED", "TRIGGER_WINDOW_ENDED", observed_at))
        elif simulated.status in {"GAP_CANCELLED", "CHASE_CANCELLED", "LOCKED_LIMIT_UP"}:
            events.append(_event_for(plan, "INVALIDATED", simulated.status, observed_at))
    return tuple(events)
