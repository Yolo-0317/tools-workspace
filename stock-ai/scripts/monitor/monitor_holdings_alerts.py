#!/usr/bin/env python3
"""持仓盘中条件监控：从 MySQL alert_rules 读取规则，触发时推微信。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.fetch_eastmoney_quotes import EastmoneyQuote, fetch_quotes

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / "output" / "monitor_state"
TZ = ZoneInfo("Asia/Shanghai")


@dataclass
class Quote:
    code: str
    name: str
    price: float
    change_amt: float
    change_pct: float


def _is_trading_time(now: datetime | None = None) -> bool:
    now = now or datetime.now(TZ)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (time(9, 30) <= t <= time(11, 30)) or (time(13, 0) <= t <= time(15, 0))


def _to_quote(em: EastmoneyQuote) -> Quote:
    return Quote(
        code=em.code,
        name=em.name,
        price=em.price,
        change_amt=em.change_amt,
        change_pct=em.change_pct,
    )


def fetch_holdings_quotes(codes: list[str]) -> dict[str, Quote]:
    em_quotes = fetch_quotes(codes)
    return {code: _to_quote(q) for code, q in em_quotes.items()}


def _load_all_rules() -> list[dict]:
    from scripts.tools.portfolio_db import load_all_monitor_rules

    return load_all_monitor_rules(today=datetime.now(TZ).date())


def _state_file(day: date) -> Path:
    return STATE_DIR / f"holdings_alerts_{day.isoformat()}.json"


def _load_state(day: date) -> set[str]:
    path = _state_file(day)
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("fired", []))


def _save_state(day: date, fired: set[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_file(day).write_text(
        json.dumps({"date": day.isoformat(), "fired": sorted(fired)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _rule_triggered(rule: dict, quote: Quote) -> bool:
    rtype = rule.get("type")
    price = quote.price
    if rtype == "price_below":
        return price < float(rule["price"])
    if rtype == "price_above":
        return price >= float(rule["price"])
    if rtype == "price_in_range":
        return float(rule["low"]) <= price <= float(rule["high"])
    if rtype == "daily_pct_above":
        return quote.change_pct > float(rule["pct"])
    return False


def _format_message(rule: dict, quote: Quote) -> str:
    msg = rule.get("message", "")
    return msg.format(price=quote.price, pct=quote.change_pct, name=quote.name)


def evaluate_rules(
    rules: list[dict],
    quotes: dict[str, Quote],
    *,
    fired: set[str],
    repeat: bool = False,
) -> list[tuple[str, str]]:
    alerts: list[tuple[str, str]] = []
    for rule in rules:
        rule_id = str(rule.get("id") or "")
        code = str(rule.get("code", "")).zfill(6)
        quote = quotes.get(code)
        if not quote or not rule_id:
            continue
        if not _rule_triggered(rule, quote):
            continue
        if not repeat and rule_id in fired:
            continue
        alerts.append((rule_id, _format_message(rule, quote)))
        fired.add(rule_id)
    return alerts


def push_wechat(text: str) -> None:
    from scripts.tools.wechat_acp_push_text import send_wechat_acp_text

    send_wechat_acp_text(text)


def run_once(*, push: bool, repeat: bool, force: bool) -> int:
    now = datetime.now(TZ)
    if not force and not _is_trading_time(now):
        print(f"非交易时段，跳过 ({now.strftime('%Y-%m-%d %H:%M')})")
        return 0

    rules = _load_all_rules()
    if not rules:
        print("❌ MySQL 无监控规则。请先运行 sync_portfolio_from_card", file=sys.stderr)
        return 1

    codes = sorted({str(r["code"]).zfill(6) for r in rules})
    try:
        quotes = fetch_holdings_quotes(codes)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 东财行情抓取失败: {exc}", file=sys.stderr)
        return 1
    if not quotes:
        print("❌ 未获取到东财行情", file=sys.stderr)
        return 1

    fired = _load_state(now.date())
    alerts = evaluate_rules(rules, quotes, fired=fired, repeat=repeat)
    _save_state(now.date(), fired)

    if not alerts:
        print(f"OK 无触发 ({now.strftime('%H:%M:%S')}) [东财 opencli]")
        for code in codes:
            q = quotes.get(code)
            if q:
                print(f"  {q.name}({code}): {q.price} ({q.change_pct:+.2f}%)")
        return 0

    body = "\n\n".join(msg for _, msg in alerts)
    header = f"【盘中监控】{now.strftime('%H:%M:%S')}\n"
    full = header + body
    print(full)

    if push:
        try:
            push_wechat(full)
            print("✅ 已推送微信", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ 推送失败: {exc}", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="持仓盘中条件监控（MySQL alert_rules）")
    parser.add_argument("--push", action="store_true", help="触发时推微信")
    parser.add_argument("--repeat", action="store_true", help="允许同日重复推送同一规则")
    parser.add_argument("--force", action="store_true", help="忽略交易时段检查")
    args = parser.parse_args()

    if args.push:
        instance = os.getenv("WECHAT_ACP_INSTANCE", "tools-workspace")
        token = Path.home() / ".wechat-acp" / "instances" / instance / "token.json"
        if not token.exists():
            print(f"❌ 未找到 wechat-acp token: {token}", file=sys.stderr)
            return 1

    return run_once(push=args.push, repeat=args.repeat, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
