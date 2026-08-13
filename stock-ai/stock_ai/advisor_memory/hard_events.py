from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import HardEvent, HardEventKind


@dataclass(frozen=True)
class HardEventInputs:
    price: float | None = None
    previous_price: float | None = None
    stop_loss: float | None = None
    target_price: float | None = None
    support_price: float | None = None
    pressure_price: float | None = None
    shares_before: int | None = None
    shares_after: int | None = None
    trend_breakdown: bool = False
    effective_breakout: bool = False
    material_risk: bool = False
    material_risk_reasons: tuple[str, ...] = ()
    market_reversal: bool = False
    sector_reversal: bool = False
    observed_at: datetime | str | None = None


def _observed_at(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime) or value is None:
        return value
    return datetime.fromisoformat(value)


def _event(
    kind: HardEventKind,
    action: str,
    evidence: dict,
    source: str,
    observed_at: datetime | None,
) -> HardEvent:
    return HardEvent(
        kind=kind,
        suggested_action=action,
        evidence=evidence,
        source=source,
        observed_at=observed_at,
    )


def detect_hard_events(inputs: HardEventInputs) -> tuple[HardEvent, ...]:
    """Detect only the five approved hard-event classes from structured facts."""
    observed_at = _observed_at(inputs.observed_at)
    events: list[HardEvent] = []

    if inputs.price is not None:
        def crossed_down(threshold: float) -> bool:
            return (
                inputs.previous_price is None or inputs.previous_price > threshold
            ) and inputs.price <= threshold

        def crossed_up(threshold: float) -> bool:
            return (
                inputs.previous_price is None or inputs.previous_price < threshold
            ) and inputs.price >= threshold
        if inputs.stop_loss is not None and crossed_down(inputs.stop_loss):
            events.append(
                _event(
                    HardEventKind.PRICE_TRIGGER,
                    "退出观察",
                    {
                        "trigger": "stop_loss",
                        "price": inputs.price,
                        "threshold": inputs.stop_loss,
                    },
                    "price_rule",
                    observed_at,
                )
            )
        elif inputs.target_price is not None and crossed_up(inputs.target_price):
            events.append(
                _event(
                    HardEventKind.PRICE_TRIGGER,
                    "分批止盈",
                    {
                        "trigger": "target_price",
                        "price": inputs.price,
                        "threshold": inputs.target_price,
                    },
                    "price_rule",
                    observed_at,
                )
            )
        elif inputs.support_price is not None and crossed_down(inputs.support_price):
            events.append(
                _event(
                    HardEventKind.PRICE_TRIGGER,
                    "降级观察",
                    {
                        "trigger": "support_broken",
                        "price": inputs.price,
                        "threshold": inputs.support_price,
                    },
                    "price_rule",
                    observed_at,
                )
            )
        elif inputs.pressure_price is not None and crossed_up(inputs.pressure_price):
            events.append(
                _event(
                    HardEventKind.PRICE_TRIGGER,
                    "升级观察",
                    {
                        "trigger": "pressure_broken",
                        "price": inputs.price,
                        "threshold": inputs.pressure_price,
                    },
                    "price_rule",
                    observed_at,
                )
            )

    if (
        inputs.shares_before is not None
        and inputs.shares_after is not None
        and inputs.shares_before != inputs.shares_after
    ):
        action = "已清仓" if inputs.shares_before > 0 and inputs.shares_after == 0 else "仓位已变，重新评估"
        events.append(
            _event(
                HardEventKind.POSITION_CHANGE,
                action,
                {
                    "shares_before": inputs.shares_before,
                    "shares_after": inputs.shares_after,
                    "shares_delta": inputs.shares_after - inputs.shares_before,
                },
                "broker_position",
                observed_at,
            )
        )

    if inputs.trend_breakdown:
        events.append(
            _event(
                HardEventKind.TREND_STRUCTURE,
                "降级观察",
                {"signal": "trend_breakdown"},
                "technical_structure",
                observed_at,
            )
        )
    elif inputs.effective_breakout:
        events.append(
            _event(
                HardEventKind.TREND_STRUCTURE,
                "升级观察",
                {"signal": "effective_breakout"},
                "technical_structure",
                observed_at,
            )
        )

    if inputs.material_risk:
        events.append(
            _event(
                HardEventKind.COMPANY_EVENT,
                "风险退出",
                {"reasons": inputs.material_risk_reasons},
                "news_impact",
                observed_at,
            )
        )

    if inputs.market_reversal or inputs.sector_reversal:
        events.append(
            _event(
                HardEventKind.MARKET_SECTOR_REVERSAL,
                "降级观察",
                {
                    "market_reversal": inputs.market_reversal,
                    "sector_reversal": inputs.sector_reversal,
                },
                "market_regime",
                observed_at,
            )
        )

    return tuple(events)
