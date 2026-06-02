"""桥接 stock-ai 模块（MySQL 看板数据）。"""

from __future__ import annotations

import json
import plistlib
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.config import ROOT, settings

_TZ = ZoneInfo("Asia/Shanghai")
_LAUNCHD_DIR = ROOT.parent / "launchd"


def _ensure_stock_ai_path() -> Path:
    stock_ai = settings.stock_ai_root
    if not stock_ai.is_dir():
        raise RuntimeError(f"stock-ai 目录不存在: {stock_ai}")
    path = str(stock_ai)
    if path not in sys.path:
        sys.path.insert(0, path)
    return stock_ai


def _load_stock_env() -> None:
    from dotenv import load_dotenv

    stock_ai = settings.stock_ai_root
    load_dotenv(stock_ai / ".env")
    load_dotenv(stock_ai.parent / "stock-mysql" / ".env")


def export_dashboard(
    *,
    snapshot_slot: str = "eod",
    strategy: str = "combined",
    live_quotes: bool = False,
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.dashboard_data import export_dashboard_payload

    return export_dashboard_payload(
        snapshot_slot=snapshot_slot,
        strategy=strategy,
        live_quotes=live_quotes,
    )


def load_current_portfolio() -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import load_account, load_alert_rules, load_positions

    positions = load_positions()
    account = load_account()
    rules = load_alert_rules(source="holdings")
    return {
        "account": {
            "total_assets": account.total_assets if account else None,
            "available_cash": account.available_cash if account else None,
            "market_value": account.market_value if account else None,
            "position_ratio": account.position_ratio if account else None,
            "holding_pnl": account.holding_pnl if account else None,
            "snapshot_date": account.snapshot_date.isoformat()
            if account and account.snapshot_date
            else None,
        },
        "positions": [
            {
                "code": p.code,
                "name": p.name,
                "shares": p.shares,
                "cost": p.cost,
                "status": p.status,
                "action": p.action,
            }
            for p in positions
        ],
        "alert_rules": rules,
    }


def load_monitor_rules(*, live: bool = False) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import load_all_monitor_rules, load_dashboard_closes

    raw_rules = load_all_monitor_rules(today=datetime.now(_TZ).date())
    rules = [_normalize_monitor_rule(r) for r in raw_rules]
    payload: dict[str, Any] = {"rules": rules}

    if not live:
        return payload

    codes = sorted({str(r.get("code", "")).zfill(6) for r in raw_rules if r.get("code")})
    from scripts.monitor.monitor_holdings_alerts import Quote, _format_message, _rule_triggered
    from scripts.tools.portfolio_db import load_monitor_live_quotes

    rows, batch_as_of = load_monitor_live_quotes(codes)
    quote_source = "mysql" if rows else "snapshot"
    qmap: dict[str, Quote] = {
        code: Quote(
            code=code,
            name=str(row.get("name") or ""),
            price=float(row["price"]),
            change_amt=float(row.get("change_amt") or 0.0),
            change_pct=float(row.get("change_pct") or 0.0),
        )
        for code, row in rows.items()
    }

    missing = [c for c in codes if c not in qmap]
    if missing:
        closes = load_dashboard_closes(missing)
        for c, p in closes.items():
            qmap[c] = Quote(code=c, name="", price=p, change_amt=0.0, change_pct=0.0)

    today = datetime.now(_TZ).date()
    state = load_monitor_state(today.isoformat())
    fired_today = set(state.get("fired") or [])
    fired_events = dict(state.get("events") or {})

    for raw, norm in zip(raw_rules, rules, strict=False):
        code = str(raw.get("code", "")).zfill(6)
        q = qmap.get(code)
        rid = str(norm.get("id") or "")
        event = fired_events.get(rid) or {}
        if q is None:
            norm["current_price"] = None
            norm["change_pct"] = None
            norm["triggered_now"] = None
            norm["fired_today"] = rid in fired_today
            if event.get("message"):
                norm["fired_message"] = event["message"]
            continue
        norm["current_price"] = float(q.price)
        norm["change_pct"] = float(q.change_pct)
        norm["triggered_now"] = _rule_triggered(raw, q)
        norm["fired_today"] = rid in fired_today
        if event.get("message"):
            norm["fired_message"] = event["message"]
            norm["fired_at"] = event.get("fired_at")
            norm["fired_price"] = event.get("price")
        elif rid in fired_today:
            from scripts.monitor.monitor_state import describe_legacy_fired

            msg, suspect = describe_legacy_fired(
                raw,
                current_price=float(q.price),
                current_change_pct=float(q.change_pct),
            )
            norm["fired_message"] = msg
            norm["fired_suspect"] = suspect
        try:
            norm["note_live"] = _format_message(raw, q)
        except Exception:  # noqa: BLE001
            norm["note_live"] = norm.get("note") or ""

    payload["quote_source"] = quote_source
    if batch_as_of is not None:
        payload["quotes_as_of"] = batch_as_of.strftime("%Y-%m-%d %H:%M:%S")
    else:
        payload["quotes_as_of"] = datetime.now(_TZ).strftime("%Y-%m-%d %H:%M:%S")
    return payload


def load_monitor_rules_list() -> list[dict[str, Any]]:
    return load_monitor_rules(live=False)["rules"]


def _normalize_monitor_rule(rule: dict[str, Any]) -> dict[str, Any]:
    threshold: str | float | None = None
    if rule.get("price") is not None:
        threshold = float(rule["price"])
    elif rule.get("pct") is not None:
        threshold = float(rule["pct"])
    elif rule.get("low") is not None and rule.get("high") is not None:
        threshold = f"{rule['low']}~{rule['high']}"
    return {
        "id": rule.get("id"),
        "source": rule.get("source", "holdings"),
        "ts_code": rule.get("code") or rule.get("ts_code"),
        "name": rule.get("name", ""),
        "rule_type": rule.get("type") or rule.get("rule_type"),
        "threshold": threshold,
        "note": rule.get("message") or rule.get("note", ""),
    }


def load_monitor_state(date_str: str | None = None) -> dict[str, Any]:
    state_dir = settings.stock_ai_root / "output" / "monitor_state"
    if date_str:
        day = date.fromisoformat(date_str[:10])
    else:
        day = datetime.now(_TZ).date()
    path = state_dir / f"holdings_alerts_{day.isoformat()}.json"
    fired: list[str] = []
    events: dict[str, Any] = {}
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        fired = list(data.get("fired") or [])
        events = dict(data.get("events") or {})
    return {
        "date": day.isoformat(),
        "fired": fired,
        "events": events,
        "fired_details": _enrich_monitor_fired(fired, events),
        "path": str(path),
        "exists": path.is_file(),
    }


def list_monitor_state_dates(*, limit: int = 90) -> list[dict[str, Any]]:
    state_dir = settings.stock_ai_root / "output" / "monitor_state"
    if not state_dir.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(state_dir.glob("holdings_alerts_*.json"), reverse=True):
        name = path.stem.removeprefix("holdings_alerts_")
        try:
            day = date.fromisoformat(name[:10])
        except ValueError:
            continue
        fired: list[str] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            fired = list(data.get("fired") or [])
        except (OSError, json.JSONDecodeError):
            pass
        entries.append(
            {
                "date": day.isoformat(),
                "fired_count": len(fired),
                "fired": fired,
            }
        )
        if len(entries) >= limit:
            break
    return entries


def _enrich_monitor_fired(
    fired_ids: list[str],
    events: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.monitor.monitor_state import describe_legacy_fired, rule_row_from_db
    from scripts.tools.portfolio_db import get_engine, load_monitor_live_quotes
    from sqlalchemy import text

    events = events or {}
    lookup: dict[str, dict[str, Any]] = {}
    engine = get_engine()
    if engine is not None:
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT rule_id, source, ts_code, name, rule_type,
                               price, low_price, high_price, pct_threshold, message_template
                        FROM alert_rules
                        """
                    )
                ).fetchall()
            for row in rows:
                rule = rule_row_from_db(row)
                rule["source"] = row.source
                lookup[str(row.rule_id)] = rule
        except Exception:
            pass

    codes = sorted(
        {
            str((lookup.get(fid) or {}).get("ts_code") or "").zfill(6)
            for fid in fired_ids
            if lookup.get(fid, {}).get("ts_code")
        }
    )
    live_rows, _ = load_monitor_live_quotes(codes)

    out: list[dict[str, Any]] = []
    for fid in fired_ids:
        rule = lookup.get(fid) or {}
        event = events.get(fid) or {}
        ts_code = str(rule.get("ts_code") or rule.get("code") or "").zfill(6)
        suspect = False
        message = event.get("message")
        if not message:
            live = live_rows.get(ts_code) or {}
            current_price = live.get("price")
            current_change_pct = live.get("change_pct")
            message, suspect = describe_legacy_fired(
                rule,
                current_price=float(current_price) if current_price is not None else None,
                current_change_pct=float(current_change_pct)
                if current_change_pct is not None
                else None,
            )
        out.append(
            {
                "id": fid,
                "name": rule.get("name") if rule else "",
                "ts_code": ts_code or "",
                "source": rule.get("source") if rule else "",
                "rule_type": rule.get("rule_type") if rule else "",
                "note": message,
                "fired_at": event.get("fired_at"),
                "fired_price": event.get("price"),
                "change_pct": event.get("change_pct"),
                "suspect": suspect,
            }
        )
    return out


def _is_all_selection_strategy(strategy: str) -> bool:
    return (strategy or "").strip().lower() in {"", "all", "*"}


def _selection_row_sort_key(row: dict[str, Any]) -> tuple[float, ...]:
    def _num(key: str) -> float:
        v = row.get(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return float("-inf")

    return (
        _num("总分"),
        _num("标签数"),
        _num("成交额(万)"),
        _num("形态分(25)"),
        _num("涨幅%"),
    )


def _enrich_selection_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import (
        load_stock_profiles_by_codes,
        merge_profile_fields_into_selection_row,
    )

    codes = [
        str(r.get("代码") or r.get("ts_code") or "").split(".")[0].zfill(6)
        for r in rows
    ]
    profiles = load_stock_profiles_by_codes(codes)
    merged_rows: list[dict[str, Any]] = []
    for row in rows:
        code = str(row.get("代码") or row.get("ts_code") or "").split(".")[0].zfill(6)
        prof = profiles.get(code)
        if prof and (not row.get("所属行业") or not row.get("公司简介")):
            merged_rows.append(merge_profile_fields_into_selection_row(row, prof))
        else:
            merged_rows.append(row)
    return merged_rows


def _selection_history_extras(
    trade_date: str,
    *,
    sop_strategy: str = "combined",
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import (
        enrich_sop_review_bundle,
        load_account,
        load_holding_codes,
        load_sop_review_bundle,
        load_stock_names_by_codes,
    )

    sop = load_sop_review_bundle(trade_date, strategy=sop_strategy)
    if sop and sop.get("items"):
        codes = [
            str(it.get("ts_code") or it.get("code") or "").split(".")[0].zfill(6)
            for it in sop["items"]
        ]
        enrich_sop_review_bundle(sop, names=load_stock_names_by_codes(codes))
    holdings = sorted(load_holding_codes())
    acct = load_account()
    pos_pct = None
    if acct and acct.position_ratio is not None:
        r = float(acct.position_ratio)
        pos_pct = r * 100 if r <= 1.0 else r
    return {
        "sop_review": sop,
        "holding_codes": holdings,
        "account_position_pct": pos_pct,
    }


def _attach_execution_card_buys(
    payload: dict[str, Any],
    *,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from scripts.tools.execution_card_buys import execution_card_buys_from_selection

    holdings = payload.get("holding_codes") or []
    selection_rows = rows if rows is not None else payload.get("rows") or []
    payload["execution_card_buys"] = execution_card_buys_from_selection(
        selection_rows,
        holding_codes=holdings,
    )
    return payload


def list_selection_dates(*, strategy: str = "all") -> list[str]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import (
        list_all_selection_trade_dates,
        list_selection_trade_dates,
    )

    if _is_all_selection_strategy(strategy):
        dates = list_all_selection_trade_dates()
    else:
        dates = list_selection_trade_dates(strategy=strategy)
    return [d.isoformat() for d in dates]


def load_selection_history(
    trade_date: str,
    *,
    strategy: str = "all",
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import (
        load_selection_daily_results,
        list_selection_strategies,
    )

    if _is_all_selection_strategy(strategy):
        td: date | None = None
        merged_rows: list[dict[str, Any]] = []
        for strat in list_selection_strategies():
            td_s, rows = load_selection_daily_results(trade_date, strategy=strat)
            if td is None and td_s is not None:
                td = td_s
            for row in rows:
                tagged = dict(row)
                tagged["strategy"] = strat
                merged_rows.append(tagged)
        merged_rows.sort(key=_selection_row_sort_key, reverse=True)
        rows = _enrich_selection_rows(merged_rows)
        extras = _selection_history_extras(trade_date, sop_strategy="combined")
        return _attach_execution_card_buys(
            {
                "strategy": "all",
                "trade_date": td.isoformat() if td else trade_date,
                "count": len(rows),
                "rows": rows,
                **extras,
            },
            rows=rows,
        )

    td, rows = load_selection_daily_results(trade_date, strategy=strategy)
    rows = _enrich_selection_rows(rows)
    extras = _selection_history_extras(trade_date, sop_strategy=strategy)
    return _attach_execution_card_buys(
        {
            "strategy": strategy,
            "trade_date": td.isoformat() if td else trade_date,
            "count": len(rows),
            "rows": rows,
            **extras,
        },
        rows=rows,
    )


def load_selection_kline(
    code: str,
    trade_date: str,
    *,
    days: int = 60,
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import (
        load_stock_daily_bars,
        resolve_selection_kline_end_date,
    )

    sel_date = trade_date
    end_date = resolve_selection_kline_end_date(trade_date)
    bars = load_stock_daily_bars(code, end_date=end_date, limit=days)
    return {
        "code": str(code).split(".")[0].zfill(6),
        "trade_date": sel_date,
        "kline_end_date": end_date.isoformat(),
        "days": days,
        "count": len(bars),
        "bars": bars,
    }


def list_selection_strategies() -> list[str]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import list_selection_strategies as _list

    return _list()


def load_portfolio_history(
    *,
    days: int = 90,
    snapshot_slot: str = "eod",
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import load_portfolio_snapshot_series

    series = load_portfolio_snapshot_series(snapshot_slot=snapshot_slot)
    if days > 0 and len(series) > days:
        series = series[-days:]
    dates = sorted(
        {
            str(row.get("snapshot_date"))
            for row in series
            if row.get("snapshot_date") is not None
        },
        reverse=True,
    )
    return {
        "snapshot_slot": snapshot_slot,
        "series": [
            {
                "snapshot_date": str(r.get("snapshot_date")),
                "total_assets": _num(r.get("total_assets")),
                "market_value": _num(r.get("market_value")),
                "holding_pnl": _num(r.get("holding_pnl")),
                "position_ratio": _position_ratio_pct(r.get("position_ratio")),
            }
            for r in series
        ],
        "dates": dates,
    }


def load_portfolio_snapshot(
    snapshot_date: str,
    *,
    snapshot_slot: str = "eod",
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import load_portfolio_positions_on_date

    rows = load_portfolio_positions_on_date(snapshot_date, snapshot_slot=snapshot_slot)
    return {
        "snapshot_date": snapshot_date,
        "snapshot_slot": snapshot_slot,
        "positions": [_normalize_snapshot_position(r) for r in rows],
    }


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _position_ratio_pct(value: Any) -> float | None:
    raw = _num(value)
    if raw is None:
        return None
    if raw <= 1.5:
        return raw * 100.0
    return raw


def _normalize_snapshot_position(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts_code": row.get("ts_code"),
        "code": row.get("ts_code"),
        "name": row.get("name"),
        "shares": row.get("shares"),
        "cost_price": _num(row.get("cost_price")),
        "market_price": _num(row.get("market_price")),
        "market_value": _num(row.get("market_value")),
        "pnl_amount": _num(row.get("pnl_amount")),
        "pnl_pct": _num(row.get("pnl_pct")),
        "status_note": row.get("status_note"),
        "action_note": row.get("action_note"),
    }


def load_discipline() -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from sqlalchemy import text

    from scripts.tools.portfolio_db import (
        get_engine,
        load_account,
        load_portfolio_positions_on_date,
        load_portfolio_snapshot_series,
    )

    account = load_account()
    position_ratio = _position_ratio_pct(account.position_ratio) if account else None

    series = load_portfolio_snapshot_series(snapshot_slot="eod")
    positions: list[dict[str, Any]] = []
    if series:
        snap_date = series[-1].get("snapshot_date")
        if snap_date is not None:
            positions = [
                _normalize_snapshot_position(r)
                for r in load_portfolio_positions_on_date(snap_date, snapshot_slot="eod")
            ]

    codes = [str(p.get("ts_code", "")).zfill(6) for p in positions if p.get("ts_code")]
    daily_pct: dict[str, float] = {}
    engine = get_engine()
    if engine is not None and codes:
        placeholders = ", ".join(f":c{i}" for i in range(len(codes)))
        params = {f"c{i}": c for i, c in enumerate(codes)}
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"""
                        SELECT sd.ts_code, sd.pct_chg
                        FROM stock_daily sd
                        INNER JOIN (
                            SELECT MAX(trade_date) AS td FROM stock_daily
                        ) latest ON sd.trade_date = latest.td
                        WHERE sd.ts_code IN ({placeholders})
                        """
                    ),
                    params,
                ).fetchall()
            for row in rows:
                code = str(row.ts_code).zfill(6)
                if row.pct_chg is not None:
                    daily_pct[code] = float(row.pct_chg)
        except Exception:
            pass

    alerts: list[dict[str, Any]] = []
    if position_ratio is not None and position_ratio >= 97:
        alerts.append(
            {
                "level": "danger",
                "title": "仓位红线",
                "message": f"仓位 {position_ratio:.1f}%，不宜新开仓",
                "code": None,
            }
        )

    MEIHUA_BIO_CODE = "600873"
    MEIHUA_BIO_NAME = "梅花生物"

    for pos in positions:
        code = str(pos.get("ts_code", "")).zfill(6)
        name = str(pos.get("name") or (MEIHUA_BIO_NAME if code == MEIHUA_BIO_CODE else code))
        price = pos.get("market_price")

        if code == MEIHUA_BIO_CODE:
            alerts.append(
                {
                    "level": "info",
                    "title": MEIHUA_BIO_NAME,
                    "message": f"{MEIHUA_BIO_NAME}({MEIHUA_BIO_CODE})：严禁补仓（Q1 暴雷，趋势未稳）",
                    "code": code,
                }
            )
            if price is not None and price < 9.0:
                alerts.append(
                    {
                        "level": "danger",
                        "title": f"{MEIHUA_BIO_NAME}止损",
                        "message": f"{MEIHUA_BIO_NAME}({MEIHUA_BIO_CODE}) 现价 {price:.2f} 元 < 9.00，条件：清仓止损",
                        "code": code,
                    }
                )
            elif price is not None and price >= 10.5:
                alerts.append(
                    {
                        "level": "warn",
                        "title": f"{MEIHUA_BIO_NAME}减仓",
                        "message": f"{MEIHUA_BIO_NAME}({MEIHUA_BIO_CODE}) 现价 {price:.2f} 元 ≥ 10.50，条件：减仓 250 股",
                        "code": code,
                    }
                )

        pct = daily_pct.get(code)
        if pct is not None and pct > 5:
            alerts.append(
                {
                    "level": "warn",
                    "title": "禁止追高",
                    "message": f"{name}({code}) 当日涨幅 {pct:.2f}% > 5%，不宜建仓/加仓",
                    "code": code,
                }
            )

    return {
        "position_ratio": position_ratio,
        "alerts": alerts,
        "positions_count": len(positions),
        "as_of": datetime.now(_TZ).isoformat(timespec="seconds"),
    }


def tail_snapshot_alerts(limit: int = 30) -> list[str]:
    log_path = settings.stock_ai_root / "logs" / "snapshot_alerts.log"
    if not log_path.is_file():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def _weekday_label(n: int) -> str:
    labels = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日", 0: "日"}
    return labels.get(n, str(n))


def _format_calendar_interval(item: dict[str, Any]) -> str:
    parts: list[str] = []
    if "Weekday" in item:
        parts.append(f"周{_weekday_label(int(item['Weekday']))}")
    if "Hour" in item:
        minute = int(item.get("Minute", 0))
        parts.append(f"{int(item['Hour']):02d}:{minute:02d}")
    return " ".join(parts) if parts else "定时"


def load_launchd_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    if not _LAUNCHD_DIR.is_dir():
        return jobs

    loaded: set[str] = set()
    try:
        out = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in out.stdout.splitlines()[1:]:
            cols = line.split()
            if len(cols) >= 3:
                loaded.add(cols[2])
    except OSError:
        pass

    for plist in sorted(_LAUNCHD_DIR.glob("com.user.*.plist")):
        try:
            with plist.open("rb") as fh:
                data = plistlib.load(fh)
        except Exception:
            continue

        label = str(data.get("Label", plist.stem))
        args = data.get("ProgramArguments") or []
        entry = str(args[-1]) if args else ""
        schedule = ""
        if "StartCalendarInterval" in data:
            intervals = data["StartCalendarInterval"]
            if isinstance(intervals, dict):
                intervals = [intervals]
            schedule = "；".join(_format_calendar_interval(i) for i in intervals)
        elif "StartInterval" in data:
            sec = int(data["StartInterval"])
            if sec % 60 == 0:
                schedule = f"每 {sec // 60} 分钟"
            else:
                schedule = f"每 {sec} 秒"

        jobs.append(
            {
                "label": label,
                "entry": entry,
                "schedule": schedule or "登录/事件触发",
                "loaded": label in loaded,
                "stdout": data.get("StandardOutPath"),
                "stderr": data.get("StandardErrorPath"),
            }
        )
    return jobs


def find_selection_row(
    trade_date: str,
    strategy: str,
    code: str,
) -> dict[str, Any] | None:
    target = str(code).split(".")[0].zfill(6)
    payload = load_selection_history(trade_date, strategy=strategy)
    for row in payload.get("rows") or []:
        c = str(row.get("代码") or row.get("ts_code") or "").split(".")[0].zfill(6)
        if c == target:
            return row
    return None


def run_selection_sop_single(
    code: str,
    *,
    trade_date: str,
    strategy: str = "combined",
    row: dict[str, Any] | None = None,
    push_wechat: bool = True,
) -> dict[str, Any]:
    """单股东财 SOP + DeepSeek + 可选微信推送。"""
    import os

    _ensure_stock_ai_path()
    _load_stock_env()
    os.environ["PATH"] = os.pathsep.join(
        [
            str(Path.home() / ".local" / "bin"),
            str(Path.home() / ".nvm/versions/node/v24.14.1/bin"),
            os.environ.get("PATH", ""),
        ]
    )
    os.environ.setdefault(
        "OPENCLI_BIN",
        str(Path.home() / ".nvm/versions/node/v24.14.1/bin/opencli"),
    )
    os.environ["MYSQL_URL"] = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal", "127.0.0.1"
    )

    target = str(code).split(".")[0].zfill(6)
    if row is None:
        row = find_selection_row(trade_date, strategy, target)
    if row is None:
        raise ValueError(f"选股列表中未找到 {target}")

    from scripts.analysis.sop_review_single import review_single_and_push_wechat

    day = trade_date.replace("-", "")[:8]
    return review_single_and_push_wechat(
        target,
        row=row,
        trade_date=day,
        push=push_wechat,
    )


def load_news_meta(*, date_str: str | None = None) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.news_db import news_meta

    day = date.fromisoformat(date_str[:10]) if date_str else datetime.now(_TZ).date()
    return news_meta(day=day)


def load_news_items(
    *,
    date_str: str | None = None,
    category: str | None = None,
    sentiment: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.news_db import list_news_items

    day = date.fromisoformat(date_str[:10]) if date_str else datetime.now(_TZ).date()
    cat = category if category in {"geo", "domestic", "other"} else None
    sent = sentiment if sentiment in {"bullish", "bearish", "neutral"} else None
    items = list_news_items(
        day=day,
        category=cat,
        sentiment=sent,
        limit=min(limit, 200),
    )
    return {
        "date": day.isoformat(),
        "category": cat,
        "sentiment": sent,
        "items": items,
    }


def _sanitize_public_briefings(briefings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from scripts.tools.news_ai_interpret import sanitize_public_ai_summary

    out: list[dict[str, Any]] = []
    for row in briefings:
        item = dict(row)
        if item.get("ai_summary"):
            item["ai_summary"] = sanitize_public_ai_summary(str(item["ai_summary"]))
        out.append(item)
    return out


def load_news_briefings(*, date_str: str | None = None) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.news_db import list_briefing_snapshots

    day = date.fromisoformat(date_str[:10]) if date_str else datetime.now(_TZ).date()
    briefings = _sanitize_public_briefings(list_briefing_snapshots(day=day))
    return {"date": day.isoformat(), "briefings": briefings}


def load_latest_briefing() -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.news_db import latest_briefing_snapshot

    row = latest_briefing_snapshot()
    if row and row.get("ai_summary"):
        row = dict(row)
        from scripts.tools.news_ai_interpret import sanitize_public_ai_summary

        row["ai_summary"] = sanitize_public_ai_summary(str(row["ai_summary"]))
    return {"briefing": row}


def _emotion_json_value(value: Any) -> Any:
    from decimal import Decimal

    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _normalize_emotion_bundle(bundle: dict[str, Any] | None) -> dict[str, Any] | None:
    if not bundle:
        return None
    header = bundle.get("header")
    if header is None:
        return None
    hdr = {k: _emotion_json_value(v) for k, v in dict(header).items()}
    dragons = []
    for item in bundle.get("dragon_items") or []:
        row = {k: _emotion_json_value(v) for k, v in dict(item).items()}
        dragons.append(row)
    return {"header": hdr, "dragon_items": dragons}


def list_emotion_cycle_dates() -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import (
        latest_emotion_trade_date,
        list_emotion_cycle_trade_dates,
    )

    all_dates = [d.isoformat() for d in list_emotion_cycle_trade_dates()]
    default = latest_emotion_trade_date(checklist_slot="eod")
    return {
        "dates": all_dates,
        "default_date": default.isoformat() if default else (all_dates[0] if all_dates else None),
    }


def _build_dragon_execution_card(header: dict[str, Any] | None) -> dict[str, Any] | None:
    if not header:
        return None
    phase = str(header.get("phase") or "").strip()
    allow_raw = header.get("allow_new_open")
    allow_new = allow_raw in (1, True, "1", "true", "True")
    premium = header.get("limit_up_premium_pct")
    explode = header.get("explode_rate_pct")
    cap = header.get("position_cap_pct")

    phase_no_open = phase in ("冰点", "退潮")
    phase_can_open = phase in ("启动", "发酵", "高潮")
    premium_ok = premium is None or float(premium) >= 1.0
    explode_ok = explode is None or float(explode) < 40.0

    allow_buy = (
        phase_can_open
        and allow_new
        and premium_ok
        and explode_ok
        and not phase_no_open
    )

    if phase_no_open:
        p0 = f"P0 阶段 gate：{phase} — 禁止新开，有仓应清"
    elif phase == "分歧":
        p0 = "P0 阶段 gate：分歧 — 禁止新开，只留核心龙"
    elif allow_buy:
        p0 = f"P0 阶段 gate：{phase} — 允许仿真试探（见龙头池）"
    else:
        p0 = f"P0 阶段 gate：{phase} — 禁止新开（指标未过关）"

    return {
        "scope": "simulation_only",
        "title": "龙头执行卡",
        "mysql_tables": ["emotion_cycle_daily", "emotion_cycle_dragon_watch"],
        "schedule": "盘中 5min · 09:26 pre_market · 17:10 eod",
        "p0_gate": p0,
        "operation": header.get("action_summary"),
        "position_cap_pct": cap,
        "allow_new_open": allow_new,
        "allow_buy": allow_buy,
        "force_exit": phase_no_open,
        "exclude_list": header.get("exclude_list"),
        "main_theme": header.get("main_theme"),
        "conflict_note": "实盘与主账户以持仓执行卡为准（看板 /portfolio）",
    }


def _attach_dragon_execution_card(payload: dict[str, Any]) -> dict[str, Any]:
    hdr: dict[str, Any] | None = None
    rec = payload.get("record")
    if isinstance(rec, dict) and rec.get("header"):
        hdr = rec["header"]
    payload["data_source"] = {
        "kind": "mysql",
        "tables": ["emotion_cycle_daily", "emotion_cycle_dragon_watch"],
        "schedule": "盘中 5min · 09:26 pre_market · 17:10 eod (intraday launchd)",
    }
    payload["dragon_execution_card"] = _build_dragon_execution_card(hdr)
    return payload


def load_emotion_cycle(
    trade_date: str | None = None,
    *,
    checklist_slot: str | None = None,
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import load_emotion_cycle_checklist

    dates = list_emotion_cycle_dates()
    eod_dates = dates.get("dates") or []

    if trade_date:
        td = trade_date[:10]
        if checklist_slot:
            bundle = load_emotion_cycle_checklist(td, checklist_slot=checklist_slot)
            return _attach_dragon_execution_card({
                "dates": eod_dates,
                "default_date": dates.get("default_date"),
                "trade_date": td,
                "checklist_slot": checklist_slot,
                "record": _normalize_emotion_bundle(bundle),
            })
        pre = _normalize_emotion_bundle(
            load_emotion_cycle_checklist(td, checklist_slot="pre_market")
        )
        intraday = _normalize_emotion_bundle(
            load_emotion_cycle_checklist(td, checklist_slot="intraday")
        )
        eod = _normalize_emotion_bundle(
            load_emotion_cycle_checklist(td, checklist_slot="eod")
        )
        active = intraday or pre or eod
        return _attach_dragon_execution_card({
            "dates": eod_dates,
            "default_date": dates.get("default_date"),
            "trade_date": td,
            "pre_market": pre,
            "intraday": intraday,
            "eod": eod,
            "record": active,
            "checklist_slot": (
                str(active["header"].get("checklist_slot"))
                if active and active.get("header")
                else None
            ),
        })

    slot = checklist_slot or "intraday"
    from stock_ai.emotion_cycle_compute import is_intraday_session

    if slot == "intraday" and is_intraday_session():
        td_today = datetime.now(_TZ).date().isoformat()
        intraday = _normalize_emotion_bundle(
            load_emotion_cycle_checklist(td_today, checklist_slot="intraday")
        )
        if intraday:
            return _attach_dragon_execution_card({
                "dates": eod_dates,
                "default_date": dates.get("default_date"),
                "trade_date": td_today,
                "intraday": intraday,
                "record": intraday,
                "checklist_slot": "intraday",
            })
        slot = "eod"

    bundle = load_emotion_cycle_checklist(checklist_slot=slot)
    if not bundle and slot == "eod":
        bundle = load_emotion_cycle_checklist(checklist_slot="pre_market")
    normalized = _normalize_emotion_bundle(bundle)
    td_out = dates.get("default_date")
    slot_out = slot
    if normalized and normalized.get("header"):
        hdr = normalized["header"]
        td_out = str(hdr.get("trade_date", ""))[:10] or td_out
        slot_out = str(hdr.get("checklist_slot") or slot_out or "")
    return _attach_dragon_execution_card({
        "dates": eod_dates,
        "default_date": dates.get("default_date"),
        "trade_date": td_out,
        "checklist_slot": slot_out,
        "record": normalized,
    })
