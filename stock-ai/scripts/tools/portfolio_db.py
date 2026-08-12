#!/usr/bin/env python3
"""持仓与监控规则 MySQL 读写（权威数据源；选股见 selection_daily_results）。"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[2]
STOCK_AI = ROOT
AGENT = STOCK_AI / "investment-agent"


@dataclass
class DbPosition:
    code: str
    name: str
    shares: int
    cost: float
    status: str = ""
    action: str = ""


@dataclass
class DbAccount:
    total_assets: float | None
    available_cash: float | None
    market_value: float | None
    position_ratio: float | None
    holding_pnl: float | None
    snapshot_date: date | None


def _load_dotenv() -> None:
    for path in (STOCK_AI / ".env", ROOT.parent / "stock-mysql" / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def _normalize_mysql_host(url: str) -> str:
    """本机直跑时把 host.docker.internal 换成 127.0.0.1；容器内保持原样。"""
    if os.path.exists("/.dockerenv"):
        return url
    return url.replace("host.docker.internal", "127.0.0.1")


def mysql_url() -> str:
    _load_dotenv()
    url = os.environ.get("MYSQL_URL", "")
    if not url:
        user = os.environ.get("MYSQL_USER", "stock")
        password = os.environ.get("MYSQL_PASSWORD", "")
        db = os.environ.get("MYSQL_DATABASE", "stock_data")
        url = f"mysql+pymysql://{user}:{password}@127.0.0.1:3306/{db}"
    return _normalize_mysql_host(url)


def get_engine() -> Engine | None:
    url = mysql_url()
    if not url or "://" not in url:
        return None
    try:
        return create_engine(url, pool_pre_ping=True)
    except Exception:
        return None


def _row_to_rule(row: Any) -> dict:
    rule: dict[str, Any] = {
        "id": row.rule_id,
        "code": str(row.ts_code).zfill(6),
        "name": row.name or "",
        "type": row.rule_type,
        "message": row.message_template or "",
    }
    if row.price is not None:
        rule["price"] = float(row.price)
    if row.low_price is not None:
        rule["low"] = float(row.low_price)
    if row.high_price is not None:
        rule["high"] = float(row.high_price)
    if row.pct_threshold is not None:
        rule["pct"] = float(row.pct_threshold)
    return rule


def load_positions(*, engine: Engine | None = None) -> list[DbPosition]:
    engine = engine or get_engine()
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT ts_code, name, shares, cost_price, status_note, action_note
                    FROM portfolio_positions
                    WHERE is_active = 1
                    ORDER BY ts_code
                    """
                )
            ).fetchall()
    except Exception:
        return []

    out: list[DbPosition] = []
    for row in rows:
        code = str(row.ts_code).zfill(6)
        if not re.fullmatch(r"\d{6}", code):
            continue
        out.append(
            DbPosition(
                code=code,
                name=str(row.name or code),
                shares=int(row.shares or 0),
                cost=float(row.cost_price or 0),
                status=str(row.status_note or ""),
                action=str(row.action_note or ""),
            )
        )
    return out


def load_holding_codes(*, engine: Engine | None = None) -> set[str]:
    return {p.code for p in load_positions(engine=engine)}


def load_account(*, engine: Engine | None = None) -> DbAccount | None:
    engine = engine or get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT total_assets, available_cash, market_value, position_ratio,
                           holding_pnl, snapshot_date
                    FROM portfolio_account
                    WHERE id = 1
                    """
                )
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    snap = row.snapshot_date
    return DbAccount(
        total_assets=float(row.total_assets) if row.total_assets is not None else None,
        available_cash=float(row.available_cash) if row.available_cash is not None else None,
        market_value=float(row.market_value) if row.market_value is not None else None,
        position_ratio=float(row.position_ratio) if row.position_ratio is not None else None,
        holding_pnl=float(row.holding_pnl) if row.holding_pnl is not None else None,
        snapshot_date=snap if isinstance(snap, date) else None,
    )


def load_latest_closes(codes: list[str], *, engine: Engine | None = None) -> dict[str, float]:
    """从东财 OpenCLI 采集最新价（禁止 HTTP API / MySQL 行情兜底）。"""
    _ = engine
    if not codes:
        return {}
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_quotes

        quotes = fetch_quotes([str(c).zfill(6) for c in codes])
        return {c: q.price for c, q in quotes.items() if q.price is not None}
    except Exception:
        return {}


def upsert_monitor_live_quotes(
    quotes: dict[str, Any],
    *,
    quoted_at: datetime | None = None,
    source: str = "opencli",
    engine: Engine | None = None,
) -> int:
    """写入 monitor_live_quotes（盘中 cron 每 5 分钟更新）。"""
    if not quotes:
        return 0
    engine = engine or get_engine()
    if engine is None:
        return 0
    quoted_at = quoted_at or datetime.now()
    n = 0
    with engine.begin() as conn:
        for code, q in quotes.items():
            ts = str(code).zfill(6)
            name = getattr(q, "name", None) or (q.get("name") if isinstance(q, dict) else "") or ""
            price = getattr(q, "price", None) if not isinstance(q, dict) else q.get("price")
            if price is None:
                continue
            change_amt = (
                getattr(q, "change_amt", None)
                if not isinstance(q, dict)
                else q.get("change_amt")
            )
            change_pct = (
                getattr(q, "change_pct", None)
                if not isinstance(q, dict)
                else q.get("change_pct")
            )
            conn.execute(
                text(
                    """
                    INSERT INTO monitor_live_quotes
                        (ts_code, name, price, change_amt, change_pct, source, quoted_at)
                    VALUES
                        (:ts_code, :name, :price, :change_amt, :change_pct, :source, :quoted_at)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        price = VALUES(price),
                        change_amt = VALUES(change_amt),
                        change_pct = VALUES(change_pct),
                        source = VALUES(source),
                        quoted_at = VALUES(quoted_at)
                    """
                ),
                {
                    "ts_code": ts,
                    "name": name,
                    "price": float(price),
                    "change_amt": change_amt,
                    "change_pct": change_pct,
                    "source": source,
                    "quoted_at": quoted_at.replace(tzinfo=None)
                    if quoted_at.tzinfo
                    else quoted_at,
                },
            )
            n += 1
    return n


def load_monitor_live_quotes(
    codes: list[str],
    *,
    engine: Engine | None = None,
) -> tuple[dict[str, dict[str, Any]], datetime | None]:
    """读 monitor_live_quotes；返回 ({code: row}, 最新 quoted_at)。"""
    if not codes:
        return {}, None
    engine = engine or get_engine()
    if engine is None:
        return {}, None
    codes6 = sorted({str(c).zfill(6) for c in codes})
    placeholders = ", ".join(f":c{i}" for i in range(len(codes6)))
    params: dict[str, Any] = {f"c{i}": c for i, c in enumerate(codes6)}
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT ts_code, name, price, change_amt, change_pct, source, quoted_at
                    FROM monitor_live_quotes
                    WHERE ts_code IN ({placeholders})
                    """
                ),
                params,
            ).fetchall()
    except Exception:
        return {}, None
    out: dict[str, dict[str, Any]] = {}
    batch_as_of: datetime | None = None
    for row in rows:
        code = str(row.ts_code).zfill(6)
        quoted_at = row.quoted_at
        if isinstance(quoted_at, datetime):
            if batch_as_of is None or quoted_at > batch_as_of:
                batch_as_of = quoted_at
        out[code] = {
            "code": code,
            "name": row.name or "",
            "price": float(row.price),
            "change_amt": float(row.change_amt) if row.change_amt is not None else 0.0,
            "change_pct": float(row.change_pct) if row.change_pct is not None else 0.0,
            "source": row.source or "opencli",
            "quoted_at": quoted_at,
        }
    return out, batch_as_of


def load_dashboard_closes(
    codes: list[str],
    *,
    snapshot_slot: str = "eod",
    engine: Engine | None = None,
) -> dict[str, float]:
    """看板展示价：持仓每日快照 > stock_daily 最近收盘（不走 OpenCLI）。"""
    engine = engine or get_engine()
    if engine is None or not codes:
        return {}

    codes6 = sorted({str(c).zfill(6) for c in codes})
    out: dict[str, float] = {}
    slot = (snapshot_slot or "eod").strip() or "eod"

    try:
        with engine.connect() as conn:
            snap = conn.execute(
                text(
                    "SELECT MAX(snapshot_date) FROM portfolio_positions_daily "
                    "WHERE snapshot_slot = :slot"
                ),
                {"slot": slot},
            ).scalar()
            if snap is not None:
                snap_s = snap.isoformat() if isinstance(snap, date) else str(snap)[:10]
                placeholders = ", ".join(f":c{i}" for i in range(len(codes6)))
                params: dict[str, Any] = {
                    "d": snap_s,
                    "slot": slot,
                    **{f"c{i}": c for i, c in enumerate(codes6)},
                }
                rows = conn.execute(
                    text(
                        f"""
                        SELECT ts_code, market_price
                        FROM portfolio_positions_daily
                        WHERE snapshot_date = :d AND snapshot_slot = :slot
                          AND ts_code IN ({placeholders})
                        """
                    ),
                    params,
                ).fetchall()
                for row in rows:
                    if row.market_price is not None:
                        out[str(row.ts_code).zfill(6)] = float(row.market_price)
    except Exception:
        pass

    for code in codes6:
        if code in out:
            continue
        bars = load_stock_daily_bars(code, limit=1, engine=engine)
        if bars and bars[-1].get("close") is not None:
            out[code] = float(bars[-1]["close"])

    return out


