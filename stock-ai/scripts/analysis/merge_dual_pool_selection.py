#!/usr/bin/env python3
"""Merge technical selection rows with the fresh major-news event pool."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.portfolio_db import save_selection_daily_results
from scripts.tools.selection_results import merge_selection_strategies_df, parse_trade_date
from stock_ai.dual_pool_selection import merge_dual_pool_rows
from stock_ai.news_impact.providers import load_news_coverage


@dataclass(frozen=True)
class DualPoolRunSummary:
    trade_date: date
    technical_count: int
    both_count: int
    vetoed_count: int
    event_watch_count: int
    coverage_status: str
    news_cutoff: datetime
    output_path: Path
    mysql_rows: int


def run_dual_pool_selection(
    *,
    trade_date: date | str | None = None,
    top_n: int = 5,
    output_path: Path | str | None = None,
    write_db: bool = True,
    now: datetime | None = None,
) -> DualPoolRunSummary:
    resolved_now = now or datetime.now().astimezone()
    resolved_date, technical_frame, _source = merge_selection_strategies_df(
        trade_date=trade_date,
        include_news=False,
    )
    coverage = load_news_coverage(now=resolved_now)
    coverage_status = "不足" if coverage.missing_scopes else "完整"
    merged = merge_dual_pool_rows(
        technical_frame.to_dict(orient="records"),
        coverage.events,
        now=resolved_now,
        coverage_status=coverage_status,
    )
    output = Path(output_path) if output_path is not None else (
        ROOT / "output" / f"stock_selection_dual_pool_{resolved_date.strftime('%Y%m%d')}.csv"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(merged.technical_rows).to_csv(output, index=False, encoding="utf-8-sig")

    mysql_rows = 0
    if write_db:
        mysql_rows += save_selection_daily_results(
            resolved_date,
            list(merged.technical_rows),
            strategy="dual_pool",
            enrich_names=False,
        )
        mysql_rows += save_selection_daily_results(
            resolved_date,
            list(merged.event_watch_rows),
            strategy="news_event_watch",
            enrich_names=False,
        )

    states = [str(row.get("候选池来源", "technical")) for row in merged.technical_rows]
    summary = DualPoolRunSummary(
        trade_date=resolved_date,
        technical_count=sum(state == "technical" for state in states),
        both_count=sum(state == "both" for state in states),
        vetoed_count=sum(state == "vetoed" for state in states),
        event_watch_count=len(merged.event_watch_rows),
        coverage_status=coverage_status,
        news_cutoff=coverage.fetched_at,
        output_path=output,
        mysql_rows=mysql_rows,
    )

    print(f"交易日：{summary.trade_date.isoformat()}")
    print(
        "候选池："
        f"技术独有 {summary.technical_count}，技术与消息共振 {summary.both_count}，"
        f"重大利空否决 {summary.vetoed_count}，消息观察 {summary.event_watch_count}"
    )
    print(f"消息覆盖：{summary.coverage_status}；截止 {summary.news_cutoff.isoformat()}")
    print(f"结果文件：{summary.output_path}")
    if write_db:
        print(f"MySQL写入：{summary.mysql_rows} 条")
    preview = pd.DataFrame(merged.technical_rows).head(max(0, top_n))
    if not preview.empty:
        columns = [column for column in ("代码", "名称", "总分", "候选池来源", "消息方向") if column in preview]
        print(preview[columns].to_string(index=False))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="合并技术候选池与重大新闻事件池")
    parser.add_argument("--date", help="交易日，格式 YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--top", type=int, default=5, help="终端预览数量")
    parser.add_argument("--no-db", action="store_true", help="不写入MySQL")
    parser.add_argument("--output", type=Path, help="输出CSV路径")
    args = parser.parse_args(argv)
    run_dual_pool_selection(
        trade_date=parse_trade_date(args.date) if args.date else None,
        top_n=args.top,
        output_path=args.output,
        write_db=not args.no_db,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
