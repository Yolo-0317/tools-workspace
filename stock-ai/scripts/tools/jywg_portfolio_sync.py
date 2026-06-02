#!/usr/bin/env python3
"""东财 jywg 网页持仓 JSON → MySQL portfolio_positions / portfolio_account。"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from scripts.tools.holdings_card_parser import CardAccount, CardPosition


def _parse_money(text: str) -> float | None:
    if not text:
        return None
    s = str(text).replace(",", "").strip()
    m = re.search(r"([+-]?[\d.]+)", s)
    return float(m.group(1)) if m else None


def _parse_int(text: str) -> int:
    m = re.search(r"(\d+)", str(text).replace(",", ""))
    return int(m.group(1)) if m else 0


def _status_from_pnl_pct(pnl_pct: str) -> str:
    v = _parse_money(pnl_pct.replace("%", ""))
    if v is None:
        return ""
    if v <= -20:
        return "🔴 深套"
    if v < 0:
        return "⚠️ 微亏"
    return "✅ 盈利"


def jywg_payload_to_card(payload: dict[str, Any]) -> tuple[list[CardPosition], CardAccount]:
    """将 fetch_jywg_positions_opencli 输出转为 sync_from_card 结构。"""
    account_raw = payload.get("account") or {}
    total = _parse_money(account_raw.get("总资产", ""))
    cash = _parse_money(account_raw.get("可用资金", ""))
    market = _parse_money(account_raw.get("证券市值", ""))
    holding_pnl = _parse_money(account_raw.get("持仓盈亏", ""))
    ratio = (market / total) if market is not None and total else None

    positions: list[CardPosition] = []
    for row in payload.get("positions") or []:
        code = str(row.get("code", "")).zfill(6)
        if not re.fullmatch(r"\d{6}", code):
            continue
        asset_type = "fund" if code.startswith(("15", "16", "51")) else "stock"
        positions.append(
            CardPosition(
                name=str(row.get("name") or ""),
                code=code,
                shares=_parse_int(row.get("qty") or row.get("available") or "0"),
                cost=_parse_money(row.get("cost") or "") or 0.0,
                price=_parse_money(row.get("price") or ""),
                status=_status_from_pnl_pct(str(row.get("pnl_pct") or "")),
                action="",
                asset_type=asset_type,
            )
        )

    acct = CardAccount(
        total_assets=total,
        available_cash=cash,
        market_value=market,
        fund_value=None,
        position_ratio=ratio,
        holding_pnl=holding_pnl,
        daily_pnl=_parse_money(account_raw.get("当日盈亏", "")),
        snapshot_date=date.today(),
    )
    return positions, acct


def sync_jywg_payload(payload: dict[str, Any]) -> dict[str, int]:
    """写入持仓与账户；不修改 alert_rules（仍由执行卡 sync 维护）。"""
    from scripts.tools.portfolio_db import sync_positions_and_account

    positions, account = jywg_payload_to_card(payload)
    if not positions:
        raise RuntimeError("jywg  payload 无持仓行")
    return sync_positions_and_account(positions, account, source="jywg")