def load_alert_rules(
    *,
    source: str | None = None,
    engine: Engine | None = None,
) -> list[dict]:
    engine = engine or get_engine()
    if engine is None:
        return []
    sql = """
        SELECT rule_id, ts_code, name, rule_type, price, low_price, high_price,
               pct_threshold, message_template
        FROM alert_rules
        WHERE is_enabled = 1
    """
    params: dict[str, Any] = {}
    if source:
        sql += " AND source = :source"
        params["source"] = source
    sql += " ORDER BY rule_id"
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return []
    return [_row_to_rule(r) for r in rows]


def load_active_selection_rules(
    *,
    today: date | None = None,
    engine: Engine | None = None,
) -> list[dict]:
    try:
        from stock_ai.advisor_selection import selection_watch_sync_enabled

        if not selection_watch_sync_enabled():
            return []
    except ImportError:
        pass
    today = today or date.today()
    engine = engine or get_engine()
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT ar.rule_id, ar.ts_code, ar.name, ar.rule_type, ar.price,
                           ar.low_price, ar.high_price, ar.pct_threshold, ar.message_template
                    FROM alert_rules ar
                    INNER JOIN selection_watch_picks swp
                      ON swp.ts_code = ar.ts_code
                     AND swp.watch_date = :today
                     AND swp.is_active = 1
                    WHERE ar.source = 'selection'
                      AND ar.is_enabled = 1
                    ORDER BY ar.rule_id
                    """
                ),
                {"today": today.isoformat()},
            ).fetchall()
    except Exception:
        return []
    rules = [_row_to_rule(r) for r in rows]
    for rule in rules:
        rule["watch_date"] = today.isoformat()
    return rules


def load_all_monitor_rules(*, today: date | None = None) -> list[dict]:
    """持仓规则 + 当日选股监控规则（仅 MySQL）。"""
    today = today or date.today()
    engine = get_engine()
    holdings = load_alert_rules(source="holdings", engine=engine)
    for rule in holdings:
        rule["source"] = "holdings"
    selection = load_active_selection_rules(today=today, engine=engine)
    for rule in selection:
        rule["source"] = "selection"
    return holdings + selection


def sync_from_card(positions, account, rules: list[dict]) -> dict[str, int]:
    """写入 portfolio_positions / portfolio_account / alert_rules（source=holdings）。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法同步")

    active_codes = [p.code for p in positions]
    rule_ids = [str(r["id"]) for r in rules]

    with engine.begin() as conn:
        if active_codes:
            placeholders = ", ".join(f":c{i}" for i in range(len(active_codes)))
            params = {f"c{i}": c for i, c in enumerate(active_codes)}
            conn.execute(
                text(
                    f"UPDATE portfolio_positions SET is_active = 0 "
                    f"WHERE ts_code NOT IN ({placeholders})"
                ),
                params,
            )
        else:
            conn.execute(text("UPDATE portfolio_positions SET is_active = 0"))

        pos_n = 0
        for p in positions:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_positions
                      (ts_code, name, asset_type, shares, cost_price,
                       status_note, action_note, source, is_active)
                    VALUES
                      (:code, :name, :atype, :shares, :cost, :status, :action, 'card', 1)
                    ON DUPLICATE KEY UPDATE
                      name = VALUES(name),
                      asset_type = VALUES(asset_type),
                      shares = VALUES(shares),
                      cost_price = VALUES(cost_price),
                      status_note = VALUES(status_note),
                      action_note = VALUES(action_note),
                      source = 'card',
                      is_active = 1
                    """
                ),
                {
                    "code": p.code,
                    "name": p.name,
                    "atype": getattr(p, "asset_type", "stock"),
                    "shares": p.shares,
                    "cost": p.cost,
                    "status": p.status,
                    "action": p.action,
                },
            )
            pos_n += 1

        acct_n = 0
        if account.total_assets is not None or account.available_cash is not None:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_account
                      (id, total_assets, available_cash, market_value, position_ratio,
                       holding_pnl, snapshot_date)
                    VALUES
                      (1, :total, :cash, :market, :pos, :pnl, :snap)
                    ON DUPLICATE KEY UPDATE
                      total_assets = VALUES(total_assets),
                      available_cash = VALUES(available_cash),
                      market_value = VALUES(market_value),
                      position_ratio = VALUES(position_ratio),
                      holding_pnl = VALUES(holding_pnl),
                      snapshot_date = VALUES(snapshot_date)
                    """
                ),
                {
                    "total": account.total_assets,
                    "cash": account.available_cash,
                    "market": account.market_value,
                    "pos": account.position_ratio,
                    "pnl": account.holding_pnl,
                    "snap": account.snapshot_date,
                },
            )
            acct_n = 1

        if rule_ids:
            placeholders = ", ".join(f":r{i}" for i in range(len(rule_ids)))
            params = {f"r{i}": rid for i, rid in enumerate(rule_ids)}
            conn.execute(
                text(
                    f"UPDATE alert_rules SET is_enabled = 0 "
                    f"WHERE source = 'holdings' AND rule_id NOT IN ({placeholders})"
                ),
                params,
            )
        else:
            conn.execute(text("UPDATE alert_rules SET is_enabled = 0 WHERE source = 'holdings'"))

        rule_n = upsert_alert_rules(rules, source="holdings", conn=conn)

    return {"positions": pos_n, "account": acct_n, "rules": rule_n}


def sync_holdings_alert_rules(rules: list[dict]) -> int:
    """仅同步 alert_rules（source=holdings），不改动 portfolio_positions / portfolio_account。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法同步")

    rule_ids = [str(r["id"]) for r in rules]
    with engine.begin() as conn:
        if rule_ids:
            placeholders = ", ".join(f":r{i}" for i in range(len(rule_ids)))
            params = {f"r{i}": rid for i, rid in enumerate(rule_ids)}
            conn.execute(
                text(
                    f"UPDATE alert_rules SET is_enabled = 0 "
                    f"WHERE source = 'holdings' AND rule_id NOT IN ({placeholders})"
                ),
                params,
            )
        else:
            conn.execute(text("UPDATE alert_rules SET is_enabled = 0 WHERE source = 'holdings'"))
        return upsert_alert_rules(rules, source="holdings", conn=conn)


def sync_positions_and_account(
    positions,
    account,
    *,
    source: str = "jywg",
) -> dict[str, int]:
    """仅同步 portfolio_positions / portfolio_account，不改动 alert_rules。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法同步")

    active_codes = [p.code for p in positions]
    src = (source or "jywg").strip() or "jywg"

    with engine.begin() as conn:
        if active_codes:
            placeholders = ", ".join(f":c{i}" for i in range(len(active_codes)))
            params = {f"c{i}": c for i, c in enumerate(active_codes)}
            conn.execute(
                text(
                    f"UPDATE portfolio_positions SET is_active = 0 "
                    f"WHERE ts_code NOT IN ({placeholders})"
                ),
                params,
            )
        else:
            conn.execute(text("UPDATE portfolio_positions SET is_active = 0"))

        pos_n = 0
        for p in positions:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_positions
                      (ts_code, name, asset_type, shares, cost_price,
                       status_note, action_note, source, is_active)
                    VALUES
                      (:code, :name, :atype, :shares, :cost, :status, :action, :src, 1)
                    ON DUPLICATE KEY UPDATE
                      name = VALUES(name),
                      asset_type = VALUES(asset_type),
                      shares = VALUES(shares),
                      cost_price = VALUES(cost_price),
                      status_note = VALUES(status_note),
                      action_note = VALUES(action_note),
                      source = VALUES(source),
                      is_active = 1
                    """
                ),
                {
                    "code": p.code,
                    "name": p.name,
                    "atype": getattr(p, "asset_type", "stock"),
                    "shares": p.shares,
                    "cost": p.cost,
                    "status": p.status,
                    "action": p.action,
                    "src": src,
                },
            )
            pos_n += 1

        acct_n = 0
        if account.total_assets is not None or account.available_cash is not None:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_account
                      (id, total_assets, available_cash, market_value, position_ratio,
                       holding_pnl, snapshot_date)
                    VALUES
                      (1, :total, :cash, :market, :pos, :pnl, :snap)
                    ON DUPLICATE KEY UPDATE
                      total_assets = VALUES(total_assets),
                      available_cash = VALUES(available_cash),
                      market_value = VALUES(market_value),
                      position_ratio = VALUES(position_ratio),
                      holding_pnl = VALUES(holding_pnl),
                      snapshot_date = VALUES(snapshot_date)
                    """
                ),
                {
                    "total": account.total_assets,
                    "cash": account.available_cash,
                    "market": account.market_value,
                    "pos": account.position_ratio,
                    "pnl": account.holding_pnl,
                    "snap": account.snapshot_date,
                },
            )
            acct_n = 1

    return {"positions": pos_n, "account": acct_n, "rules": 0}


