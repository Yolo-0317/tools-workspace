#!/usr/bin/env python3
"""并行跑 A轨 combined(+watch) / ma5 / 五因子，写入 MySQL 分 strategy 桶。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "core_v2", ROOT / "core_v3"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    print("=" * 60)
    print("① A轨 combined + B轨 watch")
    print("=" * 60)
    from stock_selection_combined import main as run_combined

    run_combined()

    print("\n" + "=" * 60)
    print("② MA5 回踩（strategy=ma5）")
    print("=" * 60)
    from scripts.selection.stock_selection_ma5 import main as run_ma5

    run_ma5()

    print("\n" + "=" * 60)
    print("③ 五因子（strategy=five_factor）")
    print("=" * 60)
    from stock_selection_five_factor_mysql import main as run_five

    run_five()

    print("\n" + "=" * 60)
    print("④ 筑底+放量突破（strategy=bottom_breakout）")
    print("=" * 60)
    from stock_selection_bottom_breakout_eastmoney import main as run_bottom_breakout

    run_bottom_breakout()

    print(
        "\n✅ 并行选股完成：combined / watch / ma5 / five_factor / bottom_breakout 已分桶入库"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
