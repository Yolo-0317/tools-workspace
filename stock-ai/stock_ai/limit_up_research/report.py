"""Deterministic JSON and Markdown reports for the research ledger."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime
from typing import Sequence

from .models import ForwardLabel, NormalizedSnapshot, SelectionAttribution


def _safe_dict(value):
    out = asdict(value)
    for key, item in tuple(out.items()):
        if hasattr(item, "isoformat"):
            out[key] = item.isoformat()
    return out


def build_research_report(
    *,
    run_id: int,
    snapshot: NormalizedSnapshot,
    attributions: Sequence[SelectionAttribution],
    labels: Sequence[ForwardLabel],
    selection_date: date,
    data_cutoff: datetime,
) -> tuple[dict, str]:
    counts = {kind: 0 for kind in ("LIMIT_UP", "EXPLODED", "LIMIT_DOWN")}
    ladder: dict[str, list[str]] = defaultdict(list)
    themes: Counter[str] = Counter()
    for fact in snapshot.facts:
        counts[fact.pool_kind] += 1
        if fact.pool_kind == "LIMIT_UP":
            ladder[str(fact.board_height or 1)].append(f"{fact.code} {fact.name}")
            if fact.main_theme:
                themes[fact.main_theme] += 1
    heights = [
        int(fact.board_height or 1)
        for fact in snapshot.facts
        if fact.pool_kind == "LIMIT_UP"
    ]
    board_summary = {
        "first_board": sum(1 for height in heights if height == 1),
        "multi_board": sum(1 for height in heights if height >= 2),
        "max_height": max(heights, default=0),
    }
    by_strategy: dict[str, list[SelectionAttribution]] = defaultdict(list)
    misses: Counter[str] = Counter()
    for item in attributions:
        by_strategy[item.strategy].append(item)
        if not item.selected and item.first_reason_code:
            misses[item.first_reason_code] += 1
    coverage = {
        strategy: {
            "selected": sum(1 for item in rows if item.selected),
            "total": len(rows),
            "rate": sum(1 for item in rows if item.selected) / len(rows) if rows else 0.0,
        }
        for strategy, rows in sorted(by_strategy.items())
    }
    label_summary = {
        horizon: {
            "total": sum(1 for item in labels if item.horizon == horizon),
            "complete": sum(
                1 for item in labels if item.horizon == horizon and item.data_complete
            ),
        }
        for horizon in ("T1", "T3", "T5")
    }
    payload = {
        "schema_version": "limit-up-research-report-v1",
        "run_id": int(run_id),
        "trade_date": snapshot.trade_date.isoformat(),
        "selection_date": selection_date.isoformat(),
        "source": "eastmoney-opencli-topic-pool",
        "data_cutoff": data_cutoff.isoformat(timespec="seconds"),
        "snapshot_hash": snapshot.snapshot_hash,
        "counts": counts,
        "board_ladder": {key: sorted(value) for key, value in sorted(ladder.items(), key=lambda x: int(x[0]))},
        "board_summary": board_summary,
        "themes": dict(themes.most_common()),
        "strategy_coverage": coverage,
        "miss_reasons": dict(misses.most_common()),
        "pool_rows": [_safe_dict(item) for item in snapshot.facts],
        "attributions": [_safe_dict(item) for item in attributions],
        "label_backfill": [_safe_dict(item) for item in labels],
        "label_summary": label_summary,
        "missing_fields": sorted({field for fact in snapshot.facts for field in fact.missing_fields}),
    }
    lines = [
        f"# {snapshot.trade_date.isoformat()} 东财涨停研究复盘",
        "",
        f"- 运行 ID：{run_id}",
        f"- 数据截止：{payload['data_cutoff']}",
        f"- 归因基准日：{payload['selection_date']}",
        f"- 涨停：{counts['LIMIT_UP']}；炸板：{counts['EXPLODED']}；跌停：{counts['LIMIT_DOWN']}",
        f"- 首板：{board_summary['first_board']}；二板及以上：{board_summary['multi_board']}；最高：{board_summary['max_height']}板",
        "",
        "## 连板梯队",
        "",
    ]
    for height, names in payload["board_ladder"].items():
        lines.append(f"- {height}板：{'、'.join(names)}")
    lines.extend(["", "## 策略覆盖", ""])
    for strategy, stats in coverage.items():
        lines.append(f"- {strategy}：{stats['selected']}/{stats['total']}（{stats['rate']:.1%}）")
    lines.extend(["", "## 前向标签回填", ""])
    for horizon, stats in label_summary.items():
        lines.append(f"- {horizon}：{stats['total']} 条（完整 {stats['complete']}）")
    lines.extend(["", "## 漏选原因", ""])
    for reason, count in payload["miss_reasons"].items():
        lines.append(f"- {reason}：{count}")
    return payload, "\n".join(lines).rstrip() + "\n"