def _broker_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("broker_captured_at must be timezone-aware")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _sync_broker_facts_with_connection(
    positions, account, *, source: str, conn
) -> dict[str, int]:
    active_codes = [position.code for position in positions]
    if active_codes:
        placeholders = ", ".join(f":c{i}" for i in range(len(active_codes)))
        params = {f"c{i}": code for i, code in enumerate(active_codes)}
        conn.execute(
            text(
                f"UPDATE portfolio_positions SET is_active = 0 "
                f"WHERE ts_code NOT IN ({placeholders})"
            ),
            params,
        )
    else:
        conn.execute(text("UPDATE portfolio_positions SET is_active = 0"))

    for position in positions:
        conn.execute(
            text(
                """
                INSERT INTO portfolio_positions
                  (ts_code, name, asset_type, shares, available_shares, cost_price,
                   current_price, market_value, position_pnl, position_pnl_pct,
                   daily_pnl, daily_pnl_pct, broker_captured_at,
                   status_note, action_note, source, is_active)
                VALUES
                  (:code, :name, :atype, :shares, :available, :cost,
                   :price, :market, :pnl, :pnl_pct, :daily_pnl, :daily_pnl_pct,
                   :captured_at, :status, :action, :source, 1)
                ON DUPLICATE KEY UPDATE
                  name = VALUES(name),
                  asset_type = VALUES(asset_type),
                  shares = VALUES(shares),
                  available_shares = VALUES(available_shares),
                  cost_price = VALUES(cost_price),
                  current_price = VALUES(current_price),
                  market_value = VALUES(market_value),
                  position_pnl = VALUES(position_pnl),
                  position_pnl_pct = VALUES(position_pnl_pct),
                  daily_pnl = VALUES(daily_pnl),
                  daily_pnl_pct = VALUES(daily_pnl_pct),
                  broker_captured_at = VALUES(broker_captured_at),
                  status_note = VALUES(status_note),
                  action_note = VALUES(action_note),
                  source = VALUES(source),
                  is_active = 1
                """
            ),
            {
                "code": position.code,
                "name": position.name,
                "atype": position.asset_type,
                "shares": position.shares,
                "available": position.available_shares,
                "cost": position.cost_price,
                "price": position.current_price,
                "market": position.market_value,
                "pnl": position.position_pnl,
                "pnl_pct": position.position_pnl_pct,
                "daily_pnl": position.daily_pnl,
                "daily_pnl_pct": position.daily_pnl_pct,
                "captured_at": _broker_timestamp(position.broker_captured_at),
                "status": position.status,
                "action": position.action,
                "source": source,
            },
        )

    account_count = 0
    if account.total_assets is not None or account.available_cash is not None:
        conn.execute(
            text(
                """
                INSERT INTO portfolio_account
                  (id, total_assets, available_cash, cash_balance, withdrawable_cash,
                   frozen_cash, market_value, position_ratio, holding_pnl, daily_pnl,
                   snapshot_date, broker_captured_at)
                VALUES
                  (1, :total, :available, :balance, :withdrawable, :frozen,
                   :market, :ratio, :holding_pnl, :daily_pnl, :snapshot_date, :captured_at)
                ON DUPLICATE KEY UPDATE
                  total_assets = VALUES(total_assets),
                  available_cash = VALUES(available_cash),
                  cash_balance = VALUES(cash_balance),
                  withdrawable_cash = VALUES(withdrawable_cash),
                  frozen_cash = VALUES(frozen_cash),
                  market_value = VALUES(market_value),
                  position_ratio = VALUES(position_ratio),
                  holding_pnl = VALUES(holding_pnl),
                  daily_pnl = VALUES(daily_pnl),
                  snapshot_date = VALUES(snapshot_date),
                  broker_captured_at = VALUES(broker_captured_at)
                """
            ),
            {
                "total": account.total_assets,
                "available": account.available_cash,
                "balance": account.cash_balance,
                "withdrawable": account.withdrawable_cash,
                "frozen": account.frozen_cash,
                "market": account.market_value,
                "ratio": account.position_ratio,
                "holding_pnl": account.holding_pnl,
                "daily_pnl": account.daily_pnl,
                "snapshot_date": account.broker_captured_at.astimezone(timezone.utc).date(),
                "captured_at": _broker_timestamp(account.broker_captured_at),
            },
        )
        account_count = 1
    return {"positions": len(positions), "account": account_count, "rules": 0}


def sync_broker_positions_and_account(
    positions,
    account,
    *,
    source: str = "jywg",
    engine: Engine | None = None,
    connection=None,
) -> dict[str, int]:
    """保存完整券商事实，不读取或修改 alert_rules。"""

    normalized_source = (source or "jywg").strip() or "jywg"
    if connection is not None:
        return _sync_broker_facts_with_connection(
            positions, account, source=normalized_source, conn=connection
        )

    target_engine = engine or get_engine()
    if target_engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法同步")
    with target_engine.begin() as conn:
        return _sync_broker_facts_with_connection(
            positions, account, source=normalized_source, conn=conn
        )


def upsert_alert_rules(rules: list[dict], *, source: str, conn) -> int:
    n = 0
    for r in rules:
        rid = str(r.get("id") or f"{source}_{r.get('code')}_{n}")
        conn.execute(
            text(
                """
                INSERT INTO alert_rules
                  (rule_id, ts_code, name, rule_type, price, low_price, high_price,
                   pct_threshold, message_template, source, is_enabled)
                VALUES
                  (:rid, :code, :name, :rtype, :price, :low, :high, :pct, :msg, :src, 1)
                ON DUPLICATE KEY UPDATE
                  ts_code = VALUES(ts_code),
                  name = VALUES(name),
                  rule_type = VALUES(rule_type),
                  price = VALUES(price),
                  low_price = VALUES(low_price),
                  high_price = VALUES(high_price),
                  pct_threshold = VALUES(pct_threshold),
                  message_template = VALUES(message_template),
                  source = VALUES(source),
                  is_enabled = 1
                """
            ),
            {
                "rid": rid,
                "code": str(r.get("code", "")),
                "name": str(r.get("name", "")),
                "rtype": str(r.get("type", "")),
                "price": r.get("price"),
                "low": r.get("low"),
                "high": r.get("high"),
                "pct": r.get("pct"),
                "msg": str(r.get("message", "")),
                "src": source,
            },
        )
        n += 1
    return n


