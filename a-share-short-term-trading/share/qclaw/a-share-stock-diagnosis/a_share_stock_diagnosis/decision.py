"""Deterministic entry and manual-holding guidance."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import math
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from .chip import calculate_chip_metrics
from .indicators import calculate_indicators
from .models import (
    ChipMetrics,
    DailyBar,
    DiagnosisResult,
    HoldingInput,
    Quote,
    Security,
    SessionContext,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
CYQ_WARNING = "筹码为成交与换手衰减模型估算，不是真实持仓成本。"


def _ceil_cent(value: float) -> float:
    return math.ceil((value - 1e-9) * 100) / 100


def _floor_cent(value: float) -> float:
    return math.floor((value + 1e-9) * 100) / 100


def round_sell_quantity(requested: int, available: int) -> int:
    if requested <= 0 or available <= 0:
        return 0
    return (min(requested, available) // 100) * 100


def build_entry_levels(
    indicators: Mapping[str, float],
    chip: ChipMetrics,
) -> dict[str, float]:
    atr = float(indicators["atr14"])
    resistance = max(float(indicators["high20"]), chip.cost_90_high)
    trigger = _ceil_cent(resistance + 0.10 * atr)
    entry_ceiling = _ceil_cent(trigger + 0.50 * atr)
    support = max(float(indicators["low10"]), chip.cost_90_low, float(indicators["ma10"]))
    invalidation = _floor_cent(support - 0.10 * atr)
    risk_fraction = (trigger - invalidation) / trigger if trigger > 0 else 0.0
    first_reduce = _ceil_cent(trigger + 2.0 * (trigger - invalidation))
    return {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "trigger": trigger,
        "entry_ceiling": entry_ceiling,
        "invalidation": invalidation,
        "first_reduce": first_reduce,
        "risk_fraction": risk_fraction,
    }


def _holding_payload(
    holding: HoldingInput,
    price: float | None,
    suggested_sell: int | None,
) -> dict[str, float | int | None]:
    pnl = None if price is None else round((price - holding.cost_price) * holding.shares, 2)
    pnl_pct = None if price is None else round((price / holding.cost_price - 1.0) * 100.0, 4)
    return {
        "shares": holding.shares,
        "cost_price": holding.cost_price,
        "available_shares": holding.available_shares,
        "market_price": price,
        "market_value": None if price is None else round(price * holding.shares, 2),
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "suggested_sell_shares": suggested_sell,
    }


def _failed_result(
    security: Security,
    context: SessionContext,
    as_of: datetime,
    reason: str,
    holding: HoldingInput | None,
    *,
    decision: str | None = None,
    error_code: str = "DATA_UNAVAILABLE",
) -> DiagnosisResult:
    selected = decision or ("OBSERVE" if holding is not None else "NO_TRADE")
    return DiagnosisResult(
        schema_version="1.0",
        symbol=security.code,
        name=security.name,
        session=context.session,
        as_of=as_of,
        diagnosis_trade_date=context.diagnosis_trade_date,
        data_freshness="unavailable",
        quote=None,
        latest_bar=None,
        indicators={},
        chip_estimate=None,
        decision=selected,
        actionable=False,
        reason=reason,
        next_action="补齐有效数据后重新诊断",
        levels={},
        holding=None if holding is None else _holding_payload(holding, None, None),
        warnings=[CYQ_WARNING],
        source_refs={},
        errors=[{"code": error_code, "message": reason}],
    )


def _quote_is_fresh(quote: Quote, security: Security, as_of: datetime) -> bool:
    if quote.code != security.code:
        return False
    local_quote = quote.as_of.astimezone(SHANGHAI)
    local_now = as_of.astimezone(SHANGHAI)
    return (
        local_quote.date() == local_now.date()
        and abs((local_now - local_quote).total_seconds()) <= 15 * 60
    )


def diagnose(
    security: Security,
    context: SessionContext,
    bars: Sequence[DailyBar],
    quote: Quote | None,
    holding: HoldingInput | None,
    *,
    as_of: datetime,
) -> DiagnosisResult:
    if not context.calendar_confirmed or context.diagnosis_trade_date is None:
        return _failed_result(
            security,
            context,
            as_of,
            "交易日历未确认，未生成交易结论",
            holding,
            error_code="CALENDAR_UNKNOWN",
        )
    ordered = sorted(bars, key=lambda item: item.trade_date)
    if not ordered:
        return _failed_result(security, context, as_of, "缺少有效日线", holding)
    latest = ordered[-1]
    static_session = context.session in {"PRE_MARKET", "POST_MARKET", "NON_TRADING_DAY"}
    if latest.trade_date > context.diagnosis_trade_date or (
        static_session and latest.trade_date != context.diagnosis_trade_date
    ):
        return _failed_result(
            security,
            context,
            as_of,
            "最近完整日线与目标交易日不一致",
            holding,
            error_code="TRADE_DATE_MISMATCH",
        )
    try:
        indicators = calculate_indicators(ordered)
        chip = calculate_chip_metrics(ordered)
        levels = build_entry_levels(indicators, chip)
    except ValueError as exc:
        return _failed_result(
            security,
            context,
            as_of,
            str(exc),
            holding,
            error_code="CALCULATION_INPUT_INVALID",
        )

    use_realtime = context.session == "INTRADAY" and quote is not None and _quote_is_fresh(
        quote, security, as_of
    )
    usable_price = quote.price if use_realtime and quote is not None else latest.close
    quote_payload = None
    source_refs = {"daily": f"eastmoney-public:daily:{security.code}:{latest.trade_date.isoformat()}"}
    if use_realtime and quote is not None:
        quote_payload = asdict(quote)
        source_refs["quote"] = f"eastmoney-public:quote:{security.code}:{quote.as_of.isoformat()}"
    chip_payload = asdict(chip)
    latest_payload = asdict(latest)
    rounded_indicators = {key: round(value, 4) for key, value in indicators.items()}
    rounded_levels = {key: round(value, 8) for key, value in levels.items()}
    warnings = [CYQ_WARNING]

    if holding is None:
        risk_fraction = levels["risk_fraction"]
        if not 0.015 <= risk_fraction <= 0.05:
            decision = "NO_TRADE"
            reason = "触发价到失效价风险距离不在 1.5%–5.0%"
            next_action = "等待风险距离收敛后重新诊断"
        else:
            decision = "WAIT_ENTRY"
            reason = "价格计划已生成，但共享版不生成可执行交易许可"
            next_action = "仅观察触发条件，不追涨，不自动下单"
        return DiagnosisResult(
            "1.0",
            security.code,
            security.name,
            context.session,
            as_of,
            latest.trade_date,
            "realtime" if use_realtime else "completed_close",
            quote_payload,
            latest_payload,
            rounded_indicators,
            chip_payload,
            decision,
            False,
            reason,
            next_action,
            rounded_levels,
            None,
            warnings,
            source_refs,
            [],
        )

    if context.session == "INTRADAY" and not use_realtime:
        return DiagnosisResult(
            "1.0",
            security.code,
            security.name,
            context.session,
            as_of,
            latest.trade_date,
            "completed_close_non_realtime",
            None,
            latest_payload,
            rounded_indicators,
            chip_payload,
            "OBSERVE",
            False,
            "盘中实时行情缺失，持仓指导已降级",
            "恢复实时行情后重新诊断",
            rounded_levels,
            _holding_payload(holding, latest.close, None),
            warnings + ["当前价格为最近完整收盘价，不是实时价格。"],
            source_refs,
            [{"code": "QUOTE_UNAVAILABLE", "message": "盘中实时行情不可用"}],
        )

    suggested_sell: int | None = 0
    if usable_price <= levels["invalidation"]:
        desired_decision = "EXIT"
        requested = holding.available_shares or 0
        reason = "价格已到或跌破失效价"
    elif usable_price < levels["support"] or usable_price >= levels["first_reduce"]:
        desired_decision = "REDUCE"
        requested = 0 if holding.available_shares is None else holding.available_shares // 2
        reason = "价格跌破支撑或达到第一减仓目标"
    else:
        desired_decision = "HOLD"
        requested = 0
        reason = "价格仍在防守位之上，未达到减仓条件"

    if desired_decision in {"REDUCE", "EXIT"} and holding.available_shares is None:
        decision = "OBSERVE"
        suggested_sell = None
        next_action = "先在券商确认当前可卖股数"
    elif desired_decision in {"REDUCE", "EXIT"} and holding.available_shares == 0:
        decision = "OBSERVE"
        suggested_sell = 0
        next_action = "当前无可卖股数，下一交易日重新确认 T+1 可卖数量"
        warnings.append("当前可卖股数为 0，不得生成当日卖出数量。")
    else:
        decision = desired_decision
        suggested_sell = round_sell_quantity(requested, holding.available_shares or 0)
        next_action = {
            "HOLD": "继续持有并执行失效价防守",
            "REDUCE": "仅在条件保持成立时考虑减少对应可卖股数",
            "EXIT": "失效条件已成立，优先控制风险",
        }[decision]

    return DiagnosisResult(
        "1.0",
        security.code,
        security.name,
        context.session,
        as_of,
        latest.trade_date,
        "realtime" if use_realtime else "completed_close",
        quote_payload,
        latest_payload,
        rounded_indicators,
        chip_payload,
        decision,
        False,
        reason,
        next_action,
        rounded_levels,
        _holding_payload(holding, usable_price, suggested_sell),
        warnings,
        source_refs,
        [],
    )
