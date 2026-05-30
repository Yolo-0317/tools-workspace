#!/usr/bin/env python3
"""Load holdings + trading rules for daily selection / AI review."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

QCLAW_WORKSPACE = Path.home() / ".qclaw/workspace"
AGENT_ROOT = Path(__file__).resolve().parents[2] / "investment-agent"
AGENT_HOLDINGS = AGENT_ROOT / "持仓执行卡.md"
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


def _cell(line: str, idx: int) -> str:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) <= idx:
        return ""
    return parts[idx].strip("* ")


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


def load_holdings_card(path: Path | None = None) -> tuple[set[str], list[Holding], str]:
    if path is None:
        path = AGENT_HOLDINGS if AGENT_HOLDINGS.exists() else DEFAULT_HOLDINGS
    codes: set[str] = set()
    holdings: list[Holding] = []
    if not path.exists():
        return codes, holdings, "（未找到持仓执行卡）"

    text = path.read_text(encoding="utf-8")
    in_table = False
    for line in text.splitlines():
        if line.startswith("| 股票 | 代码 |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if line.startswith("|------"):
                continue
            code = _cell(line, 2)
            if not re.fullmatch(r"\d{6}", code):
                continue
            codes.add(code)
            holdings.append(
                Holding(
                    name=_cell(line, 1),
                    code=code,
                    shares=_cell(line, 3),
                    cost=_cell(line, 4),
                    price=_cell(line, 5),
                    pnl=_cell(line, 7),
                    status=_cell(line, 8),
                    action=_cell(line, 9),
                )
            )

    parts: list[str] = ["## 当前持仓快照"]
    for h in holdings:
        parts.append(
            f"- {h.name}({h.code}) {h.shares}股 成本{h.cost} 现价{h.price} "
            f"盈亏{h.pnl} | 卡片建议: {h.action}"
        )

    for line in text.splitlines():
        if line.startswith("- **可用资金**") or line.startswith("- **仓位**"):
            parts.append(line.lstrip("- "))

    for title in ("## 进行中计划", "## 禁止规则", "## 仓位控制"):
        section = _extract_section(text, title)
        if section:
            parts.extend(["", section])

    if len(parts) <= 1:
        return codes, holdings, "（持仓执行卡无有效内容）"

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


def load_full_decision_context(
    holdings_path: Path | None = None,
    rules_path: Path | None = None,
) -> tuple[set[str], str]:
    """Return holdings codes and combined context for AI decision-making."""
    codes, _, holdings_ctx = load_holdings_card(holdings_path)
    rules_ctx = load_trading_rules(rules_path)
    combined = (
        "# 决策上下文（必须全部遵循）\n\n"
        "## A. 高级操盘策略（A股定制版，全部逻辑）\n"
        f"{rules_ctx}\n\n"
        "## B. 持仓执行卡（最新计划与红线，优先级高于通用策略冲突处）\n"
        f"{holdings_ctx}"
    )
    return codes, combined
