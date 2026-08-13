from __future__ import annotations

from datetime import date

from stock_ai.advisor_memory.diagnosis import (
    enforce_locked_action,
    format_memory_context,
    prepare_diagnosis,
)
from stock_ai.advisor_memory.models import CycleStatus, DecisionCycle, HardEvent, HardEventKind


DAYS = tuple(date(2026, 8, day) for day in (10, 11, 12, 13, 14, 17))


class MemoryRepository:
    def __init__(self, cycle=None):
        self.cycle = cycle
        self.opened = []
        self.transitions = []

    def load_active_cycle_model(self, code):
        return self.cycle

    def open_cycle(self, **kwargs):
        self.opened.append(kwargs)
        self.cycle = DecisionCycle(cycle_id=7, status=CycleStatus.ACTIVE, **kwargs)
        return self.cycle

    def record_transition(self, cycle, transition, **kwargs):
        self.transitions.append((cycle, transition, kwargs))


def active_cycle() -> DecisionCycle:
    return DecisionCycle(
        cycle_id=1,
        code="600000",
        name="测试股份",
        started_trade_date=DAYS[0],
        review_trade_date=DAYS[2],
        expiry_trade_date=DAYS[4],
        initial_action="持有观察",
        current_action="持有观察",
        status=CycleStatus.ACTIVE,
        trigger_plan={"horizon": "3-5个交易日", "position_plan": "维持现有股数"},
    )


def test_diagnosis_keeps_action_without_hard_event() -> None:
    repository = MemoryRepository(active_cycle())

    decision = prepare_diagnosis(
        "600000",
        name="测试股份",
        as_of=DAYS[1],
        trading_days=DAYS,
        hard_events=(),
        repository=repository,
    )

    assert decision.locked_action == "持有观察"
    assert decision.previous_action == "持有观察"
    assert decision.relation == "维持"
    assert decision.cycle_day == 2
    assert decision.next_review_date == DAYS[2]


def test_first_diagnosis_opens_three_to_five_day_cycle() -> None:
    repository = MemoryRepository()

    decision = prepare_diagnosis(
        "600000",
        name="测试股份",
        as_of=DAYS[0],
        trading_days=DAYS,
        hard_events=(),
        repository=repository,
        initial_action="持有观察",
        trigger_plan={"horizon": "3-5个交易日", "position_plan": "维持现有股数"},
    )

    assert decision.cycle_day == 1
    assert decision.locked_action == "持有观察"
    assert repository.opened[0]["review_trade_date"] == DAYS[2]
    assert repository.opened[0]["expiry_trade_date"] == DAYS[4]
    assert repository.opened[0]["trigger_plan"]["position_plan"] == "维持现有股数"


def test_position_close_interrupts_cycle_and_locks_closed_action() -> None:
    repository = MemoryRepository(active_cycle())
    event = HardEvent(
        HardEventKind.POSITION_CHANGE,
        "已清仓",
        {"shares_before": 500, "shares_after": 0},
        "jywg",
    )

    decision = prepare_diagnosis(
        "600000",
        name="测试股份",
        as_of=DAYS[1],
        trading_days=DAYS,
        hard_events=(event,),
        repository=repository,
    )

    assert decision.locked_action == "已清仓"
    assert decision.relation == "失效"
    assert decision.hard_events == (event,)


def test_memory_context_exposes_cycle_and_lock() -> None:
    decision = prepare_diagnosis(
        "600000",
        name="测试股份",
        as_of=DAYS[1],
        trading_days=DAYS,
        hard_events=(),
        repository=MemoryRepository(active_cycle()),
    )

    context = format_memory_context(decision)

    assert "当前周期第2/5日" in context
    assert "锁定动作：持有观察" in context
    assert "下次复核日：2026-08-12" in context
    assert "不得提出锁定集合之外的动作" in context


def test_conflicting_ai_action_is_removed() -> None:
    decision = prepare_diagnosis(
        "600000",
        name="测试股份",
        as_of=DAYS[1],
        trading_days=DAYS,
        hard_events=(),
        repository=MemoryRepository(active_cycle()),
    )

    cleaned, rejected = enforce_locked_action(
        "操作建议：立即清仓\n新增证据：量能普通。",
        decision,
    )

    assert rejected is True
    assert "立即清仓" not in cleaned
    assert cleaned.startswith("操作建议：持有观察")
    assert "新增证据" in cleaned


def test_ai_cannot_replace_stored_trigger_plan() -> None:
    decision = prepare_diagnosis(
        "600000",
        name="测试股份",
        as_of=DAYS[1],
        trading_days=DAYS,
        hard_events=(),
        repository=MemoryRepository(active_cycle()),
    )

    cleaned, rejected = enforce_locked_action(
        "仓位计划：立刻满仓\n失效条件：永不止损\n新增证据：量能温和。",
        decision,
    )

    assert rejected is True
    assert "立刻满仓" not in cleaned
    assert "永不止损" not in cleaned
    assert "维持现有股数" in cleaned
