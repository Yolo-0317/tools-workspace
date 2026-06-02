"""盘中监控触发状态（JSON 文件 + 看板展示）。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / "output" / "monitor_state"


def state_file(day: date) -> Path:
    return STATE_DIR / f"holdings_alerts_{day.isoformat()}.json"


def load_state(day: date) -> tuple[set[str], dict[str, dict[str, Any]]]:
    path = state_file(day)
    if not path.exists():
        return set(), {}
    data = json.loads(path.read_text(encoding="utf-8"))
    fired = set(data.get("fired") or [])
    events = dict(data.get("events") or {})
    return fired, events


def save_state(day: date, fired: set[str], events: dict[str, dict[str, Any]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": day.isoformat(),
        "fired": sorted(fired),
        "events": {k: events[k] for k in sorted(fired) if k in events},
    }
    state_file(day).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def rule_row_from_db(row: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "id": row.rule_id,
        "code": str(row.ts_code).zfill(6),
        "ts_code": str(row.ts_code).zfill(6),
        "name": row.name or "",
        "type": row.rule_type,
        "rule_type": row.rule_type,
        "message": row.message_template or "",
        "note": row.message_template or "",
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


def rule_is_satisfied(rule: dict[str, Any], *, price: float, change_pct: float = 0.0) -> bool:
    rtype = rule.get("type") or rule.get("rule_type")
    if rtype == "price_below":
        return price < float(rule["price"])
    if rtype == "price_above":
        return price >= float(rule["price"])
    if rtype == "price_in_range":
        return float(rule["low"]) <= price <= float(rule["high"])
    if rtype == "daily_pct_above":
        return change_pct > float(rule["pct"])
    return False


def fired_summary_from_rule(rule: dict[str, Any]) -> str:
    name = str(rule.get("name") or "")
    code = str(rule.get("code") or rule.get("ts_code") or "").zfill(6)
    rtype = rule.get("type") or rule.get("rule_type") or ""

    if rtype == "price_below" and rule.get("price") is not None:
        return f"⚠️ {name}({code}) 今日曾触发：跌破 {float(rule['price']):.2f} 元保护线"
    if rtype == "price_above" and rule.get("price") is not None:
        return f"📌 {name}({code}) 今日曾触发：涨破 {float(rule['price']):.2f} 元"
    if rtype == "price_in_range" and rule.get("low") is not None and rule.get("high") is not None:
        return (
            f"📌 {name}({code}) 今日曾触发：进入 "
            f"{float(rule['low']):.2f}~{float(rule['high']):.2f} 元区间"
        )
    if rtype == "daily_pct_above" and rule.get("pct") is not None:
        return f"⚠️ {name}({code}) 今日曾触发：涨幅超过 {float(rule['pct']):.2f}%"
    template = str(rule.get("message") or rule.get("note") or "").strip()
    return template.replace("{price}", "—").replace("{pct}", "—") or f"{name}({code}) 今日曾触发"


def describe_legacy_fired(
    rule: dict[str, Any],
    *,
    current_price: float | None = None,
    current_change_pct: float | None = None,
) -> tuple[str, bool]:
    """无 events 时的展示文案；返回 (note, suspect)。"""
    summary = fired_summary_from_rule(rule)
    suspect = False
    if current_price is not None:
        change_pct = current_change_pct if current_change_pct is not None else 0.0
        if not rule_is_satisfied(rule, price=current_price, change_pct=change_pct):
            suspect = True
            return (
                f"{summary}。"
                f"现价 {current_price:.2f} 元已不满足条件，"
                f"该记录可能为误触发（无触发价存档）。",
                True,
            )
    return f"{summary}（触发价未记录）", suspect


def prune_suspect_fired(
    fired: set[str],
    events: dict[str, dict[str, Any]],
    rules: list[dict[str, Any]],
    quotes: dict[str, Any],
) -> list[str]:
    """移除无 events 且当前行情不满足条件的误触发 id。"""
    rule_by_id = {str(r.get("id") or ""): r for r in rules if r.get("id")}
    removed: list[str] = []

    for rid in list(fired):
        if rid in events:
            continue
        rule = rule_by_id.get(rid)
        if not rule:
            continue
        code = str(rule.get("code", "")).zfill(6)
        quote = quotes.get(code)
        if quote is None:
            continue
        price = getattr(quote, "price", None) if not isinstance(quote, dict) else quote.get("price")
        change_pct = (
            getattr(quote, "change_pct", 0.0)
            if not isinstance(quote, dict)
            else quote.get("change_pct", 0.0)
        )
        if price is None:
            continue
        if not rule_is_satisfied(rule, price=float(price), change_pct=float(change_pct or 0.0)):
            fired.discard(rid)
            events.pop(rid, None)
            removed.append(rid)
    return removed
