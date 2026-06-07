#!/usr/bin/env python3
"""OpenCLI 东财档案 enrich：入选股 brief_info + F10 所属板块 → stock_profile + raw_json。"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "core_v2"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from dotenv import load_dotenv

from scripts.tools.fetch_eastmoney_quotes import (
    fetch_selection_profiles_batch,
    selection_profile_from_payload,
)
from scripts.tools.portfolio_db import (
    _selection_row_code,
    enrich_selection_profiles_for_date,
    latest_selection_trade_date,
    load_selection_daily_results,
    load_stock_profiles_by_codes,
    patch_selection_daily_profiles,
    upsert_stock_profiles,
)
from scripts.tools.selection_results import (
    ENRICH_UNIFIED_TOP5_STRATEGIES,
    pick_unified_top5,
)


def _parse_trade_date(raw: str | None) -> date | None:
    if not raw or raw.lower() in {"latest", "auto", "last"}:
        return None
    text = raw.strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return datetime.fromisoformat(text).date()


def _snapshot_to_profile_dict(snap) -> dict:
    return {
        "ts_code": snap.code,
        "name": snap.name,
        "industry": snap.industry,
        "concepts": snap.concepts,
        "profile_text": snap.profile_text,
        "info_text": snap.info_text,
        "sectors_text": snap.sectors_text,
        "source": "eastmoney-opencli",
    }


def run_enrich(
    *,
    trade_date: date | None = None,
    strategy: str = "combined",
    codes: list[str] | None = None,
    wait_seconds: float = 2.0,
    dry_run: bool = False,
    reparse_only: bool = False,
) -> dict:
    td, rows = load_selection_daily_results(trade_date, strategy=strategy)
    if td is None or not rows:
        resolved = trade_date or latest_selection_trade_date(strategy=strategy)
        print(f"⚠️ 无选股记录: strategy={strategy} trade_date={resolved}")
        return {"trade_date": None, "count": 0}

    if codes:
        code_set = {str(c).split(".")[0].zfill(6) for c in codes}
        rows = [r for r in rows if _selection_row_code(r) in code_set]

    uniq_codes = [_selection_row_code(r) for r in rows]
    uniq_codes = list(dict.fromkeys(c for c in uniq_codes if c))
    print(f"📋 enrich {len(uniq_codes)} 只 · {td.isoformat()} · strategy={strategy}")

    if dry_run:
        print("dry-run:", ", ".join(uniq_codes))
        return {"trade_date": td.isoformat(), "codes": uniq_codes, "dry_run": True}

    if reparse_only:
        stored = load_stock_profiles_by_codes(uniq_codes)
        snapshots = {}
        for code in uniq_codes:
            row = stored.get(code) or {}
            snapshots[code] = selection_profile_from_payload(
                code,
                name=str(row.get("name") or code),
                info_text=str(row.get("info_text") or ""),
                sectors_text=str(row.get("sectors_text") or ""),
            )
    else:
        snapshots = fetch_selection_profiles_batch(
            uniq_codes,
            wait_seconds=wait_seconds,
            close_browser=True,
        )
    profiles_by_code = {
        code: _snapshot_to_profile_dict(snap) for code, snap in snapshots.items()
    }
    result = enrich_selection_profiles_for_date(
        td,
        strategy=strategy,
        profiles_by_code=profiles_by_code,
    )
    ok = sum(1 for c in uniq_codes if profiles_by_code.get(c, {}).get("industry") or profiles_by_code.get(c, {}).get("concepts"))
    print(
        f"✓ upsert={result['upserted']} patched={result['patched']} "
        f"有行业/概念={ok}/{len(uniq_codes)}"
    )
    for code in uniq_codes[:5]:
        p = profiles_by_code.get(code, {})
        concepts = "、".join(p.get("concepts") or [])[:40]
        print(f"  {code} {p.get('name') or ''} | {p.get('industry') or '—'} | {concepts or '—'}")
    if len(uniq_codes) > 5:
        print(f"  ... 共 {len(uniq_codes)} 只")
    return result


def run_enrich_unified_top5(
    *,
    trade_date: date | None = None,
    top_n: int = 5,
    strategies: tuple[str, ...] | None = None,
    wait_seconds: float = 2.0,
    dry_run: bool = False,
    reparse_only: bool = False,
) -> dict:
    """五策略合并 Top5：OpenCLI 抓一次档案，写 stock_profile 并回写各策略命中行。"""
    strat_list = tuple(strategies or ENRICH_UNIFIED_TOP5_STRATEGIES)
    try:
        td, codes, source = pick_unified_top5(
            trade_date=trade_date,
            top_n=top_n,
            strategies=strat_list,
        )
    except FileNotFoundError as exc:
        print(f"⚠️ 无法合并 Top{top_n}: {exc}")
        return {"trade_date": None, "count": 0}

    if not codes:
        print(f"⚠️ 合并 Top{top_n} 为空 · {source}")
        return {"trade_date": td.isoformat() if td else None, "count": 0}

    print(
        f"📋 enrich 合并 Top{len(codes)} · {td.isoformat()} · {source}\n"
        f"   代码: {', '.join(codes)}"
    )

    if dry_run:
        return {"trade_date": td.isoformat(), "codes": codes, "dry_run": True}

    if reparse_only:
        stored = load_stock_profiles_by_codes(codes)
        snapshots = {}
        for code in codes:
            row = stored.get(code) or {}
            snapshots[code] = selection_profile_from_payload(
                code,
                name=str(row.get("name") or code),
                info_text=str(row.get("info_text") or ""),
                sectors_text=str(row.get("sectors_text") or ""),
            )
    else:
        snapshots = fetch_selection_profiles_batch(
            codes,
            wait_seconds=wait_seconds,
            close_browser=True,
        )
    profiles_by_code = {
        code: _snapshot_to_profile_dict(snap) for code, snap in snapshots.items()
    }
    upserted = upsert_stock_profiles(list(profiles_by_code.values()))
    patched_total = 0
    for strat in strat_list:
        patched_total += patch_selection_daily_profiles(
            td,
            profiles_by_code,
            strategy=strat,
        )
    ok = sum(
        1
        for c in codes
        if profiles_by_code.get(c, {}).get("industry")
        or profiles_by_code.get(c, {}).get("concepts")
    )
    print(
        f"✓ stock_profile upsert={upserted} "
        f"selection patched={patched_total} 有行业/概念={ok}/{len(codes)}"
    )
    for code in codes:
        p = profiles_by_code.get(code, {})
        concepts = "、".join(p.get("concepts") or [])[:40]
        print(f"  {code} {p.get('name') or ''} | {p.get('industry') or '—'} | {concepts or '—'}")
    return {
        "trade_date": td.isoformat(),
        "codes": codes,
        "upserted": upserted,
        "patched": patched_total,
        "source": source,
    }


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="OpenCLI 入选股档案 enrich")
    parser.add_argument(
        "--trade-date",
        default="latest",
        help="YYYY-MM-DD / YYYYMMDD / latest",
    )
    parser.add_argument("--strategy", default="combined", help="单策略模式时使用")
    parser.add_argument(
        "--top5-unified",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="五策略合并按总分取 Top5 再 enrich（默认开启）",
    )
    parser.add_argument("--top-n", type=int, default=5, help="合并 Top N，默认 5")
    parser.add_argument("--codes", default="", help="逗号分隔，仅 enrich 子集（单策略模式）")
    parser.add_argument("--wait-seconds", type=float, default=2.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--reparse-only",
        action="store_true",
        help="不重新抓页，仅用 stock_profile 原文重解析",
    )
    args = parser.parse_args()

    td = _parse_trade_date(args.trade_date)
    if args.top5_unified and not args.codes.strip():
        run_enrich_unified_top5(
            trade_date=td,
            top_n=args.top_n,
            wait_seconds=args.wait_seconds,
            dry_run=args.dry_run,
            reparse_only=args.reparse_only,
        )
        return

    codes = [c.strip() for c in args.codes.split(",") if c.strip()] or None
    run_enrich(
        trade_date=td,
        strategy=args.strategy,
        codes=codes,
        wait_seconds=args.wait_seconds,
        dry_run=args.dry_run,
        reparse_only=args.reparse_only,
    )


if __name__ == "__main__":
    main()
