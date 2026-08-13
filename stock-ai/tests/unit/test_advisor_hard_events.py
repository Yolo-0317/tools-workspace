from __future__ import annotations

from stock_ai.advisor_memory.hard_events import HardEventInputs, detect_hard_events
from stock_ai.advisor_memory.models import HardEventKind


def test_small_daily_move_is_not_a_hard_event() -> None:
    events = detect_hard_events(
        HardEventInputs(price=10.05, previous_price=10.0)
    )

    assert events == ()


def test_stop_loss_is_a_price_hard_event() -> None:
    events = detect_hard_events(
        HardEventInputs(
            price=9.49,
            previous_price=9.60,
            stop_loss=9.50,
            observed_at="2026-08-13T10:00:00+08:00",
        )
    )

    assert events[0].kind is HardEventKind.PRICE_TRIGGER
    assert events[0].suggested_action == "退出观察"
    assert events[0].evidence["trigger"] == "stop_loss"


def test_position_close_is_a_hard_event() -> None:
    events = detect_hard_events(
        HardEventInputs(shares_before=500, shares_after=0)
    )

    assert events[0].kind is HardEventKind.POSITION_CHANGE
    assert events[0].suggested_action == "已清仓"


def test_position_increase_requires_reassessment() -> None:
    events = detect_hard_events(
        HardEventInputs(shares_before=500, shares_after=700)
    )

    assert events[0].kind is HardEventKind.POSITION_CHANGE
    assert events[0].suggested_action == "仓位已变，重新评估"


def test_trend_breakdown_is_a_hard_event() -> None:
    events = detect_hard_events(HardEventInputs(trend_breakdown=True))

    assert events[0].kind is HardEventKind.TREND_STRUCTURE
    assert events[0].suggested_action == "降级观察"


def test_effective_breakout_is_a_hard_event() -> None:
    events = detect_hard_events(HardEventInputs(effective_breakout=True))

    assert events[0].kind is HardEventKind.TREND_STRUCTURE
    assert events[0].suggested_action == "升级观察"


def test_material_risk_is_a_hard_event() -> None:
    events = detect_hard_events(
        HardEventInputs(
            material_risk=True,
            material_risk_reasons=("监管立案",),
        )
    )

    assert events[0].kind is HardEventKind.COMPANY_EVENT
    assert events[0].suggested_action == "风险退出"
    assert events[0].evidence["reasons"] == ("监管立案",)


def test_sector_reversal_is_a_hard_event() -> None:
    events = detect_hard_events(HardEventInputs(sector_reversal=True))

    assert events[0].kind is HardEventKind.MARKET_SECTOR_REVERSAL
    assert events[0].suggested_action == "降级观察"


def test_target_hit_is_a_price_hard_event() -> None:
    events = detect_hard_events(
        HardEventInputs(price=11.02, previous_price=10.95, target_price=11.0)
    )

    assert events[0].suggested_action == "分批止盈"
    assert events[0].evidence["trigger"] == "target_price"


def test_price_remaining_above_pressure_does_not_repeat_hard_event() -> None:
    events = detect_hard_events(
        HardEventInputs(price=11.2, previous_price=11.1, pressure_price=11.0)
    )

    assert events == ()
