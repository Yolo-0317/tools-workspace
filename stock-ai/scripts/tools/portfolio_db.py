#!/usr/bin/env python3
"""持仓与监控规则 MySQL 读写（权威数据源；选股见 selection_daily_results）。"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
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


def mysql_url() -> str:
    _load_dotenv()
    url = os.environ.get("MYSQL_URL", "")
    if not url:
        user = os.environ.get("MYSQL_USER", "stock")
        password = os.environ.get("MYSQL_PASSWORD", "")
        db = os.environ.get("MYSQL_DATABASE", "stock_data")
        url = f"mysql+pymysql://{user}:{password}@127.0.0.1:3306/{db}"
    return url.replace("host.docker.internal", "127.0.0.1")


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
    selection = load_active_selection_rules(today=today, engine=engine)
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


def _selection_row_code(row: dict[str, Any]) -> str:
    return str(row.get("代码", "")).split(".")[0].zfill(6)


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
) -> int:
    """写入选股全量结果：同日 + 同 strategy 先删后插（覆盖）；不同日期或策略保留。"""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入 selection_daily_results")

    td = _parse_selection_trade_date(trade_date)
    strat = (strategy or "combined").strip() or "combined"
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM selection_daily_results "
                "WHERE trade_date = :d AND strategy = :s"
            ),
            {"d": td.isoformat(), "s": strat},
        )
        n = 0
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
        return td, []

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
            out.append(raw)
    return resolved, out


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
    return {
        "header": dict(header._mapping),
        "items": [dict(r._mapping) for r in items],
    }


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