def sync_selection_payload(payload: dict) -> dict[str, int]:
    """将选股监控结构写入 DB（selection_watch_picks + alert_rules）。"""
    engine = get_engine()
    if engine is None:
        return {"alert_rules": 0, "selection_watch_picks": 0}

    trade_date = payload.get("selection_trade_date") or date.today().isoformat()
    watch_date = payload.get("watch_date") or trade_date
    picks = payload.get("picks") or []
    rules = payload.get("rules") or []

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE selection_watch_picks SET is_active = 0 WHERE watch_date = :wd"),
            {"wd": watch_date},
        )
        pick_n = 0
        for p in picks:
            code = str(p.get("code", ""))
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO selection_watch_picks
                      (selection_trade_date, watch_date, ts_code, name, close_price,
                       change_pct, score, label, action_hint, in_holdings, raw_json, is_active)
                    VALUES
                      (:td, :wd, :code, :name, :close, :pct, :score, :label, :action,
                       :held, :raw, 1)
                    """
                ),
                {
                    "td": trade_date,
                    "wd": watch_date,
                    "code": code,
                    "name": str(p.get("name", code)),
                    "close": p.get("close"),
                    "pct": p.get("change_pct"),
                    "score": p.get("score"),
                    "label": p.get("label"),
                    "action": p.get("action"),
                    "held": 1 if p.get("in_holdings") else 0,
                    "raw": json.dumps(p, ensure_ascii=False),
                },
            )
            pick_n += 1
        rule_n = upsert_alert_rules(rules, source="selection", conn=conn)

    return {"alert_rules": rule_n, "selection_watch_picks": pick_n}


def _parse_selection_trade_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    s = str(value).strip().replace("-", "")
    if len(s) >= 8 and s[:8].isdigit():
        return datetime.strptime(s[:8], "%Y%m%d").date()
    return datetime.fromisoformat(str(value)[:10]).date()


def _code6(code: str) -> str:
    return str(code).split(".")[0].zfill(6)


def _to_ts_code(code: str) -> str:
    code_str = _code6(code)
    if code_str.startswith(("60", "68")):
        return f"{code_str}.SH"
    return f"{code_str}.SZ"


_STOCK_NAME_CACHE: dict[str, str] | None = None
_NAME_CACHE_FILE = STOCK_AI / "output" / "cache" / "stock_name_map.json"
_OPENCLI_NAME_LOOKUP_LIMIT = 128
_MARKET_NAME_CACHE_MIN = 500
_BULK_WARM_ATTEMPTED = False


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _name_needs_enrich(name: str, code: str) -> bool:
    n = (name or "").strip()
    if not n or n == code:
        return True
    if n.isdigit() and len(n) == 6:
        return True
    return not _has_cjk(n)


def _read_disk_name_cache() -> dict[str, str]:
    if not _NAME_CACHE_FILE.is_file():
        return {}
    try:
        data = json.loads(_NAME_CACHE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                _code6(k): str(v).strip()
                for k, v in data.items()
                if _has_cjk(str(v))
            }
    except Exception:
        pass
    return {}


def _write_disk_name_cache(extra: dict[str, str]) -> None:
    if not extra:
        return
    merged = _read_disk_name_cache()
    for code, cn in extra.items():
        c = _code6(code)
        if cn and _has_cjk(cn):
            merged[c] = cn.strip()
    _NAME_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _NAME_CACHE_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _fetch_eastmoney_market_name_cache(*, force: bool = False) -> dict[str, str]:
    """东财 clist 全市场代码→名称，写入本地缓存（Tushare 不可用时的主来源）。"""
    cache = _read_disk_name_cache()
    if len(cache) >= _MARKET_NAME_CACHE_MIN and not force:
        return cache
    try:
        import requests
    except ImportError:
        return cache

    fs = "m:1+t:2,m:1+t:23,m:0+t:6,m:0+t:80,m:0+t:81,m:0+t:82,m:0+t:83"
    prev_no_proxy = os.environ.get("NO_PROXY")
    os.environ["NO_PROXY"] = "*"
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
    merged = dict(cache)
    pn = 1
    pz = 500
    try:
        while pn <= 80:
            try:
                resp = session.get(
                    "https://push2.eastmoney.com/api/qt/clist/get",
                    params={"pn": pn, "pz": pz, "fs": fs, "fields": "f12,f14"},
                    timeout=30,
                )
                resp.raise_for_status()
                payload = resp.json()
            except Exception:
                break
            block = (payload.get("data") or {}).get("diff") or []
            if not block:
                break
            for item in block:
                if not isinstance(item, dict):
                    continue
                code = _code6(str(item.get("f12") or ""))
                name = str(item.get("f14") or "").strip()
                if code and name and _has_cjk(name):
                    merged[code] = name
            total = int((payload.get("data") or {}).get("total") or 0)
            if pn * pz >= total:
                break
            pn += 1
    finally:
        if prev_no_proxy is None:
            os.environ.pop("NO_PROXY", None)
        else:
            os.environ["NO_PROXY"] = prev_no_proxy
    if len(merged) > len(cache):
        _write_disk_name_cache(merged)
    global _STOCK_NAME_CACHE
    _STOCK_NAME_CACHE = None
    return merged


def _fetch_opencli_market_name_cache(*, force: bool = False) -> dict[str, str]:
    """OpenCLI 东财 A 股列表 JSONP 分页（clist HTTP 不可用时的全量兜底）。"""
    cache = _read_disk_name_cache()
    if len(cache) >= _MARKET_NAME_CACHE_MIN and not force:
        return cache
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_market_names_opencli

        print(
            "OpenCLI 东财 A 股列表 DOM 翻页（约 6～8 分钟）…",
            file=sys.stderr,
        )
        fetched = fetch_market_names_opencli(close_browser=True)
    except Exception as exc:  # noqa: BLE001
        print(f"OpenCLI A 股列表失败: {exc}", file=sys.stderr)
        return cache

    merged = dict(cache)
    merged.update(fetched)
    if len(merged) > len(cache):
        _write_disk_name_cache(merged)
    global _STOCK_NAME_CACHE
    _STOCK_NAME_CACHE = None
    print(
        f"OpenCLI A 股列表: +{len(fetched)} 条，合计 {len(merged)} 条",
        file=sys.stderr,
    )
    return merged


def ensure_market_name_cache(*, force: bool = False) -> int:
    """预热代码→中文名缓存（东财 clist → OpenCLI A 股列表 → 逐股补缺）。"""
    _load_dotenv()
    _fetch_eastmoney_market_name_cache(force=force)
    cache = _read_disk_name_cache()
    if len(cache) < _MARKET_NAME_CACHE_MIN:
        cache = _fetch_opencli_market_name_cache(force=force)
    global _STOCK_NAME_CACHE
    _STOCK_NAME_CACHE = cache
    return len(cache)


def _fetch_opencli_names(codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_quotes_opencli

        quotes = fetch_quotes_opencli(codes, close_browser=True)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for code, quote in quotes.items():
        cn = (quote.name or "").strip()
        c = _code6(code)
        if cn and _has_cjk(cn) and cn != c:
            out[c] = cn
    return out


def _fetch_tushare_name_cache(*, refresh: bool = False) -> dict[str, str]:
    """本地名称缓存（Tushare 仅有行情权限，不调用 stock_basic）。"""
    global _STOCK_NAME_CACHE
    if _STOCK_NAME_CACHE is not None and not refresh:
        return _STOCK_NAME_CACHE
    _load_dotenv()
    cache: dict[str, str] = dict(_read_disk_name_cache())
    _STOCK_NAME_CACHE = cache
    return cache


def load_stock_names_by_codes(
    codes: list[str],
    *,
    engine: Engine | None = None,
) -> dict[str, str]:
    """6 位代码 → 中文名（持仓 → 东财全市场缓存 → OpenCLI 补缺）。"""
    normalized: list[str] = []
    for raw in codes:
        code = _code6(raw)
        if re.fullmatch(r"\d{6}", code) and code not in normalized:
            normalized.append(code)
    if not normalized:
        return {}

    global _BULK_WARM_ATTEMPTED
    if not _BULK_WARM_ATTEMPTED and len(_read_disk_name_cache()) < _MARKET_NAME_CACHE_MIN:
        _BULK_WARM_ATTEMPTED = True
        ensure_market_name_cache()

    out: dict[str, str] = {}
    engine = engine or get_engine()
    if engine is not None:
        placeholders = ", ".join(f":c{i}" for i in range(len(normalized)))
        params = {f"c{i}": c for i, c in enumerate(normalized)}
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"SELECT ts_code, name FROM portfolio_positions "
                        f"WHERE is_active = 1 AND ts_code IN ({placeholders})"
                    ),
                    params,
                ).fetchall()
            for row in rows:
                code = _code6(row.ts_code)
                cn = str(row.name or "").strip()
                if cn and _has_cjk(cn):
                    out[code] = cn
        except Exception:
            pass

    try:
        from stock_ai.symbols import CODE_NAMES

        for code in normalized:
            if code in out:
                continue
            cn = (CODE_NAMES.get(code) or "").strip()
            if cn and _has_cjk(cn):
                out[code] = cn
    except Exception:
        pass

    tushare_names = _fetch_tushare_name_cache()
    for code in normalized:
        if code in out:
            continue
        cn = tushare_names.get(code) or tushare_names.get(_to_ts_code(code), "")
        if cn:
            out[code] = cn

    missing = [c for c in normalized if c not in out]
    if missing and len(missing) <= _OPENCLI_NAME_LOOKUP_LIMIT:
        opencli = _fetch_opencli_names(missing)
        out.update(opencli)
        _write_disk_name_cache(opencli)
    return out


def enrich_sop_review_bundle(
    bundle: dict[str, Any] | None,
    *,
    names: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    if not bundle or not bundle.get("items"):
        return bundle
    items = bundle["items"]
    if names is None:
        codes = [_code6(str(it.get("ts_code", ""))) for it in items]
        names = load_stock_names_by_codes(codes)
    for item in items:
        code = _code6(str(item.get("ts_code", item.get("code", ""))))
        item["code"] = code
        cur = str(item.get("name") or "").strip()
        cn = (names or {}).get(code, "")
        if cn and _name_needs_enrich(cur, code):
            item["name"] = cn
    return bundle


def enrich_selection_row_names(
    rows: list[dict[str, Any]],
    *,
    names: dict[str, str] | None = None,
    engine: Engine | None = None,
    force: bool = False,
) -> list[dict[str, Any]]:
    if not rows:
        return rows
    if names is None:
        codes = [_selection_row_code(r) for r in rows]
        names = load_stock_names_by_codes(codes, engine=engine)
    for row in rows:
        code = _selection_row_code(row)
        cur = str(row.get("名称") or row.get("name") or "").strip()
        cn = (names or {}).get(code, "")
        if not cn:
            continue
        if force or _name_needs_enrich(cur, code) or cur != cn:
            row["名称"] = cn
            if "name" in row:
                row["name"] = cn
    return rows


def _selection_row_code(row: dict[str, Any]) -> str:
    return _code6(str(row.get("代码", row.get("code", ""))))


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:  # NaN / inf
            return None
        return value
    if hasattr(value, "item"):
        try:
            return _json_safe_value(value.item())
        except Exception:
            return str(value)
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)


def _json_safe_selection_row(row: dict[str, Any]) -> dict[str, Any]:
    clean = {str(k): _json_safe_value(v) for k, v in row.items()}
    if "代码" in clean and clean["代码"] is not None:
        clean["代码"] = _selection_row_code(clean)
    return clean


def save_selection_daily_results(
    trade_date: date | str,
    rows: list[dict[str, Any]],
    *,
    strategy: str = "combined",
    enrich_names: bool = True,
) -> int:
    """写入选股全量结果：同日 + 同 strategy 先删后插（覆盖）；不同日期或策略保留。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入 selection_daily_results")

    td = _parse_selection_trade_date(trade_date)
    strat = (strategy or "combined").strip() or "combined"
    if rows and enrich_names:
        enrich_selection_row_names(rows, engine=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM selection_daily_results "
                "WHERE trade_date = :d AND strategy = :s"
            ),
            {"d": td.isoformat(), "s": strat},
        )
        n = 0
        if not rows:
            conn.execute(
                text(
                    """
                    INSERT INTO selection_daily_results
                      (trade_date, strategy, ts_code, rank_no, raw_json)
                    VALUES (:td, :strat, '000000', 0, :raw)
                    """
                ),
                {
                    "td": td.isoformat(),
                    "strat": strat,
                    "raw": json.dumps(
                        {"_lane_completed": True, "_candidate_count": 0},
                        ensure_ascii=False,
                    ),
                },
            )
        for rank_no, row in enumerate(rows, 1):
            safe = _json_safe_selection_row(row)
            code = _selection_row_code(safe)
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO selection_daily_results
                      (trade_date, strategy, ts_code, rank_no, close_price, change_pct, total_score,
                       label_count, amount_wan, strategy_label, action_hint, raw_json)
                    VALUES
                      (:td, :strat, :code, :rank, :close, :pct, :score, :lc, :amt, :label, :action, :raw)
                    """
                ),
                {
                    "td": td.isoformat(),
                    "strat": strat,
                    "code": code,
                    "rank": rank_no,
                    "close": safe.get("收盘价"),
                    "pct": safe.get("涨幅%"),
                    "score": safe.get("总分"),
                    "lc": safe.get("标签数"),
                    "amt": safe.get("成交额(万)"),
                    "label": safe.get("策略标签"),
                    "action": safe.get("建议动作"),
                    "raw": json.dumps(safe, ensure_ascii=False),
                },
            )
            n += 1
    return n


def list_selection_trade_dates(
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> list[date]:
    engine = engine or get_engine()
    if engine is None:
        return []
    strat = (strategy or "combined").strip() or "combined"
    if strat.lower() in {"all", "*"}:
        return list_all_selection_trade_dates(engine=engine)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT trade_date
                    FROM selection_daily_results
                    WHERE strategy = :s
                    ORDER BY trade_date DESC
                    """
                ),
                {"s": strat},
            ).fetchall()
    except Exception:
        return []
    out: list[date] = []
    for row in rows:
        val = row.trade_date
        if isinstance(val, date):
            out.append(val)
        else:
            out.append(datetime.fromisoformat(str(val)[:10]).date())
    return out


