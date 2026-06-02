#!/usr/bin/env python3
"""情绪周期日检：MySQL 读写 CLI（游资轨）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.portfolio_db import (  # noqa: E402
    EMOTION_CYCLE_PHASES,
    list_emotion_cycle_trade_dates,
    load_emotion_cycle_checklist,
    save_emotion_cycle_checklist,
)


def _json_template() -> dict:
    return {
        "trade_date": "YYYY-MM-DD",
        "checklist_slot": "pre_market",
        "header": {
            "limit_up_count": None,
            "limit_down_count": None,
            "up_down_ratio": "2100:900",
            "max_board_height": None,
            "limit_up_premium_pct": None,
            "explode_rate_pct": None,
            "total_amount_yi": None,
            "theme_count": None,
            "phase": "启动",
            "phase_vs_yesterday": "升温",
            "position_cap_pct": 30,
            "allow_new_open": 1,
            "main_theme": "",
            "main_theme_is_new": 0,
            "drain_market": 0,
            "action_summary": "观察",
            "tomorrow_phase": "",
            "tomorrow_position_cap_pct": None,
            "tomorrow_plan": "",
            "exclude_list": "",
            "review_notes": "",
        },
        "dragon_items": [
            {
                "ts_code": "000001",
                "name": "示例",
                "board_height": 2,
                "main_theme": "",
                "checklist_pass": 5,
                "notes": "",
            }
        ],
    }


def cmd_template(_: argparse.Namespace) -> int:
    print(json.dumps(_json_template(), ensure_ascii=False, indent=2))
    print("\n# phase 可选:", " | ".join(sorted(EMOTION_CYCLE_PHASES)), file=sys.stderr)
    print("# checklist_slot: pre_market | eod", file=sys.stderr)
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    path = Path(args.file)
    payload = json.loads(path.read_text(encoding="utf-8"))
    trade_date = payload.get("trade_date") or args.date
    if not trade_date:
        print("缺少 trade_date（JSON 或 --date）", file=sys.stderr)
        return 1
    slot = payload.get("checklist_slot") or args.slot
    header = payload.get("header") or payload
    dragons = payload.get("dragon_items") or []
    stats = save_emotion_cycle_checklist(
        trade_date,
        header,
        checklist_slot=slot,
        dragon_items=dragons,
    )
    print(json.dumps(stats, ensure_ascii=False))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    bundle = load_emotion_cycle_checklist(
        trade_date=args.date,
        checklist_slot=args.slot,
    )
    if not bundle:
        print("无记录", file=sys.stderr)
        return 1
    print(json.dumps(bundle, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    dates = list_emotion_cycle_trade_dates()
    for d in dates:
        print(d.isoformat())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="情绪周期日检 MySQL 工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tpl = sub.add_parser("template", help="输出 JSON 模板")
    p_tpl.set_defaults(func=cmd_template)

    p_save = sub.add_parser("save", help="从 JSON 写入 MySQL")
    p_save.add_argument("--file", "-f", required=True, help="日检 JSON 文件")
    p_save.add_argument("--date", help="覆盖 JSON 内 trade_date")
    p_save.add_argument("--slot", default="pre_market", choices=["pre_market", "eod"])
    p_save.set_defaults(func=cmd_save)

    p_show = sub.add_parser("show", help="读取并打印")
    p_show.add_argument("--date", help="交易日，默认最新")
    p_show.add_argument("--slot", choices=["pre_market", "eod"])
    p_show.set_defaults(func=cmd_show)

    p_list = sub.add_parser("list", help="列出已有交易日")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
