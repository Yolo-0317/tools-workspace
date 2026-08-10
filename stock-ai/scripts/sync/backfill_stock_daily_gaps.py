#!/usr/bin/env python3
"""一次性补全 stock_daily：2023 前历史 + 落后最新交易日的增量。"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

_REPO = Path(__file__).resolve().parents[2]
load_dotenv(_REPO / ".env")

from scripts.sync.sync_tushare_daily_to_mysql import (  # noqa: E402
    RateLimiter,
    fetch_daily_data,
    get_mysql_engine,
    init_tushare,
    save_daily_data_to_db,
)

BACKFILL_START = "20180101"
BACKFILL_END = "20221230"
CUTOFF_MIN = "2023-01-03"


def _mysql_url() -> str:
    import os

    url = os.getenv("MYSQL_URL") or ""
    if not Path("/.dockerenv").is_file():
        url = url.replace("host.docker.internal", "127.0.0.1")
    return url


def _full_code(ts_code: str, exch_code: str | None) -> str:
    if "." in ts_code:
        return ts_code
    exch = exch_code or ("SH" if ts_code.startswith(("6", "68", "9")) else "SZ")
    return f"{ts_code}.{exch}"


def _parse_args():
    import argparse

    p = argparse.ArgumentParser(description="补全 stock_daily 缺口")
    p.add_argument(
        "--forward-only",
        action="store_true",
        help="仅追平至库内最新交易日，不补 2018-2022 历史",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    engine = create_engine(_mysql_url(), pool_pre_ping=True)
    pro = init_tushare()
    rl = RateLimiter(40)
    today = datetime.now().strftime("%Y%m%d")

    with engine.connect() as conn:
        global_max = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).scalar()
        rows = conn.execute(
            text(
                """
                SELECT ts_code, exch_code,
                       MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
                FROM stock_daily
                WHERE ts_code NOT LIKE '%.%'
                GROUP BY ts_code, exch_code
                ORDER BY ts_code
                """
            )
        ).fetchall()

    if args.forward_only:
        pending = [r for r in rows if r.max_d < global_max]
        mode = "仅追平"
    else:
        pending = [
            r for r in rows if str(r.min_d) == CUTOFF_MIN or r.max_d < global_max
        ]
        mode = "追平+2018-2022"
    total = len(pending)
    print(
        f"模式：{mode} | 去重后 {len(rows)} 只；待补 {total} 只；"
        f"库内最新交易日 {global_max}"
    )
    if not pending:
        print("无需补全，已全部就绪")
        return 0

    back_n = fwd_n = api_calls = 0
    for i, row in enumerate(pending, 1):
        full = _full_code(row.ts_code, row.exch_code)
        min_d, max_d = row.min_d, row.max_d

        if not args.forward_only and str(min_d) == CUTOFF_MIN:
            rl.wait_if_needed()
            df, _ = fetch_daily_data(
                pro, full, start_date=BACKFILL_START, end_date=BACKFILL_END
            )
            api_calls += 1
            if not df.empty:
                n = save_daily_data_to_db(engine, df, full)
                back_n += n
                if n:
                    print(f"[{i}/{total}] {full} 补 2018-2022: {n} 条")

        if max_d < global_max:
            start = (max_d + timedelta(days=1)).strftime("%Y%m%d")
            if start <= today:
                rl.wait_if_needed()
                df, _ = fetch_daily_data(pro, full, start_date=start, end_date=today)
                api_calls += 1
                if not df.empty:
                    n = save_daily_data_to_db(engine, df, full)
                    fwd_n += n
                    if n:
                        print(f"[{i}/{total}] {full} 补增量: {n} 条")

        if i % 200 == 0:
            print(f"... 进度 {i}/{total}，API {api_calls}，回填 {back_n}，增量 {fwd_n}")
        time.sleep(0.3)

    print(
        f"完成：API {api_calls} 次，2018-2022 回填 {back_n} 条，"
        f"追平最新日 {fwd_n} 条"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