def list_all_selection_trade_dates(*, engine: Engine | None = None) -> list[date]:
    """任意 strategy 有数据的交易日（合并视图用）。"""
    engine = engine or get_engine()
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT trade_date
                    FROM selection_daily_results
                    ORDER BY trade_date DESC
                    """
                )
            ).fetchall()
    except Exception:
        return []
    out: list[date] = []
    for row in rows:
        val = row.trade_date
        if isinstance(val, date):
            out.append(val)
        else:
            out.append(datetime.fromisoformat(str(val)[:10]).date())
    return out


def list_selection_strategies(*, engine: Engine | None = None) -> list[str]:
    engine = engine or get_engine()
    if engine is None:
        return ["combined"]
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT strategy
                    FROM selection_daily_results
                    ORDER BY strategy
                    """
                )
            ).fetchall()
    except Exception:
        return ["combined"]
    out = [str(r[0]) for r in rows if r[0]]
    return out or ["combined"]


def latest_selection_trade_date(
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> date | None:
    engine = engine or get_engine()
    if engine is None:
        return None
    strat = (strategy or "combined").strip() or "combined"
    try:
        with engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT MAX(trade_date) FROM selection_daily_results "
                    "WHERE strategy = :s"
                ),
                {"s": strat},
            ).scalar()
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def load_selection_daily_results(
    trade_date: date | str | None = None,
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
    enrich_names: bool = True,
) -> tuple[date | None, list[dict[str, Any]]]:
    """读取选股结果，返回与 CSV 列一致的字典列表。"""
    engine = engine or get_engine()
    if engine is None:
        return None, []

    td = _parse_selection_trade_date(trade_date) if trade_date else None
    strat = (strategy or "combined").strip() or "combined"
    sql = """
        SELECT trade_date, raw_json
        FROM selection_daily_results
        WHERE strategy = :strat
    """
    params: dict[str, Any] = {"strat": strat}
    if td is not None:
        sql += " AND trade_date = :d"
        params["d"] = td.isoformat()
    else:
        sql += (
            " AND trade_date = ("
            "SELECT MAX(trade_date) FROM selection_daily_results WHERE strategy = :strat2"
            ")"
        )
        params["strat2"] = strat
    sql += " ORDER BY rank_no"

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return None, []

    if not rows:
        return None, []

    out: list[dict[str, Any]] = []
    resolved = td
    for row in rows:
        if resolved is None and row.trade_date is not None:
            resolved = (
                row.trade_date
                if isinstance(row.trade_date, date)
                else datetime.fromisoformat(str(row.trade_date)[:10]).date()
            )
        raw = row.raw_json
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, dict):
            if raw.get("_lane_completed") is True:
                continue
            out.append(raw)
    if enrich_names:
        out = enrich_selection_row_names(out, engine=engine)
    return resolved, out


def _profile_row_from_dict(item: dict[str, Any]) -> dict[str, Any]:
    code = str(item.get("ts_code") or item.get("code") or "").split(".")[0].zfill(6)
    concepts = item.get("concepts")
    if isinstance(concepts, str):
        try:
            concepts = json.loads(concepts)
        except json.JSONDecodeError:
            concepts = [c.strip() for c in concepts.split(",") if c.strip()]
    if not isinstance(concepts, list):
        concepts = []
    return {
        "code": code,
        "name": (item.get("name") or "").strip() or None,
        "industry": ((item.get("industry") or item.get("所属行业") or "").strip() or None)[:128]
        if (item.get("industry") or item.get("所属行业"))
        else None,
        "concepts": [str(c).strip() for c in concepts if str(c).strip()],
        "profile_text": (item.get("profile_text") or item.get("公司简介") or "").strip() or None,
        "info_text": (item.get("info_text") or "").strip() or None,
        "sectors_text": (item.get("sectors_text") or "").strip() or None,
        "source": (item.get("source") or "eastmoney-opencli").strip() or "eastmoney-opencli",
    }


def upsert_stock_profiles(
    profiles: list[dict[str, Any]],
    *,
    engine: Engine | None = None,
) -> int:
    engine = engine or get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入 stock_profile")
    if not profiles:
        return 0

    n = 0
    with engine.begin() as conn:
        for raw in profiles:
            row = _profile_row_from_dict(raw)
            code = row["code"]
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO stock_profile
                      (ts_code, name, industry, concepts, profile_text, info_text, sectors_text, source)
                    VALUES
                      (:code, :name, :industry, :concepts, :profile_text, :info_text, :sectors_text, :source)
                    ON DUPLICATE KEY UPDATE
                      name = VALUES(name),
                      industry = COALESCE(VALUES(industry), industry),
                      concepts = COALESCE(VALUES(concepts), concepts),
                      profile_text = COALESCE(VALUES(profile_text), profile_text),
                      info_text = COALESCE(VALUES(info_text), info_text),
                      sectors_text = COALESCE(VALUES(sectors_text), sectors_text),
                      source = VALUES(source),
                      updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "code": code,
                    "name": row["name"],
                    "industry": row["industry"],
                    "concepts": json.dumps(row["concepts"], ensure_ascii=False)
                    if row["concepts"]
                    else None,
                    "profile_text": row["profile_text"],
                    "info_text": row["info_text"],
                    "sectors_text": row["sectors_text"],
                    "source": row["source"],
                },
            )
            n += 1
    return n


def load_stock_profiles_by_codes(
    codes: list[str],
    *,
    engine: Engine | None = None,
) -> dict[str, dict[str, Any]]:
    engine = engine or get_engine()
    if engine is None or not codes:
        return {}

    uniq = [
        str(c).split(".")[0].zfill(6)
        for c in dict.fromkeys(str(c).split(".")[0].zfill(6) for c in codes)
    ]
    placeholders = ", ".join(f":c{i}" for i in range(len(uniq)))
    params = {f"c{i}": c for i, c in enumerate(uniq)}
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT ts_code, name, industry, concepts, profile_text, info_text, sectors_text, source, updated_at
                    FROM stock_profile
                    WHERE ts_code IN ({placeholders})
                    """
                ),
                params,
            ).fetchall()
    except Exception:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.ts_code).zfill(6)
        concepts = row.concepts
        if isinstance(concepts, str):
            try:
                concepts = json.loads(concepts)
            except json.JSONDecodeError:
                concepts = []
        out[code] = {
            "ts_code": code,
            "name": row.name,
            "industry": row.industry,
            "concepts": concepts or [],
            "profile_text": row.profile_text,
            "info_text": row.info_text,
            "sectors_text": row.sectors_text,
            "source": row.source,
            "updated_at": str(row.updated_at) if row.updated_at else None,
        }
    return out


def load_industry_map(*, engine: Engine | None = None) -> dict[str, str]:
    """6 位代码 / ts_code → 行业名（OpenCLI enrich 写入的 stock_profile）。"""
    engine = engine or get_engine()
    if engine is None:
        return {}

    out: dict[str, str] = {}

    def _put(code: str, industry: str | None) -> None:
        ind = (industry or "").strip()
        if not ind or ind in {"N/A", "-", "--"}:
            return
        c6 = _code6(code)
        out[c6] = ind
        out[_to_ts_code(c6)] = ind

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT ts_code, industry FROM stock_profile
                    WHERE industry IS NOT NULL AND industry != ''
                    """
                )
            ).fetchall()
        for row in rows:
            _put(str(row.ts_code), str(row.industry))
    except Exception:
        pass

    return out


def is_st_stock_name(name: str) -> bool:
    """ST / *ST 名称识别。"""
    n = (name or "").strip()
    if not n:
        return False
    return bool(re.match(r"^\*?ST", n, re.IGNORECASE))


def load_st_codes_from_names(name_map: dict[str, str] | None = None) -> set[str]:
    """从代码→名称映射中提取 ST 代码集合。"""
    if name_map is None:
        name_map = _fetch_tushare_name_cache()
    st: set[str] = set()
    for code, name in name_map.items():
        if not re.fullmatch(r"\d{6}", str(code)):
            continue
        if is_st_stock_name(str(name)):
            st.add(str(code))
    return st


def load_st_codes(*, engine: Engine | None = None) -> set[str]:
    """ST 代码：东财全市场名称缓存（OpenCLI enrich 前兜底）。"""
    _ = engine
    ensure_market_name_cache()
    return load_st_codes_from_names(_read_disk_name_cache())


