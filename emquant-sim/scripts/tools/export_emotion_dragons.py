#!/usr/bin/env python3
"""从 MySQL 情绪周期龙头观察池导出 dragons.json（供 Win11 dragon_main.py）。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from scripts._bootstrap import ensure_paths, import_stock_ai_module, stock_ai_root

ensure_paths()

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "output" / "emquant" / "dragons.json"

HEADER_KEYS = (
    "trade_date",
    "checklist_slot",
    "limit_up_count",
    "limit_down_count",
    "max_board_height",
    "limit_up_premium_pct",
    "explode_rate_pct",
    "total_amount_yi",
    "theme_count",
    "phase",
    "phase_vs_yesterday",
    "position_cap_pct",
    "allow_new_open",
    "main_theme",
    "main_theme_is_new",
    "drain_market",
    "action_summary",
    "exclude_list",
    "tomorrow_phase",
    "tomorrow_position_cap_pct",
    "tomorrow_plan",
)


def _json_val(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _normalize_header(header: dict) -> dict:
    out: dict[str, object] = {}
    for key in HEADER_KEYS:
        if key in header:
            out[key] = _json_val(header[key])
    if "trade_date" in header and "trade_date" not in out:
        out["trade_date"] = _json_val(header["trade_date"])
    return out


def _normalize_dragons(items: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in items:
        code = str(item.get("ts_code") or item.get("code") or "").split(".")[0].zfill(6)
        if not code.isdigit() or len(code) != 6:
            continue
        rows.append(
            {
                "rank_no": int(item.get("rank_no") or len(rows) + 1),
                "ts_code": code,
                "name": str(item.get("name") or ""),
                "board_height": _json_val(item.get("board_height")),
                "main_theme": str(item.get("main_theme") or ""),
                "checklist_pass": _json_val(item.get("checklist_pass")),
                "notes": str(item.get("notes") or ""),
            }
        )
    return rows


def _default_export_slot() -> str:
    try:
        mod = import_stock_ai_module("stock_ai/emotion_cycle_compute.py")
        if mod.is_intraday_session():
            return "intraday"
    except Exception:
        pass
    return "eod"


def load_bundle(
    *,
    trade_date: str | None,
    checklist_slot: str,
) -> tuple[dict, list[dict], str]:
    portfolio_db = import_stock_ai_module("scripts/tools/portfolio_db.py")
    load_dotenv(stock_ai_root() / ".env")
    load_dotenv(stock_ai_root().parent / "stock-mysql" / ".env")

    td = trade_date
    slot = checklist_slot
    if not td:
        latest = portfolio_db.latest_emotion_trade_date(checklist_slot=slot)
        if latest is None:
            raise RuntimeError("emotion_cycle_daily 无记录，请先 sync_emotion_cycle")
        td = latest.isoformat()

    bundle = portfolio_db.load_emotion_cycle_checklist(td, checklist_slot=slot)
    if not bundle:
        for fallback in ("intraday", "eod", "pre_market"):
            if fallback == slot:
                continue
            bundle = portfolio_db.load_emotion_cycle_checklist(td, checklist_slot=fallback)
            if bundle:
                break
    if not bundle or not bundle.get("header"):
        raise RuntimeError(f"未找到 {td} slot={checklist_slot} 的情绪日检")

    header = _normalize_header(dict(bundle["header"]))
    dragons = _normalize_dragons(list(bundle.get("dragon_items") or []))
    return header, dragons, str(header.get("trade_date") or td)[:10]


def main() -> int:
    parser = argparse.ArgumentParser(description="导出情绪周期龙头池 → dragons.json")
    parser.add_argument("--date", help="交易日 YYYY-MM-DD，默认最新 eod")
    parser.add_argument(
        "--slot",
        default=None,
        choices=["pre_market", "intraday", "eod"],
        help="默认：盘中 intraday，否则 eod",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slot = args.slot or _default_export_slot()
    try:
        header, dragons, td = load_bundle(trade_date=args.date, checklist_slot=slot)
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    payload = {
        "version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": "mysql:emotion_cycle_daily+emotion_cycle_dragon_watch",
        "trade_date": td,
        "checklist_slot": slot,
        "header": header,
        "dragon_items": dragons,
    }

    phase = header.get("phase")
    print(f"交易日 {td} slot={slot} phase={phase} 龙头 {len(dragons)} 只")
    for row in dragons:
        print(
            f"  #{row['rank_no']} {row['ts_code']} {row['name']} "
            f"{row.get('board_height')}板 pass={row.get('checklist_pass')}"
        )

    if args.dry_run:
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
