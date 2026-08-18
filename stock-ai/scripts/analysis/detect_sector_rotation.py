#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from scripts.tools.portfolio_db import get_engine
from stock_ai.sector_rotation.models import RotationPolicy
from stock_ai.sector_rotation.providers import ProductionRotationDataProvider
from stock_ai.sector_rotation.repository import SQLRotationRepository
from stock_ai.sector_rotation.service import RotationSourceError, detect_sector_rotation


def build_provider() -> ProductionRotationDataProvider:
    return ProductionRotationDataProvider()


def build_repository():
    engine = get_engine()
    return SQLRotationRepository(engine.connect()) if engine is not None else None


def _edition(value: str, now: datetime) -> str:
    if value != "auto":
        return value
    if now.weekday() < 5 and (now.hour, now.minute) < (15, 0) and (now.hour, now.minute) >= (9, 30):
        return "intraday"
    return "close"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="手动检测强势板块轮动")
    parser.add_argument("--edition", choices=("auto", "intraday", "close"), default="auto")
    parser.add_argument("--top-sectors", type=int, default=6)
    parser.add_argument("--stocks-per-sector", type=int, default=10)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-db", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if not 1 <= args.top_sectors <= 12 or not 3 <= args.stocks_per_sector <= 20:
            print("参数错误：top-sectors需为1至12，stocks-per-sector需为3至20")
            return 2
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        repository = None if args.no_db else build_repository()
        result = detect_sector_rotation(
            provider=build_provider(), repository=repository, policy=RotationPolicy(),
            observed_at=now, edition=_edition(args.edition, now),
            top_sectors=args.top_sectors, stocks_per_sector=args.stocks_per_sector,
            output_path=args.output,
        )
    except (RotationSourceError, RuntimeError, ValueError) as exc:
        print(f"检测失败：{exc}")
        return 2
    print(f"报告路径：{result.report_path}")
    print(f"运行状态：SUCCESS")
    print(f"入选方向：{len(result.chains)}")
    if result.warnings:
        print(f"数据提示：{'；'.join(result.warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
