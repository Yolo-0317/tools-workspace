"""Intraday verification of a frozen end-of-day trade plan."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from short_term_trading.diagnosis import TradePlanDraft
from short_term_trading.evidence import EvidenceSnapshot, is_fresh


@dataclass(frozen=True)
class IntradayRiskGate:
    market_status: Literal["ALLOW", "LIMITED", "FREEZE"]
    portfolio_approved: bool
    maximum_shares: int
    reason: str = ""


@dataclass(frozen=True)
class IntradayDecision:
    code: str
    status: Literal["NO_TRADE", "WAIT_ENTRY", "BUY_ALLOWED", "EXIT"]
    reason: str
    as_of: str
    maximum_shares: int
    passed_gates: list[str]
    failed_gates: list[str]
    evidence_refs: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _decision(
    plan: TradePlanDraft,
    now: datetime,
    status: Literal["NO_TRADE", "WAIT_ENTRY", "BUY_ALLOWED", "EXIT"],
    reason: str,
    *,
    passed: list[str] | None = None,
    failed: list[str] | None = None,
    refs: dict[str, str] | None = None,
    maximum_shares: int = 0,
) -> IntradayDecision:
    return IntradayDecision(
        code=plan.code,
        status=status,
        reason=reason,
        as_of=now.isoformat(),
        maximum_shares=maximum_shares,
        passed_gates=passed or [],
        failed_gates=failed or [],
        evidence_refs=refs or {},
    )


def _fresh(snapshot: EvidenceSnapshot | None, expected_kind: str, now: datetime) -> bool:
    return snapshot is not None and snapshot.kind == expected_kind and is_fresh(snapshot, now)


def _order_book_passes(snapshots: list[EvidenceSnapshot], now: datetime) -> bool:
    valid = [snapshot for snapshot in snapshots if _fresh(snapshot, "order_book", now)]
    if len(valid) < 3:
        return False
    latest_three = valid[-3:]
    intervals = [
        (later.as_of - earlier.as_of).total_seconds()
        for earlier, later in zip(latest_three, latest_three[1:])
    ]
    if any(interval < 60 for interval in intervals):
        return False
    passes = 0
    for snapshot in latest_three:
        bids = sum(float(snapshot.data[f"bid_{index}"]) for index in range(1, 6))
        asks = sum(float(snapshot.data[f"ask_{index}"]) for index in range(1, 6))
        if asks > 0 and bids / asks >= 1.2:
            passes += 1
    return passes >= 2


def verify_intraday_plan(
    plan: TradePlanDraft,
    *,
    quote: EvidenceSnapshot | None,
    fund_flow: EvidenceSnapshot | None,
    sector: EvidenceSnapshot | None,
    chip: EvidenceSnapshot | None,
    order_books: list[EvidenceSnapshot],
    risk_gate: IntradayRiskGate,
    now: datetime,
    is_holding: bool = False,
) -> IntradayDecision:
    if plan.status != "WAIT_ENTRY" or plan.trigger_price is None or plan.entry_ceiling is None or plan.invalidation_price is None:
        return _decision(plan, now, "NO_TRADE", "没有可验证的收盘价格计划", failed=["plan"])
    if not _fresh(quote, "quote", now):
        return _decision(plan, now, "NO_TRADE", "报价快照缺失或过期", failed=["quote"])
    price = float(quote.data["price"])
    if is_holding and price <= plan.invalidation_price:
        return _decision(plan, now, "EXIT", "现价跌破硬失效价", passed=["quote"], refs={"quote": quote.raw_evidence_ref})
    if risk_gate.market_status == "FREEZE":
        return _decision(plan, now, "NO_TRADE", "市场状态为 FREEZE", failed=["market"])
    if not risk_gate.portfolio_approved or risk_gate.maximum_shares <= 0:
        return _decision(plan, now, "NO_TRADE", risk_gate.reason or "组合风控未放行", failed=["portfolio"])
    if price < plan.trigger_price:
        return _decision(plan, now, "WAIT_ENTRY", "未到突破触发价", passed=["quote"], refs={"quote": quote.raw_evidence_ref})
    if price > plan.entry_ceiling:
        return _decision(plan, now, "NO_TRADE", "现价超过计划入场上限", failed=["price"], refs={"quote": quote.raw_evidence_ref})

    passed = ["price"]
    failed: list[str] = []
    refs = {"quote": quote.raw_evidence_ref}
    if not (
        quote.data.get("vwap") is not None
        and float(quote.data["price"]) >= float(quote.data["vwap"])
        and float(quote.data["volume_ratio"]) >= 1.5
        and float(quote.data["turnover"]) >= 1.0
        and bool(quote.data.get("trigger_held_3m"))
    ):
        failed.append("price_volume")
    else:
        passed.append("price_volume")
    if not _fresh(fund_flow, "fund_flow", now) or float(fund_flow.data["main_net_inflow"]) <= 0:
        failed.append("fund_flow")
    else:
        passed.append("fund_flow")
        refs["fund_flow"] = fund_flow.raw_evidence_ref
    if not _fresh(sector, "sector", now) or not (
        float(sector.data["change_pct"]) >= 1.0 and float(sector.data["advancing_ratio"]) >= 60.0
    ):
        failed.append("sector")
    else:
        passed.append("sector")
        refs["sector"] = sector.raw_evidence_ref
    if not _fresh(chip, "chip", now) or not (
        price >= float(chip.data["cost_90_high"]) and float(chip.data["profit_ratio"]) <= 85.0
    ):
        failed.append("chip")
    else:
        passed.append("chip")
        refs["chip"] = chip.raw_evidence_ref
    if not _order_book_passes(order_books, now):
        failed.append("order_book")
    else:
        passed.append("order_book")
        refs["order_book"] = order_books[-1].raw_evidence_ref
    if failed:
        return _decision(plan, now, "NO_TRADE", f"盘中门禁未通过：{','.join(failed)}", passed=passed, failed=failed, refs=refs)
    return _decision(
        plan,
        now,
        "BUY_ALLOWED",
        "价格触发且五项盘中确认与组合风控全部通过；有效期 5 分钟",
        passed=passed,
        refs=refs,
        maximum_shares=min(plan.maximum_shares, risk_gate.maximum_shares),
    )
