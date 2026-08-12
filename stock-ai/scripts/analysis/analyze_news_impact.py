#!/usr/bin/env python3
"""独立运行单股消息影响分析，可复用已核验事件缓存。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from stock_ai.news_impact import NewsEvent, ProbabilityPaths, StockContext, analyze_stock_news_impact
from stock_ai.news_impact.formatting import format_stock_impact_card
from stock_ai.news_impact.providers import load_news_coverage


def parse_probabilities(raw: str) -> ProbabilityPaths:
    try:
        values = tuple(int(part.strip()) for part in raw.split(","))
    except ValueError as exc:
        raise ValueError("概率必须是三个整数") from exc
    if len(values) != 3 or sum(values) != 100 or min(values) < 0:
        raise ValueError("概率必须是三个非负整数且合计100")
    return ProbabilityPaths(*values)


def _load_event_json(path: Path, *, now: datetime) -> list[NewsEvent]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else [payload]
    events = []
    for row in rows:
        values = dict(row)
        for key in ("published_at", "observed_at", "valid_until"):
            if values.get(key):
                values[key] = datetime.fromisoformat(values[key])
        values.setdefault("observed_at", now)
        values["subjects"] = tuple(values.get("subjects") or ())
        events.append(NewsEvent(**values))
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="分析海外及国内消息对A股个股三路径概率的影响")
    parser.add_argument("--code", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--industry", default="")
    parser.add_argument("--concept", action="append", default=[])
    parser.add_argument("--base", default="35,45,20", help="强,中,弱；合计100")
    parser.add_argument("--existing-holding", action="store_true")
    parser.add_argument("--event-json", type=Path, help="导入已核验的标准事件JSON并写入缓存")
    args = parser.parse_args(argv)

    now = datetime.now().astimezone()
    if args.event_json:
        events = _load_event_json(args.event_json, now=now)
        try:
            from scripts.tools.news_impact_db import upsert_cached_events
            upsert_cached_events(events)
        except Exception as exc:
            print(f"事件缓存写入失败，仍使用本次内存事件：{exc}", file=sys.stderr)
    else:
        events = list(load_news_coverage(now=now).events)
    result = analyze_stock_news_impact(
        StockContext(args.code.zfill(6), args.name, args.industry, tuple(args.concept)),
        events,
        parse_probabilities(args.base),
        now=now,
        existing_holding=args.existing_holding,
    )
    print(format_stock_impact_card(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
