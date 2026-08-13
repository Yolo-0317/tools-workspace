#!/usr/bin/env python3
"""东方财富证券网页持仓 JSON → MySQL portfolio_positions / portfolio_account。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
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


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    cleaned = str(value).replace(",", "").replace("%", "").strip()
    match = re.search(r"[+-]?[\d.]+", cleaned)
    if match is None:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def _captured_at(payload: dict[str, Any]) -> datetime:
    raw = str(payload.get("fetched_at") or "").strip().replace("Z", "+00:00")
    if not raw:
        raise ValueError("fetched_at is required")
    value = datetime.fromisoformat(raw)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("fetched_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _masked_account_identifier(value: Any) -> str:
    digits = "".join(re.findall(r"\d", str(value or "")))
    if len(digits) < 4:
        return ""
    return f"{digits[:2]}{'*' * max(4, len(digits) - 4)}{digits[-2:]}"


@dataclass(frozen=True)
class BrokerPosition:
    code: str
    name: str
    asset_type: str
    shares: int
    available_shares: int
    cost_price: Decimal
    current_price: Decimal | None
    market_value: Decimal | None
    position_pnl: Decimal | None
    position_pnl_pct: Decimal | None
    daily_pnl: Decimal | None
    daily_pnl_pct: Decimal | None
    status: str
    action: str
    broker_captured_at: datetime


@dataclass(frozen=True)
class BrokerAccount:
    total_assets: Decimal | None
    available_cash: Decimal | None
    cash_balance: Decimal | None
    withdrawable_cash: Decimal | None
    frozen_cash: Decimal | None
    market_value: Decimal | None
    position_ratio: Decimal | None
    holding_pnl: Decimal | None
    daily_pnl: Decimal | None
    broker_captured_at: datetime
    masked_account_identifier: str


def _status_from_pnl_pct(pnl_pct: str) -> str:
    v = _parse_money(pnl_pct.replace("%", ""))
    if v is None:
        return ""
    if v <= -20:
        return "深套"
    if v < 0:
        return "微亏"
    return "盈利"


def jywg_payload_to_broker_facts(
    payload: dict[str, Any],
) -> tuple[list[BrokerPosition], BrokerAccount]:
    account_raw = payload.get("account") or {}
    captured_at = _captured_at(payload)
    total = _parse_decimal(account_raw.get("总资产"))
    market = _parse_decimal(account_raw.get("证券市值"))
    ratio = (
        (market / total)
        if market is not None and total not in (None, Decimal("0"))
        else None
    )

    positions: list[BrokerPosition] = []
    for row in payload.get("positions") or []:
        code = str(row.get("code", "")).strip().zfill(6)
        if not re.fullmatch(r"\d{6}", code):
            continue
        cost = _parse_decimal(row.get("cost")) or Decimal("0")
        positions.append(
            BrokerPosition(
                code=code,
                name=str(row.get("name") or ""),
                asset_type="fund" if code.startswith(("15", "16", "51")) else "stock",
                shares=_parse_int(row.get("qty") or "0"),
                available_shares=_parse_int(row.get("available") or "0"),
                cost_price=cost,
                current_price=_parse_decimal(row.get("price")),
                market_value=_parse_decimal(row.get("market_value")),
                position_pnl=_parse_decimal(row.get("pnl")),
                position_pnl_pct=_parse_decimal(row.get("pnl_pct")),
                daily_pnl=_parse_decimal(row.get("day_pnl")),
                daily_pnl_pct=_parse_decimal(row.get("day_pnl_pct")),
                status=_status_from_pnl_pct(str(row.get("pnl_pct") or "")),
                action=str(row.get("action") or ""),
                broker_captured_at=captured_at,
            )
        )

    account = BrokerAccount(
        total_assets=total,
        available_cash=_parse_decimal(account_raw.get("可用资金")),
        cash_balance=_parse_decimal(account_raw.get("资金余额")),
        withdrawable_cash=_parse_decimal(account_raw.get("可取资金")),
        frozen_cash=_parse_decimal(account_raw.get("冻结资金")),
        market_value=market,
        position_ratio=ratio,
        holding_pnl=_parse_decimal(account_raw.get("持仓盈亏")),
        daily_pnl=_parse_decimal(account_raw.get("当日盈亏")),
        broker_captured_at=captured_at,
        masked_account_identifier=_masked_account_identifier(payload.get("user")),
    )
    return positions, account


def jywg_payload_to_card(payload: dict[str, Any]) -> tuple[list[CardPosition], CardAccount]:
    """将 fetch_jywg_positions_opencli 输出转为 sync_from_card 结构。"""
    broker_positions, broker_account = jywg_payload_to_broker_facts(payload)
    positions = [
        CardPosition(
            name=position.name,
            code=position.code,
            shares=position.shares,
            cost=float(position.cost_price),
            price=(
                float(position.current_price)
                if position.current_price is not None
                else None
            ),
            status=position.status,
            action=position.action,
            asset_type=position.asset_type,
        )
        for position in broker_positions
    ]

    acct = CardAccount(
        total_assets=(
            float(broker_account.total_assets)
            if broker_account.total_assets is not None
            else None
        ),
        available_cash=(
            float(broker_account.available_cash)
            if broker_account.available_cash is not None
            else None
        ),
        market_value=(
            float(broker_account.market_value)
            if broker_account.market_value is not None
            else None
        ),
        fund_value=None,
        position_ratio=(
            float(broker_account.position_ratio)
            if broker_account.position_ratio is not None
            else None
        ),
        holding_pnl=(
            float(broker_account.holding_pnl)
            if broker_account.holding_pnl is not None
            else None
        ),
        daily_pnl=(
            float(broker_account.daily_pnl)
            if broker_account.daily_pnl is not None
            else None
        ),
        snapshot_date=date.today(),
    )
    return positions, acct


def sync_jywg_payload(payload: dict[str, Any]) -> dict[str, int]:
    """原子写入券商事实、仓位事件与决策事件；不修改 alert_rules。"""
    from stock_ai.advisor_memory.position_sync import sync_broker_facts_with_memory

    positions, account = jywg_payload_to_broker_facts(payload)
    if not positions:
        raise RuntimeError("东方财富证券网页持仓 payload 无持仓行")
    return sync_broker_facts_with_memory(positions, account, source="jywg")
