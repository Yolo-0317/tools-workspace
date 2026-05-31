#!/usr/bin/env python3
"""预热 A 股代码→中文名本地缓存（Tushare stock_basic + 东财 clist）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.tools.portfolio_db import (
    _NAME_CACHE_FILE,
    _MARKET_NAME_CACHE_MIN,
    _read_disk_name_cache,
    ensure_market_name_cache,
    get_engine,
    list_selection_trade_dates,
    load_stock_names_by_codes,
)


def main() -> int:
    force = "--force" in sys.argv
    n = ensure_market_name_cache(force=force)
    if n < _MARKET_NAME_CACHE_MIN:
        engine = get_engine()
        codes: list[str] = []
        for td in list_selection_trade_dates(strategy="combined")[:3]:
            with engine.connect() as conn:
                from sqlalchemy import text

                rows = conn.execute(
                    text(
                        "SELECT DISTINCT ts_code FROM selection_daily_results "
                        "WHERE trade_date = :d AND strategy = 'combined'"
                    ),
                    {"d": td.isoformat()},
                ).fetchall()
            codes.extend(str(r.ts_code).zfill(6) for r in rows)
        if codes:
            print(f"⏳ 全市场缓存不足，OpenCLI 补全最近选股 {len(set(codes))} 只…", file=sys.stderr)
            load_stock_names_by_codes(sorted(set(codes)))
            n = len(_read_disk_name_cache())
    print(f"✅ 名称缓存 {n} 条 → {_NAME_CACHE_FILE}")
    return 0 if n >= 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