def merge_profile_fields_into_selection_row(
    row: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(row)
    industry = profile.get("industry")
    if industry:
        merged["所属行业"] = industry
    concepts = profile.get("concepts") or []
    if concepts:
        merged["概念板块"] = concepts
        merged["概念板块文本"] = "、".join(str(c) for c in concepts)
    profile_text = profile.get("profile_text")
    if profile_text:
        merged["公司简介"] = profile_text
    profile_name = (profile.get("name") or "").strip()
    if profile_name and _has_cjk(profile_name):
        merged["名称"] = profile_name
        merged["name"] = profile_name
    merged["档案来源"] = profile.get("source") or "eastmoney-opencli"
    return merged


def patch_selection_daily_profiles(
    trade_date: date | str,
    profiles_by_code: dict[str, dict[str, Any]],
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> int:
    """将档案字段写回 selection_daily_results.raw_json（按 ts_code 匹配）。"""
    engine = engine or get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法更新 selection_daily_results")
    if not profiles_by_code:
        return 0

    td = _parse_selection_trade_date(trade_date)
    strat = (strategy or "combined").strip() or "combined"
    updated = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT ts_code, raw_json
                FROM selection_daily_results
                WHERE trade_date = :d AND strategy = :s
                ORDER BY rank_no
                """
            ),
            {"d": td.isoformat(), "s": strat},
        ).fetchall()
        for row in rows:
            code = str(row.ts_code).zfill(6)
            profile = profiles_by_code.get(code)
            if not profile:
                continue
            raw = row.raw_json
            if isinstance(raw, str):
                raw = json.loads(raw)
            if not isinstance(raw, dict):
                continue
            merged = merge_profile_fields_into_selection_row(raw, profile)
            conn.execute(
                text(
                    """
                    UPDATE selection_daily_results
                    SET raw_json = :raw
                    WHERE trade_date = :d AND strategy = :s AND ts_code = :code
                    """
                ),
                {
                    "raw": json.dumps(merged, ensure_ascii=False),
                    "d": td.isoformat(),
                    "s": strat,
                    "code": code,
                },
            )
            updated += 1
    return updated


def enrich_selection_profiles_for_date(
    trade_date: date | str | None = None,
    *,
    strategy: str = "combined",
    profiles_by_code: dict[str, dict[str, Any]] | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """upsert stock_profile + 回写当日 selection raw_json。"""
    engine = engine or get_engine()
    td, rows = load_selection_daily_results(trade_date, strategy=strategy, engine=engine)
    if td is None or not rows:
        return {"trade_date": None, "codes": [], "upserted": 0, "patched": 0}

    if profiles_by_code is None:
        return {
            "trade_date": td.isoformat(),
            "codes": [_selection_row_code(r) for r in rows],
            "upserted": 0,
            "patched": 0,
            "error": "profiles_by_code required",
        }

    profile_rows = list(profiles_by_code.values())
    upserted = upsert_stock_profiles(profile_rows, engine=engine)
    patched = patch_selection_daily_profiles(td, profiles_by_code, strategy=strategy, engine=engine)
    return {
        "trade_date": td.isoformat(),
        "codes": sorted(profiles_by_code.keys()),
        "upserted": upserted,
        "patched": patched,
    }


def _best_ts_code_for_daily(code6: str, *, engine: Engine) -> str:
    """stock_daily 存在 6 位与 .SH/.SZ 两套 ts_code 时，取最新交易日更靠后的一套。"""
    seen: set[str] = set()
    candidates: list[str] = []
    for cand in (code6, _to_ts_code(code6)):
        if cand not in seen:
            seen.add(cand)
            candidates.append(cand)
    best = code6
    best_max: date | None = None
    with engine.connect() as conn:
        for cand in candidates:
            mx = conn.execute(
                text("SELECT MAX(trade_date) FROM stock_daily WHERE ts_code = :c"),
                {"c": cand},
            ).scalar()
            if mx is None:
                continue
            if isinstance(mx, str):
                mx_d = datetime.fromisoformat(mx[:10]).date()
            elif isinstance(mx, date):
                mx_d = mx
            else:
                mx_d = datetime.fromisoformat(str(mx)[:10]).date()
            if best_max is None or mx_d > best_max:
                best_max = mx_d
                best = cand
    return best


def load_stock_daily_bars(
    code: str,
    *,
    end_date: date | str | None = None,
    limit: int = 60,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """MySQL stock_daily 日线 K 线（按交易日升序）。"""
    engine = engine or get_engine()
    if engine is None:
        return []

    ts = _code6(code)
    if not re.fullmatch(r"\d{6}", ts):
        return []

    n = max(5, min(int(limit), 250))
    end_d = _parse_selection_trade_date(end_date) if end_date else None
    ts_key = _best_ts_code_for_daily(ts, engine=engine)
    sql = """
        SELECT trade_date, open, high, low, close, pct_chg, vol, amount
        FROM stock_daily
        WHERE ts_code = :code
    """
    params: dict[str, Any] = {"code": ts_key, "n": n}
    if end_d is not None:
        sql += " AND trade_date <= :end"
        params["end"] = end_d.isoformat()
    sql += " ORDER BY trade_date DESC LIMIT :n"

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return []

    bars: list[dict[str, Any]] = []
    for row in reversed(rows):
        td = row.trade_date
        if isinstance(td, date):
            td_str = td.isoformat()
        else:
            td_str = str(td)[:10]
        bars.append(
            {
                "trade_date": td_str,
                "open": float(row.open) if row.open is not None else None,
                "high": float(row.high) if row.high is not None else None,
                "low": float(row.low) if row.low is not None else None,
                "close": float(row.close) if row.close is not None else None,
                "pct_chg": float(row.pct_chg) if row.pct_chg is not None else None,
                "vol": int(row.vol) if row.vol is not None else None,
                "amount": float(row.amount) if row.amount is not None else None,
            }
        )
    return bars


def latest_stock_daily_trade_date(*, engine: Engine | None = None) -> date | None:
    """stock_daily 全市场最新交易日。"""
    engine = engine or get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            value = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).scalar()
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def resolve_selection_kline_end_date(
    selection_trade_date: date | str,
    *,
    engine: Engine | None = None,
) -> date:
    """选股 K 线截止日：至少覆盖选股日，并延伸至已同步的最新交易日。"""
    sel_d = _parse_selection_trade_date(selection_trade_date)
    latest = latest_stock_daily_trade_date(engine=engine)
    if latest is not None and latest > sel_d:
        return latest
    return sel_d


def _snapshot_date(value: date | str | None = None) -> date:
    if value is None:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return _parse_selection_trade_date(value)


def save_portfolio_daily_snapshot(
    *,
    snapshot_date: date | str | None = None,
    snapshot_slot: str = "eod",
    fetch_market_prices: bool = True,
) -> dict[str, Any]:
    """写入账户 + 持仓每日快照（同日同 slot 覆盖）。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入持仓快照")

    snap = _snapshot_date(snapshot_date)
    slot = (snapshot_slot or "eod").strip() or "eod"
    positions = load_positions(engine=engine)
    account = load_account(engine=engine)
    if not positions:
        raise RuntimeError("无活跃持仓，跳过快照")

    closes: dict[str, float] = {}
    if fetch_market_prices:
        closes = load_latest_closes([p.code for p in positions], engine=engine)

    total_mv = 0.0
    total_pnl = 0.0
    pos_rows: list[dict[str, Any]] = []
    for p in positions:
        mp = closes.get(p.code)
        mv = (mp * p.shares) if mp is not None and p.shares else None
        pnl_amt = ((mp - p.cost) * p.shares) if mp is not None and p.shares else None
        pnl_pct = ((mp / p.cost - 1) * 100) if mp is not None and p.cost else None
        if mv is not None:
            total_mv += mv
        if pnl_amt is not None:
            total_pnl += pnl_amt
        pos_rows.append(
            {
                "code": p.code,
                "name": p.name,
                "shares": p.shares,
                "cost": p.cost,
                "mp": mp,
                "mv": mv,
                "pnl_amt": pnl_amt,
                "pnl_pct": pnl_pct,
                "status": p.status,
                "action": p.action,
            }
        )

    acct_total = account.total_assets if account else None
    acct_cash = account.available_cash if account else None
    acct_ratio = account.position_ratio if account else None
    acct_pnl = account.holding_pnl if account else total_pnl

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO portfolio_account_daily
                  (snapshot_date, snapshot_slot, total_assets, available_cash,
                   market_value, position_ratio, holding_pnl)
                VALUES
                  (:d, :slot, :total, :cash, :mv, :ratio, :pnl)
                ON DUPLICATE KEY UPDATE
                  total_assets = VALUES(total_assets),
                  available_cash = VALUES(available_cash),
                  market_value = VALUES(market_value),
                  position_ratio = VALUES(position_ratio),
                  holding_pnl = VALUES(holding_pnl)
                """
            ),
            {
                "d": snap.isoformat(),
                "slot": slot,
                "total": acct_total,
                "cash": acct_cash,
                "mv": total_mv if total_mv else (account.market_value if account else None),
                "ratio": acct_ratio,
                "pnl": acct_pnl,
            },
        )
        conn.execute(
            text(
                "DELETE FROM portfolio_positions_daily "
                "WHERE snapshot_date = :d AND snapshot_slot = :slot"
            ),
            {"d": snap.isoformat(), "slot": slot},
        )
        n = 0
        for row in pos_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO portfolio_positions_daily
                      (snapshot_date, snapshot_slot, ts_code, name, shares, cost_price,
                       market_price, market_value, pnl_amount, pnl_pct, status_note, action_note)
                    VALUES
                      (:d, :slot, :code, :name, :shares, :cost, :mp, :mv, :pnl, :pct, :st, :act)
                    """
                ),
                {
                    "d": snap.isoformat(),
                    "slot": slot,
                    "code": row["code"],
                    "name": row["name"],
                    "shares": row["shares"],
                    "cost": row["cost"],
                    "mp": row["mp"],
                    "mv": row["mv"],
                    "pnl": row["pnl_amt"],
                    "pct": row["pnl_pct"],
                    "st": row["status"],
                    "act": row["action"],
                },
            )
            n += 1
    return {"account": 1, "positions": n, "snapshot_date": snap.isoformat(), "slot": slot}


