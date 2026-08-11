#!/usr/bin/env python3
"""并行跑 A轨 combined(+watch) / ma5 / 五因子 / 筑底，写入 MySQL 分 strategy 桶。"""

from __future__ import annotations

import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "core_v2", ROOT / "core_v3"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

LANE_ORDER = ("combined", "ma5", "five_factor", "bottom_breakout")


def _run_combined() -> None:
    from stock_selection_combined import main as run_combined

    run_combined()


def _run_ma5() -> None:
    from scripts.selection.stock_selection_ma5 import main as run_ma5

    run_ma5()


def _run_five_factor() -> None:
    from stock_selection_five_factor_mysql import main as run_five

    run_five()


def _run_bottom_breakout() -> None:
    from stock_selection_bottom_breakout_eastmoney import main as run_bottom

    run_bottom()


_LANE_RUNNERS = {
    "combined": _run_combined,
    "ma5": _run_ma5,
    "five_factor": _run_five_factor,
    "bottom_breakout": _run_bottom_breakout,
}


def _execute_lane(lane: str) -> tuple[str, int, str | None, float]:
    """子进程入口：跑单条策略轨，返回 (lane, exit_code, error, seconds)。"""
    t0 = time.perf_counter()
    runner = _LANE_RUNNERS.get(lane)
    if runner is None:
        return lane, 1, f"unknown lane: {lane}", 0.0
    print(f"[{lane}] 开始", flush=True)
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            runner()
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else (1 if exc.code else 0)
        elapsed = time.perf_counter() - t0
        if code != 0:
            print(f"[{lane}] 失败 exit={code} ({elapsed:.1f}s)", flush=True)
            return lane, code, f"SystemExit({code})", elapsed
        print(f"[{lane}] 完成 ({elapsed:.1f}s)", flush=True)
        return lane, 0, None, elapsed
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - t0
        print(f"[{lane}] 异常: {exc} ({elapsed:.1f}s)", flush=True)
        return lane, 1, str(exc), elapsed
    elapsed = time.perf_counter() - t0
    print(f"[{lane}] 完成 ({elapsed:.1f}s)", flush=True)
    return lane, 0, None, elapsed


def _run_lanes_sequential() -> int:
    labels = {
        "combined": "1. A轨 combined + B轨 watch",
        "ma5": "2. MA5 回踩（strategy=ma5）",
        "five_factor": "3. 五因子（strategy=five_factor）",
        "bottom_breakout": "4. 筑底+放量突破（strategy=bottom_breakout）",
    }
    failed: list[str] = []
    for lane in LANE_ORDER:
        print("=" * 60)
        print(labels[lane])
        print("=" * 60)
        _, code, err, _ = _execute_lane(lane)
        if code != 0:
            failed.append(f"{lane}: {err or code}")
    if failed:
        print("串行选股部分失败:", "; ".join(failed), file=sys.stderr)
        return 1
    print(
        "\n选股完成：combined / watch / ma5 / five_factor / bottom_breakout 已分桶入库"
    )
    return 0


def _run_lanes_parallel(*, max_workers: int) -> int:
    workers = min(max_workers, len(LANE_ORDER))
    print(
        f"并行选股：{', '.join(LANE_ORDER)}（ProcessPool workers={workers}）",
        flush=True,
    )
    t0 = time.perf_counter()
    failed: list[str] = []
    timings: dict[str, float] = {}

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_execute_lane, lane): lane for lane in LANE_ORDER}
        for fut in as_completed(futures):
            lane, code, err, elapsed = fut.result()
            timings[lane] = elapsed
            if code != 0:
                failed.append(f"{lane}: {err or code}")

    total = time.perf_counter() - t0
    print("\n" + "=" * 60)
    print("并行选股耗时（墙钟）")
    for lane in LANE_ORDER:
        if lane in timings:
            print(f"  {lane}: {timings[lane]:.1f}s")
    print(f"  合计墙钟: {total:.1f}s（约等于最慢轨耗时，非四轨相加）")
    print("=" * 60)

    if failed:
        print("并行选股部分失败:", "; ".join(failed), file=sys.stderr)
        return 1
    print(
        "\n并行选股完成：combined / watch / ma5 / five_factor / bottom_breakout 已分桶入库"
    )
    return 0


def main() -> int:
    from scripts.tools.ensure_daily_bars import ensure_daily_bars_at_selection_start

    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        ensure_daily_bars_at_selection_start()

    sequential = os.getenv("SELECTION_LANES_SEQUENTIAL", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if sequential:
        print("SELECTION_LANES_SEQUENTIAL=1，四轨串行", flush=True)
        return _run_lanes_sequential()

    try:
        max_workers = int(os.getenv("SELECTION_LANE_WORKERS", "4"))
    except ValueError:
        max_workers = 4
    max_workers = max(1, min(max_workers, len(LANE_ORDER)))
    return _run_lanes_parallel(max_workers=max_workers)


if __name__ == "__main__":
    raise SystemExit(main())
