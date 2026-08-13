from __future__ import annotations

from datetime import date

from stock_ai.advisor_memory.trade_plan import build_trade_plan, format_trade_plan


def _bars():
    return [
        {"trade_date": date(2026, 8, day), "high": high, "low": low, "close": close, "amount": amount}
        for day, high, low, close, amount in (
            (6, 10.3, 9.8, 10.1, 100),
            (7, 10.5, 10.0, 10.3, 110),
            (10, 10.6, 10.1, 10.4, 105),
            (11, 10.7, 10.2, 10.5, 100),
            (12, 10.65, 10.3, 10.55, 95),
        )
    ]


def test_hold_plan_freezes_position_and_exposes_hard_triggers() -> None:
    plan = build_trade_plan("持有观察", current_price=10.55, bars=_bars())

    assert plan["horizon"] == "3-5个交易日"
    assert "维持现有股数" in plan["position_plan"]
    assert plan["strength_trigger_price"] == 10.7
    assert plan["defense_trigger_price"] == 9.8
    assert "超过5%不追" in plan["chase_discipline"]


def test_trade_plan_is_rendered_as_deterministic_block() -> None:
    block = format_trade_plan(build_trade_plan("持有观察", current_price=10.55, bars=_bars()))

    assert "【3-5交易日执行计划】" in block
    assert "未触发五类硬事件，不改变锁定动作" in block