def save_sop_review_daily(
    trade_date: date | str,
    *,
    strategy: str = "combined",
    selection_source: str | None = None,
    generated_at: datetime | str | None = None,
    wechat_summary: str = "",
    report_path: str | None = None,
    items: list[dict[str, Any]],
) -> dict[str, int]:
    """写入 SOP 审查批次 + 逐股明细（同日同 strategy 覆盖）。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入 sop_review")

    td = _parse_selection_trade_date(trade_date)
    strat = (strategy or "combined").strip() or "combined"
    if generated_at is None:
        gen = datetime.now()
    elif isinstance(generated_at, datetime):
        gen = generated_at
    else:
        gen = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00")[:19])

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM sop_review_items WHERE trade_date = :d AND strategy = :s"),
            {"d": td.isoformat(), "s": strat},
        )
        conn.execute(
            text(
                """
                INSERT INTO sop_review_daily
                  (trade_date, strategy, selection_source, generated_at,
                   wechat_summary, report_path)
                VALUES
                  (:d, :s, :src, :gen, :wx, :rp)
                ON DUPLICATE KEY UPDATE
                  selection_source = VALUES(selection_source),
                  generated_at = VALUES(generated_at),
                  wechat_summary = VALUES(wechat_summary),
                  report_path = VALUES(report_path)
                """
            ),
            {
                "d": td.isoformat(),
                "s": strat,
                "src": selection_source,
                "gen": gen.strftime("%Y-%m-%d %H:%M:%S"),
                "wx": wechat_summary,
                "rp": report_path,
            },
        )
        n = 0
        for item in items:
            code = str(item.get("code", "")).split(".")[0].zfill(6)
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO sop_review_items
                      (trade_date, strategy, rank_no, ts_code, name, score, decision,
                       watch_worthy, close_price, change_pct, strategy_label, action_hint,
                       support_prices, stop_price, target_prices, in_holdings, review_md, raw_json)
                    VALUES
                      (:d, :s, :rank, :code, :name, :score, :dec, :watch, :close, :pct,
                       :label, :action, :sup, :stop, :tgt, :held, :md, :raw)
                    """
                ),
                {
                    "d": td.isoformat(),
                    "s": strat,
                    "rank": int(item.get("rank_no", n + 1)),
                    "code": code,
                    "name": str(item.get("name", code)),
                    "score": item.get("score"),
                    "dec": item.get("decision"),
                    "watch": 1 if item.get("watch_worthy") else 0,
                    "close": item.get("close_price"),
                    "pct": item.get("change_pct"),
                    "label": item.get("strategy_label"),
                    "action": item.get("action_hint"),
                    "sup": json.dumps(item.get("support") or [], ensure_ascii=False),
                    "stop": item.get("stop"),
                    "tgt": json.dumps(item.get("targets") or [], ensure_ascii=False),
                    "held": 1 if item.get("in_holdings") else 0,
                    "md": item.get("review_md"),
                    "raw": json.dumps(item.get("raw_json") or {}, ensure_ascii=False),
                },
            )
            n += 1
    return {"items": n, "trade_date": td.isoformat(), "strategy": strat}


def load_portfolio_snapshot_series(
    *,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    snapshot_slot: str = "eod",
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """看板：账户快照时间序列。"""
    engine = engine or get_engine()
    if engine is None:
        return []
    slot = (snapshot_slot or "eod").strip() or "eod"
    sql = """
        SELECT snapshot_date, snapshot_slot, total_assets, available_cash,
               market_value, position_ratio, holding_pnl, created_at
        FROM portfolio_account_daily
        WHERE snapshot_slot = :slot
    """
    params: dict[str, Any] = {"slot": slot}
    if date_from:
        sql += " AND snapshot_date >= :df"
        params["df"] = _parse_selection_trade_date(date_from).isoformat()
    if date_to:
        sql += " AND snapshot_date <= :dt"
        params["dt"] = _parse_selection_trade_date(date_to).isoformat()
    sql += " ORDER BY snapshot_date"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [dict(r._mapping) for r in rows]


def load_portfolio_positions_on_date(
    snapshot_date: date | str,
    *,
    snapshot_slot: str = "eod",
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    engine = engine or get_engine()
    if engine is None:
        return []
    snap = _parse_selection_trade_date(snapshot_date)
    slot = (snapshot_slot or "eod").strip() or "eod"
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT ts_code, name, shares, cost_price, market_price, market_value,
                       pnl_amount, pnl_pct, status_note, action_note
                FROM portfolio_positions_daily
                WHERE snapshot_date = :d AND snapshot_slot = :slot
                ORDER BY ts_code
                """
            ),
            {"d": snap.isoformat(), "slot": slot},
        ).fetchall()
    return [dict(r._mapping) for r in rows]


def load_sop_review_bundle(
    trade_date: date | str | None = None,
    *,
    strategy: str = "combined",
    engine: Engine | None = None,
) -> dict[str, Any] | None:
    engine = engine or get_engine()
    if engine is None:
        return None
    strat = (strategy or "combined").strip() or "combined"
    with engine.connect() as conn:
        if trade_date:
            td = _parse_selection_trade_date(trade_date)
            header = conn.execute(
                text(
                    """
                    SELECT trade_date, strategy, selection_source, generated_at,
                           wechat_summary, report_path
                    FROM sop_review_daily
                    WHERE trade_date = :d AND strategy = :s
                    """
                ),
                {"d": td.isoformat(), "s": strat},
            ).fetchone()
        else:
            header = conn.execute(
                text(
                    """
                    SELECT trade_date, strategy, selection_source, generated_at,
                           wechat_summary, report_path
                    FROM sop_review_daily
                    WHERE strategy = :s
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """
                ),
                {"s": strat},
            ).fetchone()
        if not header:
            return None
        td_val = header.trade_date
        if not isinstance(td_val, date):
            td_val = datetime.fromisoformat(str(td_val)[:10]).date()
        items = conn.execute(
            text(
                """
                SELECT rank_no, ts_code, name, score, decision, watch_worthy,
                       close_price, change_pct, strategy_label, action_hint,
                       support_prices, stop_price, target_prices, in_holdings, review_md
                FROM sop_review_items
                WHERE trade_date = :d AND strategy = :s
                ORDER BY rank_no
                """
            ),
            {"d": td_val.isoformat(), "s": strat},
        ).fetchall()
    bundle = {
        "header": dict(header._mapping),
        "items": [dict(r._mapping) for r in items],
    }
    return enrich_sop_review_bundle(bundle)


def _json_list_field(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def load_sop_reviews_for_watch(
    trade_date: date | str | None = None,
    *,
    strategy: str = "combined",
) -> list[dict[str, Any]]:
    """监控/战报用 SOP 元数据：MySQL sop_review_items 优先。"""
    bundle = load_sop_review_bundle(trade_date=trade_date, strategy=strategy)
    if not bundle or not bundle.get("items"):
        return []

    reviews: list[dict[str, Any]] = []
    for item in bundle["items"]:
        code = str(item.get("ts_code", "")).split(".")[0].zfill(6)
        reviews.append(
            {
                "code": code,
                "name": item.get("name") or code,
                "score": float(item.get("score") or 0),
                "decision": item.get("decision") or "",
                "watch_worthy": bool(item.get("watch_worthy")),
                "support": _json_list_field(item.get("support_prices")),
                "stop": item.get("stop_price"),
                "targets": _json_list_field(item.get("target_prices")),
                "in_holdings": bool(item.get("in_holdings")),
            }
        )
    return reviews


EMOTION_CYCLE_SLOTS = frozenset({"pre_market", "intraday", "eod"})
EMOTION_CYCLE_PHASES = frozenset({"冰点", "启动", "发酵", "高潮", "分歧", "退潮"})


def _normalize_emotion_slot(slot: str | None) -> str:
    s = (slot or "pre_market").strip() or "pre_market"
    if s not in EMOTION_CYCLE_SLOTS:
        raise ValueError(f"checklist_slot 须为 pre_market|intraday|eod，收到: {s}")
    return s


def save_emotion_cycle_checklist(
    trade_date: date | str,
    header: dict[str, Any],
    *,
    checklist_slot: str = "pre_market",
    dragon_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """写入情绪周期日检（同日同 slot 覆盖 header + 龙头观察池）。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入 emotion_cycle_daily")

    td = _parse_selection_trade_date(trade_date)
    slot = _normalize_emotion_slot(checklist_slot)
    phase = header.get("phase")
    if phase is not None and str(phase).strip() and str(phase) not in EMOTION_CYCLE_PHASES:
        raise ValueError(f"phase 须为 {sorted(EMOTION_CYCLE_PHASES)} 之一")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO emotion_cycle_daily
                  (trade_date, checklist_slot, limit_up_count, limit_down_count,
                   up_down_ratio, max_board_height, limit_up_premium_pct, explode_rate_pct,
                   total_amount_yi, theme_count, phase, phase_vs_yesterday,
                   position_cap_pct, allow_new_open, main_theme, main_theme_is_new,
                   drain_market, action_summary, tomorrow_phase, tomorrow_position_cap_pct,
                   tomorrow_plan, exclude_list, review_notes, raw_json)
                VALUES
                  (:d, :slot, :lu, :ld, :udr, :mbh, :prem, :expl, :amt, :tc, :phase,
                   :pvy, :pcap, :allow, :theme, :theme_new, :drain, :action, :tphase,
                   :tpcap, :tplan, :excl, :rev, :raw)
                ON DUPLICATE KEY UPDATE
                  limit_up_count = VALUES(limit_up_count),
                  limit_down_count = VALUES(limit_down_count),
                  up_down_ratio = VALUES(up_down_ratio),
                  max_board_height = VALUES(max_board_height),
                  limit_up_premium_pct = VALUES(limit_up_premium_pct),
                  explode_rate_pct = VALUES(explode_rate_pct),
                  total_amount_yi = VALUES(total_amount_yi),
                  theme_count = VALUES(theme_count),
                  phase = VALUES(phase),
                  phase_vs_yesterday = VALUES(phase_vs_yesterday),
                  position_cap_pct = VALUES(position_cap_pct),
                  allow_new_open = VALUES(allow_new_open),
                  main_theme = VALUES(main_theme),
                  main_theme_is_new = VALUES(main_theme_is_new),
                  drain_market = VALUES(drain_market),
                  action_summary = VALUES(action_summary),
                  tomorrow_phase = VALUES(tomorrow_phase),
                  tomorrow_position_cap_pct = VALUES(tomorrow_position_cap_pct),
                  tomorrow_plan = VALUES(tomorrow_plan),
                  exclude_list = VALUES(exclude_list),
                  review_notes = VALUES(review_notes),
                  raw_json = VALUES(raw_json)
                """
            ),
            {
                "d": td.isoformat(),
                "slot": slot,
                "lu": header.get("limit_up_count"),
                "ld": header.get("limit_down_count"),
                "udr": header.get("up_down_ratio"),
                "mbh": header.get("max_board_height"),
                "prem": header.get("limit_up_premium_pct"),
                "expl": header.get("explode_rate_pct"),
                "amt": header.get("total_amount_yi"),
                "tc": header.get("theme_count"),
                "phase": phase,
                "pvy": header.get("phase_vs_yesterday"),
                "pcap": header.get("position_cap_pct"),
                "allow": header.get("allow_new_open"),
                "theme": header.get("main_theme"),
                "theme_new": header.get("main_theme_is_new"),
                "drain": header.get("drain_market"),
                "action": header.get("action_summary"),
                "tphase": header.get("tomorrow_phase"),
                "tpcap": header.get("tomorrow_position_cap_pct"),
                "tplan": header.get("tomorrow_plan"),
                "excl": header.get("exclude_list"),
                "rev": header.get("review_notes"),
                "raw": json.dumps(header.get("raw_json") or {}, ensure_ascii=False),
            },
        )
        conn.execute(
            text(
                "DELETE FROM emotion_cycle_dragon_watch "
                "WHERE trade_date = :d AND checklist_slot = :slot"
            ),
            {"d": td.isoformat(), "slot": slot},
        )
        n_dragons = 0
        for rank_no, item in enumerate(dragon_items or [], 1):
            code = str(item.get("ts_code") or item.get("code") or "").split(".")[0].zfill(6)
            if not re.fullmatch(r"\d{6}", code):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO emotion_cycle_dragon_watch
                      (trade_date, checklist_slot, rank_no, ts_code, name, board_height,
                       main_theme, checklist_pass, notes, raw_json)
                    VALUES
                      (:d, :slot, :rank, :code, :name, :bh, :theme, :pass, :notes, :raw)
                    """
                ),
                {
                    "d": td.isoformat(),
                    "slot": slot,
                    "rank": rank_no,
                    "code": code,
                    "name": item.get("name") or "",
                    "bh": item.get("board_height"),
                    "theme": item.get("main_theme"),
                    "pass": item.get("checklist_pass"),
                    "notes": item.get("notes"),
                    "raw": json.dumps(item.get("raw_json") or {}, ensure_ascii=False),
                },
            )
            n_dragons += 1
    return {
        "trade_date": td.isoformat(),
        "checklist_slot": slot,
        "dragon_items": n_dragons,
    }


