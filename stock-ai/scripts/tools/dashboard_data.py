#!/usr/bin/env python3
"""看板数据：持仓每日快照、SOP 入库、JSON 导出。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
SOP_JSON_LATEST = ROOT / "output" / "sop_review_latest.json"
SNAPSHOT_ALERT_LOG = ROOT / "logs" / "snapshot_alerts.log"


def log_snapshot_alert(message: str) -> None:
    SNAPSHOT_ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}\n"
    with SNAPSHOT_ALERT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)


def export_dashboard_payload(
    *,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    snapshot_slot: str = "eod",
    strategy: str = "combined",
) -> dict[str, Any]:
    from scripts.tools.portfolio_db import (
        latest_selection_trade_date,
        load_portfolio_positions_on_date,
        load_portfolio_snapshot_series,
        load_selection_daily_results,
        load_sop_review_bundle,
    )
    from scripts.tools.selection_results import resolve_selection_df, trade_date_to_str

    account_series = load_portfolio_snapshot_series(
        date_from=date_from,
        date_to=date_to,
        snapshot_slot=snapshot_slot,
    )

    sel_td = latest_selection_trade_date(strategy=strategy)
    selection_rows: list[dict] = []
    if sel_td:
        _, selection_rows = load_selection_daily_results(sel_td, strategy=strategy)

    sop = load_sop_review_bundle(strategy=strategy)

    latest_snap_date = account_series[-1]["snapshot_date"] if account_series else None
    positions_latest: list[dict] = []
    if latest_snap_date:
        positions_latest = load_portfolio_positions_on_date(
            latest_snap_date,
            snapshot_slot=snapshot_slot,
        )

    try:
        td, sel_df, sel_src = resolve_selection_df(strategy=strategy)
        selection_summary = {
            "trade_date": trade_date_to_str(td),
            "source": sel_src,
            "count": len(sel_df),
            "top5": sel_df.head(5).to_dict(orient="records") if not sel_df.empty else [],
        }
    except Exception as exc:  # noqa: BLE001
        selection_summary = {"error": str(exc)}

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot_slot": snapshot_slot,
        "strategy": strategy,
        "account_series": account_series,
        "positions_latest": positions_latest,
        "selection_latest": {
            "trade_date": sel_td.isoformat() if sel_td else None,
            "count": len(selection_rows),
            "rows": selection_rows[:50],
        },
        "selection_resolve": selection_summary,
        "sop_review": sop,
    }


def cmd_snapshot_portfolio(args: argparse.Namespace) -> int:
    from scripts.tools.portfolio_db import save_portfolio_daily_snapshot

    try:
        stats = save_portfolio_daily_snapshot(
            snapshot_date=args.date or None,
            snapshot_slot=args.slot,
            fetch_market_prices=not args.no_quotes,
        )
        print(
            f"✅ 持仓快照 {stats['snapshot_date']} slot={stats['slot']} "
            f"positions={stats['positions']}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        msg = f"FAIL slot={args.slot} error={exc}"
        log_snapshot_alert(msg)
        print(f"⚠️ 持仓快照失败: {exc}", file=sys.stderr)
        print(f"   已写入告警日志: {SNAPSHOT_ALERT_LOG}", file=sys.stderr)
        return 1


def cmd_backfill_sop(args: argparse.Namespace) -> int:
    from scripts.tools.portfolio_db import save_sop_review_daily

    path = Path(args.json_path) if args.json_path else SOP_JSON_LATEST
    if not path.is_file():
        print(f"❌ 未找到 {path}", file=sys.stderr)
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    td_raw = str(payload.get("trade_date", "")).strip()
    td: date | None = None
    if re.fullmatch(r"\d{8}", td_raw.replace("-", "")[:8]):
        try:
            from scripts.tools.selection_results import parse_trade_date

            td = parse_trade_date(td_raw[:8])
        except Exception:
            td = None
    if td is None:
        from scripts.tools.portfolio_db import latest_selection_trade_date

        td = latest_selection_trade_date(strategy=args.strategy)
        if td is None:
            print(f"❌ 无效 trade_date: {td_raw!r}，且无 MySQL 选股日期可回退", file=sys.stderr)
            return 1
        print(f"⚠️ JSON trade_date 无效，回退至选股日 {td.isoformat()}", file=sys.stderr)

    items: list[dict[str, Any]] = []
    for i, rev in enumerate(payload.get("reviews") or [], 1):
        items.append(
            {
                "rank_no": i,
                "code": rev.get("code"),
                "name": rev.get("name"),
                "score": rev.get("score"),
                "decision": rev.get("decision"),
                "watch_worthy": rev.get("watch_worthy"),
                "support": rev.get("support"),
                "stop": rev.get("stop"),
                "targets": rev.get("targets"),
                "in_holdings": rev.get("in_holdings"),
                "raw_json": rev,
            }
        )
    stats = save_sop_review_daily(
        td,
        strategy=args.strategy,
        selection_source=payload.get("source") or payload.get("csv"),
        generated_at=payload.get("generated_at"),
        wechat_summary=payload.get("wechat_summary", ""),
        report_path=None,
        items=items,
    )
    print(f"✅ SOP 回填 {stats['trade_date']} items={stats['items']}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    payload = export_dashboard_payload(
        date_from=args.from_date,
        date_to=args.to_date,
        snapshot_slot=args.slot,
        strategy=args.strategy,
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"✅ 已写入 {args.output}")
    else:
        print(text)
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    payload = export_dashboard_payload(snapshot_slot=args.slot, strategy=args.strategy)
    acct = payload["account_series"]
    print(f"账户快照 ({args.slot}): {len(acct)} 天")
    if acct:
        last = acct[-1]
        print(
            f"  最新 {last['snapshot_date']}: 总资产={last.get('total_assets')} "
            f"市值={last.get('market_value')} 盈亏={last.get('holding_pnl')}"
        )
    sel = payload["selection_latest"]
    print(f"选股 ({args.strategy}): {sel.get('trade_date')} {sel.get('count')} 条")
    sop = payload.get("sop_review")
    if sop:
        h = sop["header"]
        print(f"SOP: {h.get('trade_date')} items={len(sop.get('items', []))}")
    else:
        print("SOP: 无库内记录")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="看板数据：快照 / SOP 入库 / JSON 导出")
    sub = parser.add_subparsers(dest="cmd")

    p_snap = sub.add_parser("snapshot-portfolio", help="写入持仓+账户每日快照")
    p_snap.add_argument("--date", help="YYYY-MM-DD，默认今天")
    p_snap.add_argument("--slot", default="eod", help="eod|sync|manual")
    p_snap.add_argument("--no-quotes", action="store_true", help="不拉 OpenCLI 现价")
    p_snap.set_defaults(func=cmd_snapshot_portfolio)

    p_bf = sub.add_parser("backfill-sop", help="从 sop_review_latest.json 回填 DB")
    p_bf.add_argument("--json-path", default="", help="默认 output/sop_review_latest.json")
    p_bf.add_argument("--strategy", default="combined")
    p_bf.set_defaults(func=cmd_backfill_sop)

    p_ex = sub.add_parser("export", help="导出看板 JSON")
    p_ex.add_argument("--from-date", dest="from_date", default=None)
    p_ex.add_argument("--to-date", dest="to_date", default=None)
    p_ex.add_argument("--slot", default="eod")
    p_ex.add_argument("--strategy", default="combined")
    p_ex.add_argument("-o", "--output", type=Path, default=None)
    p_ex.set_defaults(func=cmd_export)

    p_sum = sub.add_parser("summary", help="打印看板数据概览")
    p_sum.add_argument("--slot", default="eod")
    p_sum.add_argument("--strategy", default="combined")
    p_sum.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
