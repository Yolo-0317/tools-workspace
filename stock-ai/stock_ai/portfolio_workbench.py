"""账户操作台：组合级决策支持数据，不包含下单能力。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.tools.holdings_card_parser import parse_account, parse_stock_positions


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "investment-agent"
CARD_PATH = AGENT_DIR / "持仓执行卡.md"
CONFIG_PATH = AGENT_DIR / "账户操作台配置.json"


def _load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def build_portfolio_workbench_payload() -> dict[str, Any]:
    """从已核对执行卡和结构化配置生成 Home Hub 的展示数据。"""
    config = _load_config()
    card_text = CARD_PATH.read_text(encoding="utf-8")
    account = parse_account(card_text)
    positions = parse_stock_positions(card_text)
    capital = config["capital"]
    arrived = float(capital["arrived_principal"])
    planned = float(capital["planned_principal"])
    qualification_target = float(capital.get("qualification_assets_target", planned))
    trading_budget = float(capital.get("trading_budget", arrived))
    principal_reconciliation_required = bool(capital.get("principal_reconciliation_required", False))
    market_value = float(account.market_value or 0)
    total_assets = float(account.total_assets or 0)
    notes = config.get("position_notes", {})
    trade_cards = config.get("trade_cards", {})
    confirmation_template = config.get("confirmation_template", {})
    position_confirmations = config.get("position_confirmations", {})

    position_rows: list[dict[str, Any]] = []
    for position in positions:
        value = position.market_value
        if value is None and position.price is not None:
            value = position.price * position.shares
        pnl_amount = (position.price - position.cost) * position.shares if position.price is not None else None
        note = notes.get(position.code, {})
        operation_card = note.get("operation_card") or {}
        trade_card = trade_cards.get(position.code, {})
        confirmation_card = deepcopy(confirmation_template)
        confirmation_card.update(position_confirmations.get(position.code, {}))
        position_rows.append(
            {
                "code": position.code,
                "name": position.name,
                "shares": position.shares,
                "cost": position.cost,
                "current_price": position.price,
                "market_value": value,
                "pnl_amount": pnl_amount,
                "pnl_pct": ((position.price / position.cost - 1) * 100)
                if position.price is not None and position.cost
                else None,
                "role": note.get("role", position.category or "待归类"),
                "decision": note.get("decision", "待诊断"),
                "next_review": note.get("next_review", "补齐持有逻辑与失效条件"),
                "operation_card": operation_card or None,
                "trade_profile": operation_card.get("trade_profile", trade_card.get("trade_profile", "库存观察·待交易化")),
                "entry_gate": operation_card.get("entry_gate", trade_card.get("entry_gate", "补齐题材、板块、量价资金、筹码与盘口确认后再评估")),
                "exit_rule": operation_card.get("exit_rule", trade_card.get("exit_rule", "资料不足时不加仓；交易逻辑失效时不转长期持有")),
                "confirmation_card": confirmation_card or None,
                "weight_pct": round((float(value) / market_value) * 100, 2) if value and market_value else None,
                "trading_budget_weight_pct": round((float(value) / trading_budget) * 100, 2)
                if value and trading_budget
                else None,
            }
        )

    themes: list[dict[str, Any]] = []
    assigned_codes: set[str] = set()
    value_by_code = {row["code"]: float(row["market_value"] or 0) for row in position_rows}
    for group in config.get("theme_groups", []):
        codes = set(group.get("codes", []))
        assigned_codes.update(codes)
        value = sum(value_by_code.get(code, 0) for code in codes)
        pct = round(value / market_value * 100, 2) if market_value else 0.0
        themes.append(
            {
                "name": group["name"],
                "market_value": value,
                "weight_pct": pct,
                "target_max_pct": group.get("target_max_pct"),
                "over_limit": pct > float(group.get("target_max_pct", 100)),
            }
        )
    other_value = sum(value for code, value in value_by_code.items() if code not in assigned_codes)
    if other_value:
        themes.append(
            {
                "name": "其他待归类",
                "market_value": other_value,
                "weight_pct": round(other_value / market_value * 100, 2) if market_value else 0.0,
                "target_max_pct": None,
                "over_limit": False,
            }
        )

    return {
        "source": "持仓执行卡（券商持仓页人工核对）",
        "as_of": account.snapshot_date.isoformat() if account.snapshot_date else None,
        "phase_label": capital["phase_label"],
        "account": {
            "arrived_principal": arrived,
            "principal_label": "已核对本金（待补新增流水）" if principal_reconciliation_required else "已到位本金",
            "planned_principal": planned,
            "qualification_assets_target": qualification_target,
            "trading_budget": trading_budget,
            "total_assets": total_assets or None,
            "market_value": market_value or None,
            "available_cash": account.available_cash,
            "holding_pnl": account.holding_pnl,
            "daily_pnl": account.daily_pnl,
            "cumulative_pnl": None if principal_reconciliation_required else round(total_assets - arrived, 2) if total_assets else None,
            "cumulative_pnl_pct": None if principal_reconciliation_required else round((total_assets / arrived - 1) * 100, 2) if total_assets and arrived else None,
            "account_position_pct": round(market_value / total_assets * 100, 2) if total_assets else None,
            "plan_arrived_pct": None if principal_reconciliation_required else round(arrived / planned * 100, 2) if planned else None,
            "plan_market_exposure_pct": round(market_value / planned * 100, 2) if planned else None,
            "trading_budget_exposure_pct": round(market_value / trading_budget * 100, 2)
            if trading_budget
            else None,
        },
        "actions": config.get("action_queue", []),
        "themes": themes,
        "positions": position_rows,
    }