def load_emotion_cycle_checklist(
    trade_date: date | str | None = None,
    *,
    checklist_slot: str | None = None,
    engine: Engine | None = None,
) -> dict[str, Any] | None:
    """读取情绪周期日检；未指定 trade_date 时取最新一条。"""
    engine = engine or get_engine()
    if engine is None:
        return None

    slot_filter = ""
    params: dict[str, Any] = {}
    if checklist_slot:
        slot = _normalize_emotion_slot(checklist_slot)
        slot_filter = " AND checklist_slot = :slot"
        params["slot"] = slot

    with engine.connect() as conn:
        if trade_date:
            td = _parse_selection_trade_date(trade_date)
            params["d"] = td.isoformat()
            header = conn.execute(
                text(
                    f"""
                    SELECT *
                    FROM emotion_cycle_daily
                    WHERE trade_date = :d{slot_filter}
                    ORDER BY checklist_slot
                    LIMIT 1
                    """
                ),
                params,
            ).fetchone()
        else:
            header = conn.execute(
                text(
                    f"""
                    SELECT *
                    FROM emotion_cycle_daily
                    WHERE 1=1{slot_filter}
                    ORDER BY trade_date DESC, checklist_slot DESC
                    LIMIT 1
                    """
                ),
                params,
            ).fetchone()
        if not header:
            return None
        hdr = dict(header._mapping)
        td_val = hdr["trade_date"]
        if not isinstance(td_val, date):
            td_val = datetime.fromisoformat(str(td_val)[:10]).date()
        slot_val = str(hdr["checklist_slot"])
        dragons = conn.execute(
            text(
                """
                SELECT rank_no, ts_code, name, board_height, main_theme,
                       checklist_pass, notes, raw_json
                FROM emotion_cycle_dragon_watch
                WHERE trade_date = :d AND checklist_slot = :slot
                ORDER BY rank_no
                """
            ),
            {"d": td_val.isoformat(), "slot": slot_val},
        ).fetchall()
    return {
        "header": hdr,
        "dragon_items": [dict(r._mapping) for r in dragons],
    }


def list_emotion_cycle_trade_dates(
    *,
    checklist_slot: str | None = None,
    engine: Engine | None = None,
) -> list[date]:
    engine = engine or get_engine()
    if engine is None:
        return []
    sql = "SELECT DISTINCT trade_date FROM emotion_cycle_daily WHERE 1=1"
    params: dict[str, Any] = {}
    if checklist_slot:
        sql += " AND checklist_slot = :slot"
        params["slot"] = _normalize_emotion_slot(checklist_slot)
    sql += " ORDER BY trade_date DESC"
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception:
        return []
    out: list[date] = []
    for row in rows:
        val = row.trade_date
        if isinstance(val, date):
            out.append(val)
        else:
            out.append(datetime.fromisoformat(str(val)[:10]).date())
    return out


def latest_emotion_trade_date(
    *,
    checklist_slot: str = "eod",
    engine: Engine | None = None,
) -> date | None:
    engine = engine or get_engine()
    if engine is None:
        return None
    try:
        from stock_ai.emotion_cycle_compute import is_intraday_session
        from zoneinfo import ZoneInfo

        if is_intraday_session():
            today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT 1 FROM emotion_cycle_daily "
                        "WHERE trade_date = :d AND checklist_slot = 'intraday' LIMIT 1"
                    ),
                    {"d": today.isoformat()},
                ).fetchone()
            if row:
                return today
    except Exception:
        pass

    dates = list_emotion_cycle_trade_dates(checklist_slot=checklist_slot, engine=engine)
    if dates:
        return dates[0]
    all_dates = list_emotion_cycle_trade_dates(engine=engine)
    return all_dates[0] if all_dates else None


def save_advisor_weekly_review(
    *,
    week_end_date: date | str,
    phase: int,
    title: str,
    health_score: int | None,
    report_md: str,
    report_json: dict[str, Any] | None = None,
    engine: Engine | None = None,
) -> None:
    engine = engine or get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL")
    wd = _parse_selection_trade_date(week_end_date)
    payload = json.dumps(report_json or {}, ensure_ascii=False)
    now = datetime.now().replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO advisor_weekly_reviews
                  (week_end_date, phase, title, health_score, report_md, report_json, created_at)
                VALUES (:d, :phase, :title, :hs, :md, :js, :created)
                ON DUPLICATE KEY UPDATE
                  phase = VALUES(phase),
                  title = VALUES(title),
                  health_score = VALUES(health_score),
                  report_md = VALUES(report_md),
                  report_json = VALUES(report_json),
                  created_at = VALUES(created_at)
                """
            ),
            {
                "d": wd.isoformat(),
                "phase": int(phase),
                "title": (title or "")[:128],
                "hs": health_score,
                "md": report_md,
                "js": payload,
                "created": now,
            },
        )


def list_advisor_weekly_reviews(*, limit: int = 12) -> list[dict[str, Any]]:
    engine = get_engine()
    if engine is None:
        return []
    lim = max(1, min(int(limit), 52))
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT week_end_date, phase, title, health_score,
                           report_md, report_json, created_at
                    FROM advisor_weekly_reviews
                    ORDER BY week_end_date DESC
                    LIMIT :lim
                    """
                ),
                {"lim": lim},
            ).fetchall()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        js = row.report_json
        if isinstance(js, str):
            try:
                js = json.loads(js)
            except Exception:
                js = {}
        out.append(
            {
                "week_end_date": row.week_end_date.isoformat(),
                "phase": int(row.phase),
                "title": row.title or "",
                "health_score": row.health_score,
                "report_md": row.report_md or "",
                "report_json": js or {},
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds")
                if row.created_at
                else None,
            }
        )
    return out


def latest_advisor_weekly_review() -> dict[str, Any] | None:
    rows = list_advisor_weekly_reviews(limit=1)
    return rows[0] if rows else None
