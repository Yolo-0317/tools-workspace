#!/usr/bin/env python3
"""检测 MySQL 日线是否落后，必要时触发 Tushare by_date 补同步。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

TZ = ZoneInfo("Asia/Shanghai")
REPO_ROOT = Path(__file__).resolve().parents[2]


def expected_latest_trade_date(
    now: datetime | None = None,
    *,
    tushare_ready_hour: int = 17,
) -> date:
    """Tushare 当日收盘数据通常 17:00 后较稳定。"""
    now = now or datetime.now(TZ)
    d = now.date()
    t = now.time()

    def _prev_weekday(day: date) -> date:
        nd = day - timedelta(days=1)
        while nd.weekday() >= 5:
            nd -= timedelta(days=1)
        return nd

    if d.weekday() >= 5:
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

    if t < time(tushare_ready_hour, 0):
        return _prev_weekday(d)
    return d


def _mysql_url() -> str:
    return (os.getenv("MYSQL_URL") or "").replace("host.docker.internal", "127.0.0.1")


def get_trade_date_bar_count(trade_date: date, mysql_url: str | None = None) -> int:
    url = mysql_url or _mysql_url()
    if not url:
        return 0
    engine = create_engine(url)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT COUNT(*) FROM stock_daily WHERE trade_date = :d"),
            {"d": trade_date},
        ).fetchone()
    return int(row[0] or 0) if row else 0


def min_expected_bar_count() -> int:
    raw = (os.getenv("DAILY_BARS_MIN_COUNT") or "3500").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 3500


def check_daily_bars_ready(
    *,
    tushare_ready_hour: int = 17,
    mysql_url: str | None = None,
) -> tuple[bool, dict]:
    """期望交易日已在库内且有足够条数（全市场日线）。"""
    expected = expected_latest_trade_date(tushare_ready_hour=tushare_ready_hour)
    db_max = get_db_max_trade_date(mysql_url)
    min_count = min_expected_bar_count()
    bar_count = get_trade_date_bar_count(expected, mysql_url) if db_max else 0
    ready = (
        db_max is not None
        and db_max >= expected
        and bar_count >= min_count
    )
    return ready, {
        "expected": expected.isoformat(),
        "db_max": db_max.isoformat() if db_max else None,
        "bar_count": bar_count,
        "min_count": min_count,
    }


def get_db_max_trade_date(mysql_url: str | None = None) -> date | None:
    url = mysql_url or _mysql_url()
    if not url:
        return None
    engine = create_engine(url)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).fetchone()
    if not row or row[0] is None:
        return None
    val = row[0]
    return val if isinstance(val, date) else datetime.strptime(str(val)[:10], "%Y-%m-%d").date()


def get_code_max_trade_date(code: str, mysql_url: str | None = None) -> date | None:
    url = mysql_url or _mysql_url()
    if not url:
        return None
    code6 = str(code).split(".")[0].zfill(6)
    engine = create_engine(url)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT MAX(trade_date) FROM stock_daily WHERE ts_code = :c"),
            {"c": code6},
        ).fetchone()
    if not row or row[0] is None:
        return None
    val = row[0]
    return val if isinstance(val, date) else datetime.strptime(str(val)[:10], "%Y-%m-%d").date()


def ensure_daily_bars_sync(
    *,
    codes: list[str] | None = None,
    tushare_ready_hour: int = 17,
    min_sync_days: int = 2,
    max_sync_days: int = 2,
    dry_run: bool = False,
) -> dict:
    """若库内最新交易日落后于期望，则 by_date 补同步。"""
    load_dotenv(REPO_ROOT / ".env")
    expected = expected_latest_trade_date(tushare_ready_hour=tushare_ready_hour)
    db_max = get_db_max_trade_date()

    stale_codes: list[str] = []
    if codes:
        for c in codes:
            cm = get_code_max_trade_date(c)
            if cm is None or cm < expected:
                stale_codes.append(str(c).split(".")[0].zfill(6))

    needs_sync = db_max is None or db_max < expected or bool(stale_codes)
    result: dict = {
        "expected": expected.isoformat(),
        "db_max": db_max.isoformat() if db_max else None,
        "stale_codes": stale_codes,
        "synced": False,
        "sync_days": 0,
        "ready": False,
    }

    min_count = min_expected_bar_count()
    bar_count = get_trade_date_bar_count(expected) if db_max and db_max >= expected else 0
    result["bar_count"] = bar_count
    result["min_count"] = min_count

    if not needs_sync and bar_count >= min_count:
        print(
            f"日线已至期望交易日 {expected}（库内 MAX={db_max}，"
            f"当日 {bar_count} 条）"
        )
        result["ready"] = True
        return result

    if not needs_sync and bar_count < min_count:
        needs_sync = True
        print(
            f"MAX={db_max} 已到 {expected}，但当日仅 {bar_count} 条（需 ≥{min_count}）",
            file=sys.stderr,
        )

    sync_days = min_sync_days

    result["sync_days"] = sync_days
    print(
        f"日线落后：期望 {expected}，库内 MAX={db_max}，"
        f"{'个股缺失 ' + ','.join(stale_codes) if stale_codes else '全市场'} → "
        f"{'仅检测' if dry_run else f'触发 Tushare by_date {sync_days} 天'}"
    )

    if dry_run:
        return result

    if not os.getenv("TUSHARE_TOKEN"):
        print("未配置 TUSHARE_TOKEN，无法补同步", file=sys.stderr)
        return result

    from scripts.sync.sync_tushare_daily_to_mysql import sync_daily_data

    rc = sync_daily_data(mode="by_date", days=sync_days, sleep_seconds=2.0, max_calls_per_minute=40)
    result["synced"] = rc == 0
    new_max = get_db_max_trade_date()
    result["db_max_after"] = new_max.isoformat() if new_max else None
    new_count = get_trade_date_bar_count(expected)
    result["bar_count_after"] = new_count
    ready = new_max is not None and new_max >= expected and new_count >= min_expected_bar_count()
    result["ready"] = ready
    if ready:
        print(
            f"补同步完成，库内 MAX={new_max}，"
            f"{expected} 共 {new_count} 条"
        )
    else:
        print(
            f"补同步后 MAX={new_max}、{expected} 条数={new_count}，"
            f"未达期望 {expected}（需 ≥{min_expected_bar_count()} 条）",
            file=sys.stderr,
        )
    return result


def ensure_daily_bars_at_selection_start(
    *,
    tushare_ready_hour: int = 17,
    sync_if_stale: bool = True,
) -> None:
    """综合选股入口：先确认当日日线已入库，落后则补同步，仍不满足则退出。"""
    if os.getenv("SKIP_DAILY_BARS_CHECK", "").strip().lower() in ("1", "true", "yes"):
        print("⏭️ 跳过日线检查（SKIP_DAILY_BARS_CHECK=1）")
        return

    load_dotenv(REPO_ROOT / ".env")
    if not _mysql_url():
        print("未配置 MYSQL_URL，无法检查日线", file=sys.stderr)
        raise SystemExit(1)

    ready, info = check_daily_bars_ready(tushare_ready_hour=tushare_ready_hour)
    if ready:
        print(
            f"日线已更新：期望 {info['expected']}，"
            f"库内 MAX={info['db_max']}，当日 {info['bar_count']} 条"
        )
        return

    print(
        f"日线未就绪：期望 {info['expected']}，"
        f"库内 MAX={info['db_max']}，当日 {info['bar_count']} 条"
        f"（需 ≥{info['min_count']}）",
        file=sys.stderr,
    )
    if not sync_if_stale:
        raise SystemExit(1)

    if not os.getenv("TUSHARE_TOKEN"):
        print("未配置 TUSHARE_TOKEN，无法补同步日线", file=sys.stderr)
        raise SystemExit(1)

    ensure_daily_bars_sync(tushare_ready_hour=tushare_ready_hour)
    ready, info = check_daily_bars_ready(tushare_ready_hour=tushare_ready_hour)
    if not ready:
        print(
            f"补同步后日线仍不可用：期望 {info['expected']}，"
            f"MAX={info['db_max']}，当日 {info['bar_count']} 条",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(
        f"日线补同步后已就绪：{info['expected']} 共 {info['bar_count']} 条"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="检测并补同步 Tushare 日线")
    parser.add_argument("--sync-if-stale", action="store_true", help="落后则自动 by_date 同步")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="同步后仍不满足则退出码 1（选股流水线推荐）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只检测不同步")
    parser.add_argument("--codes", default="", help="额外检查个股，逗号分隔")
    parser.add_argument("--ready-hour", type=int, default=17, help="Tushare 当日数据就绪小时")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]

    if not args.sync_if_stale and not args.dry_run:
        ready, info = check_daily_bars_ready(tushare_ready_hour=args.ready_hour)
        print(
            f"期望交易日: {info['expected']} | 库内 MAX: {info['db_max']} | "
            f"当日条数: {info['bar_count']} (需≥{info['min_count']}) | "
            f"就绪: {'是' if ready else '否'}"
        )
        return 0 if ready or not args.require_ready else 1

    if args.dry_run:
        ready, info = check_daily_bars_ready(tushare_ready_hour=args.ready_hour)
        if not ready:
            print(
                f"日线未就绪：期望 {info['expected']} MAX={info['db_max']} "
                f"条数={info['bar_count']}",
                file=sys.stderr,
            )
        return 0 if ready or not args.require_ready else 1

    ensure_daily_bars_sync(
        codes=codes or None,
        tushare_ready_hour=args.ready_hour,
        dry_run=False,
    )
    ready, info = check_daily_bars_ready(tushare_ready_hour=args.ready_hour)
    if args.require_ready and not ready:
        print(
            f"日线未就绪：期望 {info['expected']} MAX={info['db_max']} "
            f"条数={info['bar_count']}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
