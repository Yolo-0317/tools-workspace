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
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.dashboard_data import export_dashboard_payload

    return export_dashboard_payload(snapshot_slot=snapshot_slot, strategy=strategy)


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


def load_monitor_rules() -> list[dict[str, Any]]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import load_all_monitor_rules

    rules = load_all_monitor_rules(today=datetime.now(_TZ).date())
    return [_normalize_monitor_rule(r) for r in rules]


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
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        fired = list(data.get("fired") or [])
    return {
        "date": day.isoformat(),
        "fired": fired,
        "fired_details": _enrich_monitor_fired(fired),
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


def _enrich_monitor_fired(fired_ids: list[str]) -> list[dict[str, Any]]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import get_engine
    from sqlalchemy import text

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
                lookup[str(row.rule_id)] = {
                    "id": row.rule_id,
                    "source": row.source,
                    "ts_code": str(row.ts_code).zfill(6),
                    "name": row.name or "",
                    "rule_type": row.rule_type,
                    "note": row.message_template or "",
                }
        except Exception:
            pass

    out: list[dict[str, Any]] = []
    for fid in fired_ids:
        rule = lookup.get(fid)
        out.append(
            {
                "id": fid,
                "name": rule.get("name") if rule else "",
                "ts_code": rule.get("ts_code") if rule else "",
                "source": rule.get("source") if rule else "",
                "rule_type": rule.get("rule_type") if rule else "",
                "note": rule.get("note") if rule else "",
            }
        )
    return out


def list_selection_dates(*, strategy: str = "combined") -> list[str]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import list_selection_trade_dates

    return [d.isoformat() for d in list_selection_trade_dates(strategy=strategy)]


def load_selection_history(
    trade_date: str,
    *,
    strategy: str = "combined",
) -> dict[str, Any]:
    _ensure_stock_ai_path()
    _load_stock_env()
    from scripts.tools.portfolio_db import (
        load_holding_codes,
        load_selection_daily_results,
        load_sop_review_bundle,
        load_stock_names_by_codes,
        load_stock_profiles_by_codes,
        merge_profile_fields_into_selection_row,
        enrich_sop_review_bundle,
    )

    td, rows = load_selection_daily_results(trade_date, strategy=strategy)
    if rows:
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
        rows = merged_rows
    sop = load_sop_review_bundle(trade_date, strategy=strategy)
    if sop and sop.get("items"):
        codes = [
            str(it.get("ts_code") or it.get("code") or "").split(".")[0].zfill(6)
            for it in sop["items"]
        ]
        enrich_sop_review_bundle(sop, names=load_stock_names_by_codes(codes))
    holdings = sorted(load_holding_codes())
    return {
        "strategy": strategy,
        "trade_date": td.isoformat() if td else trade_date,
        "count": len(rows),
        "rows": rows,
        "sop_review": sop,
        "holding_codes": holdings,
    }


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
