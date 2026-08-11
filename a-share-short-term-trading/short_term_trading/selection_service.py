"""Materialize pure selector signals into auditable candidates and trade plans."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Callable, Literal, Protocol, Sequence
from uuid import UUID, uuid5

from stock_ai.short_term_selection import CandidateSignal, SelectionResult

from .contracts import CandidateV2, DataStatus, SignalStatus, TradePlanV2
from .daily_sync import DailyBar
from .diagnosis import RiskProfile, TradePlanDraft, build_eod_trade_plan
from .evidence import EvidenceSnapshot, is_chip_snapshot_for_trade_date
from .market_regime import MarketStateView


SELECTION_NAMESPACE = UUID("6930200c-c1ee-4c3c-9767-7941fd1b1fab")
SOURCE = "short-term-auto-selection"


class EvidenceStore(Protocol):
    def save_snapshot(self, snapshot: EvidenceSnapshot) -> None: ...

    def get_latest_valid_snapshot(self, code: str, kind: str) -> EvidenceSnapshot | None: ...


class PlanningStore(Protocol):
    def upsert_candidate(self, candidate: CandidateV2) -> None: ...

    def upsert_plan(self, plan: TradePlanV2) -> None: ...


@dataclass(frozen=True)
class SelectionDependencies:
    evidence_repository: EvidenceStore
    planning_repository: PlanningStore
    load_daily_bars: Callable[[str, date], list[DailyBar]]
    refresh_chip: Callable[[str, date], None]


@dataclass(frozen=True)
class SelectionRequest:
    analysis_date: date
    trading_date: date
    now: datetime
    market_state: MarketStateView
    risk_profile: RiskProfile
    portfolio_approved: bool
    rule_version: str = "short-term-selection-2.0.0"


@dataclass(frozen=True)
class SelectionItem:
    code: str
    name: str
    candidate_type: Literal["BREAKOUT", "PULLBACK"]
    setup_score: float
    source_strategies: tuple[str, ...]
    reasons: tuple[str, ...]
    status: Literal["OBSERVE", "EXECUTABLE"]
    reason: str
    plan: TradePlanV2 | None


@dataclass(frozen=True)
class SelectionReport:
    analysis_date: date
    trading_date: date
    market_status: str
    market_reasons: tuple[str, ...]
    items: tuple[SelectionItem, ...]
    rejection_counts: dict[str, int]
    rule_version: str = "short-term-selection-2.0.0"


def deterministic_id(
    kind: str,
    analysis_date: date,
    code: str,
    candidate_type: str,
    rule_version: str,
) -> str:
    value = f"{kind}:{analysis_date.isoformat()}:{code}:{candidate_type}:{rule_version}"
    return str(uuid5(SELECTION_NAMESPACE, value))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _atr14(bars: Sequence[DailyBar]) -> float:
    ranges: list[float] = []
    for previous, current in zip(bars[-15:-1], bars[-14:]):
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    if len(ranges) != 14:
        raise ValueError("日线不足 15 根，不能计算 ATR14")
    return _mean(ranges)


def _technical_snapshot(
    signal: CandidateSignal,
    bars: Sequence[DailyBar],
    request: SelectionRequest,
) -> EvidenceSnapshot:
    closes = [bar.close for bar in bars]
    if len(bars) < 21 or bars[-1].trade_date != request.analysis_date:
        raise ValueError("日线数量不足或末日与分析日期不一致")
    payload = {
        **signal.metrics,
        "ma5": _mean(closes[-5:]),
        "ma10": _mean(closes[-10:]),
        "ma20": _mean(closes[-20:]),
        "atr14": (
            signal.metrics["atr14"]
            if "atr14" in signal.metrics
            else _atr14(bars)
        ),
        "high20": max(bar.high for bar in bars[-20:]),
        "low10": min(bar.low for bar in bars[-10:]),
        "analysis_date": request.analysis_date.isoformat(),
        "source_strategies": list(signal.source_strategies),
    }
    return EvidenceSnapshot(
        snapshot_id=deterministic_id(
            "evidence", request.analysis_date, signal.code, signal.candidate_type, request.rule_version
        ),
        code=signal.code,
        kind="daily_technical",
        as_of=request.now,
        source=SOURCE,
        parser_version=request.rule_version,
        data=payload,
        raw_evidence_ref=f"mysql:stock_daily:{signal.code}:{request.analysis_date.isoformat()}",
    )


def _candidate(
    signal: CandidateSignal,
    request: SelectionRequest,
    evidence_id: str,
    status: Literal["OBSERVE", "EXECUTABLE", "REJECTED"],
    rejected_reasons: tuple[str, ...] = (),
) -> CandidateV2:
    return CandidateV2(
        candidate_id=deterministic_id(
            "candidate", request.analysis_date, signal.code, signal.candidate_type, request.rule_version
        ),
        analysis_date=request.analysis_date,
        trading_date=request.trading_date,
        code=signal.code,
        name=signal.name,
        candidate_type=signal.candidate_type,
        setup_score=Decimal(str(signal.setup_score)),
        liquidity_score=Decimal(str(signal.liquidity_score)),
        trend_score=Decimal(str(signal.trend_score)),
        catalyst_score=Decimal(str(signal.catalyst_score)),
        sector=signal.sector,
        rule_version=request.rule_version,
        source_strategies=signal.source_strategies,
        executable_status=status,
        rejected_reasons=rejected_reasons,
        evidence_refs=(evidence_id,),
        as_of=request.now,
        source=SOURCE,
        data_status=DataStatus.VALID,
    )


def _valid_until(request: SelectionRequest) -> datetime:
    value = datetime.combine(request.trading_date, time(15, 0), tzinfo=request.now.tzinfo)
    return value if value > request.now else request.now + timedelta(days=1)


def _plan(
    signal: CandidateSignal,
    request: SelectionRequest,
    draft: TradePlanDraft,
    candidate_id: str,
    evidence_refs: tuple[str, ...],
    *,
    actionable: bool,
) -> TradePlanV2:
    assert draft.trigger_price is not None
    assert draft.entry_ceiling is not None
    assert draft.invalidation_price is not None
    assert draft.first_reduce_price is not None
    risk_distance = draft.trigger_price - draft.invalidation_price
    status = SignalStatus.WAIT_ENTRY if actionable else SignalStatus.NO_TRADE
    return TradePlanV2(
        plan_id=deterministic_id(
            "plan", request.analysis_date, signal.code, signal.candidate_type, request.rule_version
        ),
        candidate_id=candidate_id,
        analysis_date=request.analysis_date,
        trading_date=request.trading_date,
        code=signal.code,
        status=status,
        trigger_price=Decimal(str(draft.trigger_price)),
        entry_ceiling=Decimal(str(draft.entry_ceiling)),
        invalidation_price=Decimal(str(draft.invalidation_price)),
        first_reduce_price=Decimal(str(draft.first_reduce_price)),
        risk_distance=Decimal(str(risk_distance)),
        risk_reward_ratio=Decimal(str(draft.indicators["risk_reward_ratio"])),
        atr=Decimal(str(draft.indicators["atr14"])),
        chip_trade_date=request.analysis_date,
        maximum_shares=draft.maximum_shares,
        market_status=request.market_state.status,
        portfolio_status="APPROVED" if actionable else "NOT_APPROVED",
        valid_until=_valid_until(request),
        rule_version=request.rule_version,
        evidence_refs=evidence_refs,
        as_of=request.now,
        source=SOURCE,
        data_status=DataStatus.VALID,
    )


def _latest_chip(
    code: str,
    request: SelectionRequest,
    dependencies: SelectionDependencies,
) -> EvidenceSnapshot | None:
    snapshot = dependencies.evidence_repository.get_latest_valid_snapshot(code, "chip")
    if is_chip_snapshot_for_trade_date(snapshot, request.analysis_date):
        return snapshot
    dependencies.refresh_chip(code, request.analysis_date)
    snapshot = dependencies.evidence_repository.get_latest_valid_snapshot(code, "chip")
    return snapshot if is_chip_snapshot_for_trade_date(snapshot, request.analysis_date) else None


def materialize_short_term_selection(
    result: SelectionResult,
    dependencies: SelectionDependencies,
    request: SelectionRequest,
) -> SelectionReport:
    if result.analysis_date != request.analysis_date:
        raise ValueError("筛选结果日期与请求分析日期不一致")
    if request.now.tzinfo is None or request.now.utcoffset() is None:
        raise ValueError("now 必须包含时区")

    rejection_counts = Counter(item.reason for item in result.rejected)
    items: list[SelectionItem] = []
    executable_count = 0
    for signal in result.candidates:
        try:
            bars = dependencies.load_daily_bars(signal.code, request.analysis_date)
            technical = _technical_snapshot(signal, bars, request)
            dependencies.evidence_repository.save_snapshot(technical)
            candidate = _candidate(signal, request, technical.snapshot_id, "OBSERVE")
            dependencies.planning_repository.upsert_candidate(candidate)

            chip = _latest_chip(signal.code, request, dependencies)
            if chip is None:
                reason = "缺少分析日有效筹码快照，保留观察但不生成交易计划"
                candidate = _candidate(
                    signal, request, technical.snapshot_id, "OBSERVE", ("CHIP_MISSING",)
                )
                dependencies.planning_repository.upsert_candidate(candidate)
                items.append(
                    SelectionItem(
                        signal.code, signal.name, signal.candidate_type, signal.setup_score,
                        signal.source_strategies, signal.reasons, "OBSERVE", reason, None,
                    )
                )
                rejection_counts["CHIP_MISSING"] += 1
                continue

            strict_limited = (
                request.rule_version == "short-term-selection-2.1.0"
                and request.market_state.status == "LIMITED"
            )
            limited_out = (
                request.market_state.status == "LIMITED"
                and not strict_limited
                and executable_count >= 2
            )
            actionable = (
                request.market_state.status != "FREEZE"
                and request.portfolio_approved
                and not strict_limited
                and not limited_out
            )
            draft = build_eod_trade_plan(
                signal.code,
                bars,
                chip,
                profile=request.risk_profile,
                now=request.now,
                expected_trade_date=request.analysis_date,
                candidate_type=signal.candidate_type,
                market_status=request.market_state.status,
                portfolio_approved=actionable,
            )
            if draft.status != "WAIT_ENTRY":
                reason = draft.reason
                candidate = _candidate(
                    signal, request, technical.snapshot_id, "OBSERVE", ("PLAN_REJECTED",)
                )
                dependencies.planning_repository.upsert_candidate(candidate)
                items.append(
                    SelectionItem(
                        signal.code, signal.name, signal.candidate_type, signal.setup_score,
                        signal.source_strategies, signal.reasons, "OBSERVE", reason, None,
                    )
                )
                rejection_counts["PLAN_REJECTED"] += 1
                continue

            if request.market_state.status == "FREEZE":
                reason = "市场状态为 FREEZE，仅保留零股观察计划"
            elif strict_limited:
                reason = "2.1 严格规则在 LIMITED 市场仅保留观察计划"
            elif limited_out:
                reason = "市场状态为 LIMITED，可执行候选已达到 2 只上限"
            elif not request.portfolio_approved:
                reason = "组合或账户数据未批准，暂不确定最大股数"
            else:
                reason = "候选、筹码、市场与组合风控均已通过"
            plan = _plan(
                signal,
                request,
                draft,
                candidate.candidate_id,
                (technical.snapshot_id, chip.snapshot_id),
                actionable=actionable,
            )
            dependencies.planning_repository.upsert_plan(plan)
            status: Literal["OBSERVE", "EXECUTABLE"] = "EXECUTABLE" if actionable else "OBSERVE"
            candidate = _candidate(
                signal,
                request,
                technical.snapshot_id,
                status,
                () if actionable else ("RISK_NOT_APPROVED",),
            )
            dependencies.planning_repository.upsert_candidate(candidate)
            if actionable:
                executable_count += 1
            items.append(
                SelectionItem(
                    signal.code, signal.name, signal.candidate_type, signal.setup_score,
                    signal.source_strategies, signal.reasons, status, reason, plan,
                )
            )
        except Exception:
            rejection_counts["PLAN_ERROR"] += 1

    return SelectionReport(
        analysis_date=request.analysis_date,
        trading_date=request.trading_date,
        market_status=str(request.market_state.status),
        market_reasons=request.market_state.reasons,
        items=tuple(items),
        rejection_counts=dict(sorted(rejection_counts.items())),
        rule_version=request.rule_version,
    )


def _price(value: Decimal) -> str:
    return f"{value:.2f}"


def render_selection_report(report: SelectionReport) -> str:
    lines = [
        f"短线自动选股｜分析数据日：{report.analysis_date.isoformat()}｜适用交易日：{report.trading_date.isoformat()}",
        f"规则版本：{report.rule_version}",
        f"市场状态：{report.market_status}（{'；'.join(report.market_reasons) or '无补充说明'}）",
    ]
    if not report.items:
        lines.append("没有满足完整数据与风控要求的候选。")
    for index, item in enumerate(report.items, 1):
        shape = "突破" if item.candidate_type == "BREAKOUT" else "回踩"
        lines.extend(
            (
                f"{index}. {item.name}（{item.code}）｜{shape}｜{item.status}｜得分 {item.setup_score:.1f}",
                f"   来源：{'+'.join(item.source_strategies)}｜理由：{'；'.join(item.reasons)}",
                f"   结论：{item.reason}",
            )
        )
        if item.plan is not None:
            plan = item.plan
            lines.append(
                "   触发价 {trigger}｜入场上限 {ceiling}｜失效价 {invalid}｜第一减仓价 {reduce}".format(
                    trigger=_price(plan.trigger_price),
                    ceiling=_price(plan.entry_ceiling),
                    invalid=_price(plan.invalidation_price),
                    reduce=_price(plan.first_reduce_price),
                )
            )
            shares = "待组合风控批准" if plan.maximum_shares is None else str(plan.maximum_shares)
            lines.append(f"   最大股数：{shares}")
    if report.rejection_counts:
        summary = "，".join(f"{reason}：{count}" for reason, count in report.rejection_counts.items())
        lines.append(f"淘汰/降级统计：{summary}")
    lines.append("这是交易计划，不代表已经下单。")
    return "\n".join(lines)
