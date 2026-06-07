#!/usr/bin/env python3
"""Load holdings + trading rules for daily selection / AI review."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

QCLAW_WORKSPACE = Path.home() / ".qclaw/workspace"
AGENT_ROOT = Path(__file__).resolve().parents[2] / "investment-agent"
AGENT_HOLDINGS = AGENT_ROOT / "持仓执行卡.md"
AGENT_ADVISOR_STRATEGY = AGENT_ROOT / "投顾主策略.md"
DEFAULT_HOLDINGS = QCLAW_WORKSPACE / "持仓执行卡.md"
TRADING_RULES_CANDIDATES = (
    AGENT_ROOT / "memory" / "trading-strategies.md",
    QCLAW_WORKSPACE / "memory" / "trading-strategies.md",
)


@dataclass
class Holding:
    name: str
    code: str
    shares: str
    cost: str
    price: str
    pnl: str
    status: str
    action: str


def _extract_section(text: str, heading_prefix: str) -> str:
    lines: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line.startswith("## ") and capturing:
            break
        if line.startswith(heading_prefix):
            capturing = True
            lines.append(line)
            continue
        if capturing:
            lines.append(line)
    return "\n".join(lines).strip()


def _load_holdings_from_db() -> tuple[set[str], list[Holding]] | None:
    from scripts.tools.portfolio_db import load_latest_closes, load_positions

    positions = load_positions()
    if not positions:
        return None

    closes = load_latest_closes([p.code for p in positions])
    codes: set[str] = set()
    holdings: list[Holding] = []
    for p in positions:
        codes.add(p.code)
        price_f = closes.get(p.code)
        price = f"{price_f:.3f}" if price_f is not None else "—"
        if price_f is not None and p.cost and p.shares:
            pnl_amt = (price_f - p.cost) * p.shares
            pnl_pct = (price_f / p.cost - 1) * 100 if p.cost else 0
            pnl = f"{pnl_amt:+.0f}({pnl_pct:+.1f}%)"
        else:
            pnl = "—"
        holdings.append(
            Holding(
                name=p.name,
                code=p.code,
                shares=str(p.shares),
                cost=f"{p.cost:.3f}",
                price=price,
                pnl=pnl,
                status=p.status,
                action=p.action,
            )
        )
    return codes, holdings


def load_holdings_card(path: Path | None = None) -> tuple[set[str], list[Holding], str]:
    if path is None:
        path = AGENT_HOLDINGS if AGENT_HOLDINGS.exists() else DEFAULT_HOLDINGS

    text = path.read_text(encoding="utf-8") if path.exists() else ""
    db_result = _load_holdings_from_db()
    if db_result is None:
        hint = (
            "（MySQL 无持仓。请先运行："
            "uv run python -m scripts.tools.sync_portfolio_from_card）"
        )
        if text:
            plans = _extract_section(text, "## 进行中计划")
            red = _extract_section(text, "## 禁止规则")
            extra = "\n\n".join(s for s in (plans, red) if s)
            return set(), [], hint + ("\n\n" + extra if extra else "")
        return set(), [], hint

    codes, holdings = db_result
    parts: list[str] = ["## 当前持仓快照（MySQL，源：持仓执行卡）"]
    for h in holdings:
        action_hint = f" | 建议: {h.action}" if h.action else ""
        parts.append(
            f"- {h.name}({h.code}) {h.shares}股 成本{h.cost} 现价{h.price} "
            f"盈亏{h.pnl}{action_hint}"
        )

    if text:
        for line in text.splitlines():
            if line.startswith("- **可用资金**") or line.startswith("- **仓位**"):
                parts.append(line.lstrip("- "))

        for title in ("## 进行中计划", "## 禁止规则", "## 仓位控制"):
            section = _extract_section(text, title)
            if section:
                parts.extend(["", section])

    return codes, holdings, "\n".join(parts)


def resolve_trading_rules_path(path: Path | None = None) -> Path | None:
    if path is not None:
        return path if path.exists() else None
    for candidate in TRADING_RULES_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_trading_rules(path: Path | None = None) -> str:
    resolved = resolve_trading_rules_path(path)
    if resolved is None:
        return "（未找到 memory/trading-strategies.md）"
    return resolved.read_text(encoding="utf-8").strip()


def load_advisor_strategy(path: Path | None = None) -> str:
    resolved = path or AGENT_ADVISOR_STRATEGY
    if not resolved.exists():
        return "（未找到 investment-agent/投顾主策略.md）"
    return resolved.read_text(encoding="utf-8").strip()


def load_full_decision_context(
    holdings_path: Path | None = None,
    rules_path: Path | None = None,
    advisor_path: Path | None = None,
) -> tuple[set[str], str]:
    """Return holdings codes and combined context for AI decision-making."""
    codes, _, holdings_ctx = load_holdings_card(holdings_path)
    advisor_ctx = load_advisor_strategy(advisor_path)
    rules_ctx = load_trading_rules(rules_path)
    combined = (
        "# 决策上下文（必须全部遵循）\n\n"
        "## A. 投顾主策略（投资决策最高权威）\n"
        f"{advisor_ctx}\n\n"
        "## B. 高级操盘策略（A股定制版）\n"
        f"{rules_ctx}\n\n"
        "## C. 持仓执行卡（执行价位、监控与红线）\n"
        f"{holdings_ctx}"
    )
    return codes, combined
