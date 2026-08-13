#!/usr/bin/env python3
"""Manually collect and review the Eastmoney limit-up research ledger."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Callable, Mapping

from dotenv import load_dotenv
from sqlalchemy import text

from stock_ai.limit_up_research import (
    StrategySnapshot,
    build_research_report,
    build_selection_attributions,
    compute_forward_labels,
    normalize_topic_pools,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = "eastmoney-opencli-topic-pool"
STRATEGIES = (
    "short_term_trade", "combined", "five_factor", "ma5", "watch",
    "bottom_breakout", "limit_up_gene_watch",
)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def run_pipeline(
    *,
    trade_date: date,
    selection_date: date,
    output_dir: Path,
    collector: Callable[[date], Mapping],
    start_run: Callable[[date], int],
    load_snapshots: Callable[[date], Mapping[str, StrategySnapshot]],
    load_labels: Callable[[tuple], tuple],
    save_bundle: Callable,
    finish_run: Callable,
    load_explainers: Callable[[date, tuple[str, ...]], Mapping] = lambda _date, _codes: {},
    now: Callable[[], datetime] = datetime.now,
) -> dict:
    run_id = start_run(trade_date)
    try:
        pools = collector(trade_date)
        snapshot = normalize_topic_pools(pools, trade_date)
        if not snapshot.facts:
            raise RuntimeError("东财三类题材池同时为空，拒绝保存为成功快照")
        limit_codes = tuple(
            fact.code for fact in snapshot.facts if fact.pool_kind == "LIMIT_UP"
        )
        attributions = build_selection_attributions(
            trade_date=trade_date,
            selection_date=selection_date,
            limit_up_codes=limit_codes,
            snapshots=load_snapshots(selection_date),
            explainers=load_explainers(selection_date, limit_codes),
        )
        labels = tuple(load_labels(snapshot.facts))
        persisted = save_bundle(run_id, trade_date, snapshot.facts, attributions, labels)
        payload, markdown = build_research_report(
            run_id=run_id,
            snapshot=snapshot,
            attributions=attributions,
            labels=labels,
            selection_date=selection_date,
            data_cutoff=now(),
        )
        json_path = output_dir / f"{trade_date.isoformat()}.json"
        md_path = output_dir / f"{trade_date.isoformat()}.md"
        _atomic_write(json_path, json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
        _atomic_write(md_path, markdown)
        counts = {
            kind: sum(1 for fact in snapshot.facts if fact.pool_kind == kind)
            for kind in ("LIMIT_UP", "EXPLODED", "LIMIT_DOWN")
        }
        finish_run(
            run_id,
            status="SUCCEEDED",
            snapshot_hash=snapshot.snapshot_hash,
            counts=counts,
            missing_fields=payload["missing_fields"],
            raw_meta={"persisted": persisted, "reports": [str(json_path), str(md_path)]},
        )
        return {
            "run_id": run_id,
            "trade_date": trade_date.isoformat(),
            "selection_date": selection_date.isoformat(),
            "counts": counts,
            "persisted": persisted,
            "json_report": str(json_path),
            "markdown_report": str(md_path),
        }
    except Exception as exc:
        finish_run(run_id, status="FAILED", error=str(exc))
        raise


def _resolve_date(engine, explicit: str | None) -> date:
    if explicit:
        return date.fromisoformat(explicit)
    today = datetime.now().date()
    operator = "<=" if datetime.now().hour >= 15 else "<"
    with engine.connect() as conn:
        value = conn.execute(
            text(f"SELECT MAX(trade_date) FROM stock_daily WHERE trade_date {operator} :d"),
            {"d": today.isoformat()},
        ).scalar()
    if value is None:
        raise RuntimeError("stock_daily 无可用已收盘交易日")
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _selection_snapshots(trade_date: date, engine) -> dict[str, StrategySnapshot]:
    from scripts.tools.portfolio_db import load_selection_daily_results

    snapshots = {}
    for strategy in STRATEGIES:
        resolved, rows = load_selection_daily_results(
            trade_date, strategy=strategy, engine=engine, enrich_names=False
        )
        snapshots[strategy] = StrategySnapshot(
            ran=resolved == trade_date,
            rows=tuple(rows),
            retained_limit=5,
        )
    return snapshots


def _previous_market_date(engine, trade_date: date) -> date:
    with engine.connect() as conn:
        value = conn.execute(
            text("SELECT MAX(trade_date) FROM stock_daily WHERE trade_date < :d"),
            {"d": trade_date.isoformat()},
        ).scalar()
    if value is None:
        raise RuntimeError("目标日前无前一交易日")
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _gene_explainers(engine, selection_date: date, codes: tuple[str, ...]) -> dict:
    if not codes:
        return {}
    from core_v2.board_filters import passes_base_filter
    from stock_ai.limit_up_research.attribution import ExplainResult, explain_limit_up_gene_result
    from stock_ai.limit_up_logic import LimitUpContext, analyze_limit_up_logic

    params = {"d": selection_date, **{f"c{i}": code for i, code in enumerate(codes)}}
    placeholders = ",".join(f":c{i}" for i in range(len(codes)))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT ts_code, trade_date, open, high, low, close, pct_chg, amount "
                "FROM stock_daily WHERE trade_date <= :d "
                f"AND LEFT(ts_code,6) IN ({placeholders}) ORDER BY ts_code, trade_date"
            ),
            params,
        ).fetchall()
    by_code = defaultdict(list)
    for row in rows:
        item = dict(row._mapping)
        code = str(item.pop("ts_code")).split(".")[0].zfill(6)
        by_code[code].append(item)

    def explain(code: str):
        bars = by_code.get(code, ())
        if not bars:
            return ExplainResult(
                "DATA_MISSING", ("DAILY_BARS_MISSING",), {}, "limit-up-gene-watch-1.0.0"
            )
        result = analyze_limit_up_logic(
            code, code, bars[-120:], LimitUpContext(observed_at=datetime.combine(selection_date, datetime.min.time()))
        )
        latest = bars[-1]
        explanation = explain_limit_up_gene_result(
            result,
            amount_wan=float(latest.get("amount") or 0.0) / 10.0,
            base_filter_passed=passes_base_filter(
                code, float(latest.get("close") or 0.0), float(latest.get("amount") or 0.0)
            ),
        )
        return explanation or ExplainResult(
            "DATA_MISSING",
            ("PERSISTED_CANDIDATE_MISSING",),
            {"selection_date": selection_date.isoformat()},
            "limit-up-gene-watch-1.0.0",
        )

    return {"limit_up_gene_watch": explain}


def _due_labels(engine, current_facts=()) -> tuple:
    with engine.connect() as conn:
        stored_samples = conn.execute(
            text(
                "SELECT DISTINCT trade_date, ts_code FROM limit_up_research_pool "
                "WHERE pool_kind='LIMIT_UP' ORDER BY trade_date, ts_code"
            )
        ).fetchall()
        samples = {
            (
                row.trade_date if isinstance(row.trade_date, date)
                else date.fromisoformat(str(row.trade_date)[:10]),
                str(row.ts_code).split(".")[0].zfill(6),
            )
            for row in stored_samples
        }
        samples.update(
            (fact.trade_date, fact.code)
            for fact in current_facts
            if fact.pool_kind == "LIMIT_UP"
        )
        if not samples:
            return ()
        start = min(signal for signal, _code in samples)
        market_dates = tuple(
            row[0] for row in conn.execute(
                text("SELECT DISTINCT trade_date FROM stock_daily WHERE trade_date >= :d ORDER BY trade_date"),
                {"d": start},
            ).fetchall()
        )
        codes = sorted({code for _signal, code in samples})
        params = {"start": start, **{f"c{i}": code for i, code in enumerate(codes)}}
        placeholders = ",".join(f":c{i}" for i in range(len(codes)))
        bars = conn.execute(
            text(
                "SELECT ts_code, trade_date, high, low, close, pct_chg FROM stock_daily "
                f"WHERE trade_date >= :start AND LEFT(ts_code,6) IN ({placeholders}) "
                "ORDER BY ts_code, trade_date"
            ),
            params,
        ).fetchall()
    by_code = defaultdict(list)
    for row in bars:
        item = dict(row._mapping)
        by_code[str(item.pop("ts_code")).split(".")[0].zfill(6)].append(item)
    labels = []
    for signal, code in sorted(samples):
        labels.extend(compute_forward_labels(signal, code, by_code.get(code, ()), market_dates))
    return tuple(labels)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="东财涨停研究账本手动采集与复盘")
    parser.add_argument("--date", help="已收盘交易日 YYYY-MM-DD；默认最近已收盘交易日")
    parser.add_argument("--output-dir", default="output/research/limit_up")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    from scripts.tools.fetch_eastmoney_quotes import fetch_emotion_topic_pools_opencli
    from scripts.tools.portfolio_db import (
        finish_limit_up_research_run,
        get_engine,
        save_limit_up_research_bundle,
        start_limit_up_research_run,
    )

    engine = get_engine()
    if engine is None:
        print(json.dumps({"ok": False, "error": "未配置 MYSQL_URL"}, ensure_ascii=False), file=sys.stderr)
        return 1
    try:
        td = _resolve_date(engine, args.date)
        selection_date = _previous_market_date(engine, td)
        result = run_pipeline(
            trade_date=td,
            selection_date=selection_date,
            output_dir=ROOT / args.output_dir,
            collector=lambda value: fetch_emotion_topic_pools_opencli(value.isoformat()),
            start_run=lambda value: start_limit_up_research_run(value, source=SOURCE, engine=engine),
            load_snapshots=lambda value: _selection_snapshots(value, engine),
            load_explainers=lambda value, codes: _gene_explainers(engine, value, codes),
            load_labels=lambda facts: _due_labels(engine, facts),
            save_bundle=lambda *values: save_limit_up_research_bundle(*values, engine=engine),
            finish_run=lambda *values, **kwargs: finish_limit_up_research_run(*values, **kwargs, engine=engine),
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
