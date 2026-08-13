"""Deterministic 3-5 session execution plans for advisor decision cycles."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _number(row: Mapping[str, Any], key: str) -> float | None:
    try:
        value = row.get(key)
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_trade_plan(
    locked_action: str,
    *,
    current_price: float | None,
    bars: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    recent = list(bars)[-5:]
    highs = [value for row in recent if (value := _number(row, "high")) is not None]
    lows = [value for row in recent if (value := _number(row, "low")) is not None]
    strength = round(max(highs), 2) if highs else None
    defense = round(min(lows), 2) if lows else None
    action = str(locked_action or "持有观察").strip() or "持有观察"
    if "已清仓" in action:
        position_plan = "维持0股；等待新决策周期，禁止当天反向重开"
    elif "清仓" in action:
        position_plan = "达到锁定条件后全部退出；普通波动不撤销计划"
    elif "减" in action:
        position_plan = "按锁定减仓计划执行；减后不因普通反弹立即加回"
    else:
        position_plan = "维持现有股数；未触发五类硬事件不加减仓"
    return {
        "horizon": "3-5个交易日",
        "locked_action": action,
        "position_plan": position_plan,
        "strength_trigger_price": strength,
        "defense_trigger_price": defense,
        "strength_trigger": (
            f"收盘放量站上{strength:.2f}，仅触发复核，不自动追买"
            if strength is not None
            else "放量突破近期压力时触发复核，不自动追买"
        ),
        "invalidation": (
            f"收盘跌破{defense:.2f}或出现放量破位，触发防守复核"
            if defense is not None
            else "趋势结构放量破位时触发防守复核"
        ),
        "chase_discipline": "单日涨幅超过5%不追；未回踩确认不新增风险",
        "current_price_at_open": float(current_price) if current_price is not None else None,
        "ordinary_day_rule": "未触发五类硬事件，不改变锁定动作",
    }


def format_trade_plan(plan: Mapping[str, Any] | None) -> str:
    if not plan:
        return "【3-5交易日执行计划】\n- 历史周期尚未补齐触发计划；动作锁定仍然有效。"
    return "\n".join(
        [
            "【3-5交易日执行计划】",
            f"- 仓位计划：{plan.get('position_plan', '维持锁定动作')}",
            f"- 强势触发：{plan.get('strength_trigger', '仅在硬事件出现时复核')}",
            f"- 失效条件：{plan.get('invalidation', '趋势结构实变时复核')}",
            f"- 追高纪律：{plan.get('chase_discipline', '不追高')}",
            f"- 周期纪律：{plan.get('ordinary_day_rule', '未触发五类硬事件，不改变锁定动作')}",
        ]
    )
