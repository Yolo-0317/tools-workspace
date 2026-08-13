from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Mapping, Sequence

from .models import CycleStatus, DecisionCycle, HardEvent
from .state_machine import advance_cycle, resolve_cycle_dates


@dataclass(frozen=True)
class DiagnosisDecision:
    cycle_id: int | str
    cycle_day: int
    next_review_date: date | None
    expiry_date: date
    previous_action: str
    locked_action: str
    relation: str
    status: CycleStatus
    hard_events: tuple[HardEvent, ...]
    allowed_actions: tuple[str, ...]
    trigger_plan: Mapping[str, Any]


def _cycle_day(cycle: DecisionCycle, as_of: date, trading_days: Sequence[date]) -> int:
    elapsed = [
        day
        for day in trading_days
        if cycle.started_trade_date <= day <= as_of
    ]
    return max(1, min(5, len(elapsed)))


def prepare_diagnosis(
    code: str,
    *,
    name: str,
    as_of: date,
    trading_days: Sequence[date],
    hard_events: Sequence[HardEvent],
    repository,
    initial_action: str = "持有观察",
    extend_at_review: bool = True,
    trigger_plan: Mapping[str, Any] | None = None,
) -> DiagnosisDecision:
    """Resolve the action before AI analysis and persist the transition."""
    cycle = repository.load_active_cycle_model(str(code).zfill(6))
    if cycle is None:
        review, expiry = resolve_cycle_dates(as_of, trading_days)
        cycle = repository.open_cycle(
            code=str(code).zfill(6),
            name=name,
            started_trade_date=as_of,
            review_trade_date=review,
            expiry_trade_date=expiry,
            initial_action=initial_action,
            current_action=initial_action,
            trigger_plan=trigger_plan,
        )
        return DiagnosisDecision(
            cycle_id=cycle.cycle_id,
            cycle_day=1,
            next_review_date=review,
            expiry_date=expiry,
            previous_action=initial_action,
            locked_action=initial_action,
            relation="新周期",
            status=CycleStatus.ACTIVE,
            hard_events=tuple(hard_events),
            allowed_actions=(initial_action,),
            trigger_plan=dict(trigger_plan or {}),
        )

    resolved_plan = dict(cycle.trigger_plan or {})
    if not resolved_plan and trigger_plan:
        resolved_plan = dict(trigger_plan)
        attach = getattr(repository, "attach_trigger_plan", None)
        if callable(attach):
            attach(
                cycle,
                resolved_plan,
                as_of=as_of,
                observed_at=datetime.combine(as_of, time(15, 0)),
            )

    transition = advance_cycle(
        cycle,
        as_of=as_of,
        hard_events=hard_events,
        extend_at_review=extend_at_review,
    )
    repository.record_transition(
        cycle,
        transition,
        as_of=as_of,
        observed_at=datetime.combine(as_of, time(15, 0)),
    )
    next_review = None
    if transition.status in (CycleStatus.ACTIVE, CycleStatus.REVIEW_DUE):
        next_review = cycle.review_trade_date
    elif transition.status is CycleStatus.EXTENDED:
        next_review = cycle.expiry_trade_date
    return DiagnosisDecision(
        cycle_id=cycle.cycle_id,
        cycle_day=_cycle_day(cycle, as_of, trading_days),
        next_review_date=next_review,
        expiry_date=cycle.expiry_trade_date,
        previous_action=cycle.current_action,
        locked_action=transition.action,
        relation=transition.relation,
        status=transition.status,
        hard_events=tuple(hard_events),
        allowed_actions=(transition.action,),
        trigger_plan=resolved_plan,
    )


def format_memory_context(decision: DiagnosisDecision) -> str:
    from .trade_plan import format_trade_plan
    review = decision.next_review_date.isoformat() if decision.next_review_date else "周期已结束"
    hard_event = "无" if not decision.hard_events else "；".join(
        f"{item.kind.value}:{item.suggested_action}" for item in decision.hard_events
    )
    memory = "\n".join(
        [
            "## 决策记忆与状态机约束",
            f"- 当前周期第{decision.cycle_day}/5日",
            f"- 上次决策：{decision.previous_action}",
            f"- 锁定动作：{decision.locked_action}",
            f"- 本次关系：{decision.relation}",
            f"- 硬事件：{hard_event}",
            f"- 下次复核日：{review}",
            f"- 允许动作：{'、'.join(decision.allowed_actions)}",
            "- AI 只能解释新增证据，不得提出锁定集合之外的动作。",
        ]
    )
    return memory + "\n" + format_trade_plan(decision.trigger_plan)


def enforce_locked_action(
    ai_text: str,
    decision: DiagnosisDecision,
) -> tuple[str, bool]:
    """Replace an AI-authored operation line with the deterministic action."""
    rejected = False
    kept: list[str] = []
    protected_prefixes = (
        "操作建议", "建议动作", "决策", "仓位计划", "强势触发",
        "入场触发", "失效条件", "追高纪律", "周期纪律",
    )
    for line in str(ai_text or "").splitlines():
        compact = line.strip().lstrip("#*- ").strip()
        if compact.startswith(protected_prefixes):
            if decision.locked_action not in compact:
                rejected = True
            continue
        kept.append(line)
    header = f"操作建议：{decision.locked_action}（{decision.relation}）"
    from .trade_plan import format_trade_plan

    plan = format_trade_plan(decision.trigger_plan)
    body = "\n".join(kept).strip()
    fixed = f"{header}\n{plan}"
    return (f"{fixed}\n{body}" if body else fixed), rejected
