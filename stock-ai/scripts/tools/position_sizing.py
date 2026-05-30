#!/usr/bin/env python3
"""基于持仓执行卡纪律的试探仓 / 换仓执行表计算。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from scripts.tools.holdings_context import AGENT_HOLDINGS


@dataclass
class AccountSnapshot:
    total_assets: float
    available_cash: float
    position_pct: float


@dataclass
class SwapLeg:
    name: str
    code: str
    shares: int
    ref_price: float
    amount: float


@dataclass
class ProbeRow:
    label: str
    entry: float
    shares: int
    amount: float
    stop: float
    target: float
    risk_yuan: float
    risk_pct: float
    reward_yuan: float
    rr_ratio: float


@dataclass
class ExecutionPlan:
    account: AccountSnapshot
    swap_out: SwapLeg | None
    after_swap_cash: float
    after_swap_position_pct: float
    single_stock_cap: float
    max_risk_budget: float
    probes: list[ProbeRow]
    recommended: str


def _parse_money(text: str) -> float:
    m = re.search(r"([\d,.]+)", text.replace(",", ""))
    return float(m.group(1)) if m else 0.0


def load_account_snapshot(holdings_path: Path | None = None) -> AccountSnapshot:
    path = holdings_path or AGENT_HOLDINGS
    if not path.exists():
        return AccountSnapshot(0.0, 0.0, 0.0)
    text = path.read_text(encoding="utf-8")
    total = available = position = 0.0
    for line in text.splitlines():
        if "**总资产**" in line:
            total = _parse_money(line)
        elif "**可用资金**" in line:
            available = _parse_money(line)
        elif line.startswith("- **仓位**"):
            m = re.search(r"([\d.]+)%", line)
            if m:
                position = float(m.group(1))
    return AccountSnapshot(total, available, position)


def _round_lots(shares: int) -> int:
    return max(0, (shares // 100) * 100)


def build_swap_probe_plan(
    *,
    target_code: str,
    target_name: str,
    entry_prices: list[tuple[str, float]],
    stop: float,
    targets: list[float],
    swap_code: str | None = None,
    swap_name: str | None = None,
    swap_shares: int = 0,
    swap_price: float = 0.0,
    probe_share_candidates: list[int] | None = None,
    single_stock_pct: float = 0.30,
    trade_risk_pct: float = 0.02,
    commission_rate: float = 0.0003,
) -> ExecutionPlan:
    """换仓 + 试探建仓执行表（100 股整数倍）。"""
    acct = load_account_snapshot()
    swap_out = None
    cash = acct.available_cash
    securities = acct.total_assets - acct.available_cash

    if swap_code and swap_shares > 0 and swap_price > 0:
        swap_out = SwapLeg(
            swap_name or swap_code,
            swap_code,
            swap_shares,
            swap_price,
            swap_shares * swap_price,
        )
        cash += swap_out.amount * (1 - commission_rate)
        securities -= swap_out.amount

    total = acct.total_assets
    after_pos = (securities / total * 100) if total else 0.0
    cap = total * single_stock_pct
    risk_budget = total * trade_risk_pct
    target1 = min(targets) if targets else 0.0

    probe_share_candidates = probe_share_candidates or [100, 200, 300]
    probes: list[ProbeRow] = []

    for label, entry in entry_prices:
        if entry <= stop:
            continue
        per_share_risk = entry - stop
        max_by_risk = _round_lots(int(risk_budget / per_share_risk)) if per_share_risk > 0 else 0
        max_by_cap = _round_lots(int(cap / entry)) if entry > 0 else 0
        max_by_cash = _round_lots(int(cash / entry)) if entry > 0 else 0
        upper = min(x for x in (max_by_risk, max_by_cap, max_by_cash) if x > 0) if any(
            x > 0 for x in (max_by_risk, max_by_cap, max_by_cash)
        ) else 100
        for sh in probe_share_candidates:
            if sh > upper:
                continue
            risk = sh * per_share_risk
            reward = sh * (target1 - entry) if target1 > entry else 0.0
            rr = (reward / risk) if risk > 0 else 0.0
            probes.append(
                ProbeRow(
                    label=label,
                    entry=entry,
                    shares=sh,
                    amount=round(sh * entry, 2),
                    stop=stop,
                    target=target1,
                    risk_yuan=round(risk, 2),
                    risk_pct=round(risk / total * 100, 2) if total else 0.0,
                    reward_yuan=round(reward, 2),
                    rr_ratio=round(rr, 2),
                )
            )

    recommended = ""
    if probes:
        ok = [p for p in probes if p.rr_ratio >= 2.0 and p.shares <= 200]
        pick = ok[0] if ok else probes[0]
        recommended = (
            f"优先方案：{pick.label} 买入 {pick.shares} 股 @约{pick.entry:.2f} 元，"
            f"止损 {pick.stop:.2f}，目标 {pick.target:.2f}，账户风险约 {pick.risk_pct:.2f}%"
        )

    return ExecutionPlan(
        account=acct,
        swap_out=swap_out,
        after_swap_cash=round(cash, 2),
        after_swap_position_pct=round(after_pos, 1),
        single_stock_cap=round(cap, 2),
        max_risk_budget=round(risk_budget, 2),
        probes=probes,
        recommended=recommended,
    )


def format_execution_plan(plan: ExecutionPlan, *, target_name: str, target_code: str) -> str:
    lines = [
        f"## {target_name}({target_code}) 换仓试探执行表",
        "",
        f"- 总资产：{plan.account.total_assets:.2f} 元 | 可用：{plan.account.available_cash:.2f} 元 | 仓位：{plan.account.position_pct:.1f}%",
    ]
    if plan.swap_out:
        s = plan.swap_out
        lines.append(
            f"- 第一步减：{s.name}({s.code}) **{s.shares} 股** @约 {s.ref_price:.2f} 元 → 释放约 **{s.amount:.0f} 元**"
        )
        lines.append(
            f"- 减后可用资金约：**{plan.after_swap_cash:.2f} 元** | 仓位约：**{plan.after_swap_position_pct:.1f}%**"
        )
    lines.extend(
        [
            f"- 单股上限（30%）：{plan.single_stock_cap:.0f} 元 | 单笔风险预算（2%）：{plan.max_risk_budget:.0f} 元",
            "",
            "| 场景 | 买入价 | 股数 | 金额 | 止损 | 目标 | 风险(元) | 风险占账户 | 盈亏比 |",
            "|------|--------|------|------|------|------|----------|------------|--------|",
        ]
    )
    for p in plan.probes:
        lines.append(
            f"| {p.label} | {p.entry:.2f} | {p.shares} | {p.amount:.0f} | {p.stop:.2f} | {p.target:.2f} | "
            f"{p.risk_yuan:.0f} | {p.risk_pct:.2f}% | {p.rr_ratio:.1f}:1 |"
        )
    if plan.recommended:
        lines.extend(["", f"**建议**：{plan.recommended}"])
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="换仓试探执行表")
    parser.add_argument("--code", required=True, help="目标代码，如 600863")
    parser.add_argument("--name", default="", help="目标名称")
    parser.add_argument("--entry", type=float, nargs="+", default=[7.0, 6.64], help="试探买入价")
    parser.add_argument("--stop", type=float, required=True, help="止损价")
    parser.add_argument("--target", type=float, nargs="+", default=[8.0, 9.0], help="目标价")
    parser.add_argument("--swap-code", default="", help="换出代码")
    parser.add_argument("--swap-name", default="", help="换出名称")
    parser.add_argument("--swap-shares", type=int, default=0, help="换出股数")
    parser.add_argument("--swap-price", type=float, default=0.0, help="换出参考价")
    args = parser.parse_args()

    entries = [(f"回踩{i + 1}@{p:.2f}", p) for i, p in enumerate(args.entry)]
    plan = build_swap_probe_plan(
        target_code=args.code.zfill(6),
        target_name=args.name or args.code,
        entry_prices=entries,
        stop=args.stop,
        targets=args.target,
        swap_code=args.swap_code.zfill(6) if args.swap_code else None,
        swap_name=args.swap_name or None,
        swap_shares=args.swap_shares,
        swap_price=args.swap_price,
    )
    print(format_execution_plan(plan, target_name=args.name or args.code, target_code=args.code.zfill(6)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
