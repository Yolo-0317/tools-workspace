#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, time
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools.portfolio_db import load_stock_daily_bars  # noqa: E402
from stock_ai.limit_up_logic import (  # noqa: E402
    LimitUpContext,
    LimitUpResult,
    analyze_limit_up_logic as run_limit_up_analysis,
    format_limit_up_logic_card,
)


def _csv_tuple(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(part.strip() for part in value.replace("，", ",").split(",") if part.strip()))


def _cutoff(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.combine(date.fromisoformat(value), time(15, 0))


def build_limit_up_result_from_db(
    *,
    code: str,
    name: str,
    as_of: str | None = None,
    concepts: tuple[str, ...] = (),
    active_themes: tuple[str, ...] = (),
    sector_change_pct: float | None = None,
    sector_limit_up_count: int | None = None,
    sector_leader_strength: str = "unknown",
    main_net_inflow_ratio: float | None = None,
    consecutive_inflow_days: int | None = None,
    material_risk: bool = False,
    material_risk_reasons: tuple[str, ...] = (),
) -> LimitUpResult | None:
    bars = load_stock_daily_bars(code, end_date=as_of, limit=60)
    if not bars:
        return None
    return run_limit_up_analysis(
        code,
        name,
        bars,
        LimitUpContext(
            concepts=concepts,
            active_themes=active_themes,
            sector_change_pct=sector_change_pct,
            sector_limit_up_count=sector_limit_up_count,
            sector_leader_strength=sector_leader_strength,
            main_net_inflow_ratio=main_net_inflow_ratio,
            consecutive_inflow_days=consecutive_inflow_days,
            material_risk=material_risk,
            material_risk_reasons=material_risk_reasons,
            observed_at=_cutoff(as_of),
        ),
        is_st="ST" in name.upper(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="分析个股涨停基因、加速结构和三路径概率")
    parser.add_argument("--code", required=True, help="六位股票代码")
    parser.add_argument("--name", required=True, help="股票名称")
    parser.add_argument("--as-of", help="历史回放截止日，YYYY-MM-DD")
    parser.add_argument("--concept", help="公司概念，逗号分隔")
    parser.add_argument("--active-theme", help="已验证活跃题材，逗号分隔")
    parser.add_argument("--sector-change", type=float, help="板块涨幅百分比")
    parser.add_argument("--sector-limit-ups", type=int, help="板块涨停家数")
    parser.add_argument(
        "--sector-leader",
        choices=("strong", "neutral", "weak", "unknown"),
        default="unknown",
        help="板块领涨股持续性",
    )
    parser.add_argument("--main-inflow-ratio", type=float, help="当日主力净流入占比")
    parser.add_argument("--inflow-days", type=int, help="连续主力净流入天数")
    parser.add_argument("--material-risk", action="store_true", help="存在官方重大风险")
    parser.add_argument("--risk-reason", action="append", default=[], help="重大风险原因，可重复")
    parser.add_argument("--json", action="store_true", help="输出结构化JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_limit_up_result_from_db(
        code=args.code,
        name=args.name,
        as_of=args.as_of,
        concepts=_csv_tuple(args.concept),
        active_themes=_csv_tuple(args.active_theme),
        sector_change_pct=args.sector_change,
        sector_limit_up_count=args.sector_limit_ups,
        sector_leader_strength=args.sector_leader,
        main_net_inflow_ratio=args.main_inflow_ratio,
        consecutive_inflow_days=args.inflow_days,
        material_risk=args.material_risk,
        material_risk_reasons=tuple(args.risk_reason),
    )
    if result is None:
        print(f"{args.name}({args.code})没有可用的完整日线", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2, default=str))
    else:
        print(format_limit_up_logic_card(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
