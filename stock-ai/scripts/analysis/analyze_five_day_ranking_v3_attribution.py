#!/usr/bin/env python3
"""Build one manual train-only market attribution artifact for ranking V3."""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import sys
from typing import Callable, Mapping, Sequence

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis.review_buy_point_case import (  # noqa: E402
    _load_benchmark_index_bars,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (  # noqa: E402
    MarketClosePanel,
    build_five_day_ranking_v3_attribution_review,
    matched_index_id,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution_report import (  # noqa: E402
    write_five_day_ranking_v3_attribution,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_report import (  # noqa: E402
    load_five_day_ranking_v3_train,
)
from stock_ai.buy_point_selection.five_day_return_report import (  # noqa: E402
    five_day_research_payload,
    load_five_day_research,
)
from stock_ai.market_codes import (  # noqa: E402
    is_sh_sz_main_board_code,
    normalize_code6,
)


_INDEX_ORDER = ("sh.000001", "sz.399001", "sh.000688")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    diagnose = commands.add_parser("diagnose-train-attribution")
    diagnose.add_argument("--train-artifact", type=Path, required=True)
    diagnose.add_argument("--research-artifact", type=Path, required=True)
    diagnose.add_argument("--output-dir", type=Path, required=True)
    return parser


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise ValueError("required artifact does not exist")
    return path


def _configured_engine(*, engine_factory: Callable[..., object] = create_engine):
    load_dotenv(ROOT / ".env", override=False)
    mysql_url = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal",
        "127.0.0.1",
    )
    if not mysql_url:
        raise RuntimeError("MYSQL_URL is not configured")
    return engine_factory(mysql_url, pool_pre_ping=True)


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _load_stock_closes(
    engine: object,
    start: date,
    end: date,
) -> dict[str, dict[date, Decimal]]:
    """Load only bounded main-board close rows from the read-only store."""

    statement = text(
        "SELECT ts_code, trade_date, close FROM stock_daily "
        "WHERE trade_date BETWEEN :start AND :end "
        "ORDER BY ts_code, trade_date"
    )
    with engine.connect() as connection:
        rows = connection.execute(
            statement,
            {"start": start, "end": end},
        ).mappings().all()
    closes: dict[str, dict[date, Decimal]] = {}
    for row in rows:
        raw_code = str(row["ts_code"])
        if not is_sh_sz_main_board_code(raw_code):
            continue
        try:
            trade_date = _as_date(row["trade_date"])
            close = Decimal(str(row["close"]))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if not start <= trade_date <= end or not close.is_finite() or close <= 0:
            continue
        code = normalize_code6(raw_code)
        closes.setdefault(code, {})[trade_date] = close
    return {
        code: dict(sorted(values.items()))
        for code, values in sorted(closes.items())
    }


def _load_mysql_stock_closes(
    start: date,
    end: date,
) -> dict[str, dict[date, Decimal]]:
    engine = _configured_engine()
    try:
        return _load_stock_closes(engine, start, end)
    finally:
        dispose = getattr(engine, "dispose", None)
        if callable(dispose):
            dispose()


def _required_index_ids(train_artifact: object) -> tuple[str, ...]:
    payload = train_artifact.payload
    if not isinstance(payload, Mapping):
        raise ValueError("invalid train payload")
    variants = payload.get("variants")
    if not isinstance(variants, list):
        raise ValueError("invalid train payload")
    required: set[str] = set()
    for variant in variants:
        if not isinstance(variant, Mapping):
            raise ValueError("invalid train payload")
        segment = variant.get("segment")
        if not isinstance(segment, Mapping):
            raise ValueError("invalid train payload")
        for field in ("admitted_trade_keys", "ranked_plan_keys"):
            plan_keys = segment.get(field)
            if not isinstance(plan_keys, list):
                raise ValueError("invalid train payload")
            for plan_key in plan_keys:
                if not isinstance(plan_key, Mapping) or "code" not in plan_key:
                    raise ValueError("invalid train payload")
                required.add(matched_index_id(str(plan_key["code"])))
    return tuple(index_id for index_id in _INDEX_ORDER if index_id in required)


def _load_required_benchmark_closes(
    required_index_ids: Sequence[str],
    start: date,
    end: date,
    *,
    benchmark_loader: Callable[[date, date], Mapping[str, Sequence[object]]] = (
        _load_benchmark_index_bars
    ),
) -> dict[str, dict[date, Decimal]]:
    required = tuple(required_index_ids)
    if len(required) != len(set(required)) or any(
        index_id not in _INDEX_ORDER for index_id in required
    ):
        raise ValueError("invalid benchmark registry")
    if not required:
        return {}
    loaded = benchmark_loader(start, end)
    result: dict[str, dict[date, Decimal]] = {}
    for index_id in required:
        bars: dict[date, Decimal] = {}
        for bar in loaded.get(index_id, ()):
            try:
                trade_date = _as_date(bar.trade_date)
                close = Decimal(str(bar.close))
            except (AttributeError, InvalidOperation, TypeError, ValueError):
                continue
            if start <= trade_date <= end and close.is_finite() and close > 0:
                bars[trade_date] = close
        result[index_id] = dict(sorted(bars.items()))
    return result


def _default_benchmark_loader(
    index_ids: Sequence[str],
    start: date,
    end: date,
) -> dict[str, dict[date, Decimal]]:
    return _load_required_benchmark_closes(index_ids, start, end)


def dispatch_command(
    args: argparse.Namespace,
    *,
    stock_loader: Callable[[date, date], Mapping[str, Mapping[date, Decimal]]]
    | None = None,
    benchmark_loader: Callable[
        [Sequence[str], date, date],
        Mapping[str, Mapping[date, Decimal]],
    ]
    | None = None,
    writer: Callable[[object, Path], Path] = (
        write_five_day_ranking_v3_attribution
    ),
) -> Path:
    if args.command != "diagnose-train-attribution":
        raise ValueError("unsupported command")

    train = load_five_day_ranking_v3_train(
        _require_file(args.train_artifact)
    )
    research = load_five_day_research(
        _require_file(args.research_artifact)
    )
    parent_payload = five_day_research_payload(research)
    parent_identity = str(parent_payload["artifact_identity"])
    if (
        parent_identity != train.parent_research_identity
        or research.input_fingerprint != train.parent_input_fingerprint
        or research.split != train.split
        or not research.point_in_time_complete
        or research.test_outcomes_read
    ):
        raise ValueError("parent lineage mismatch")

    train_dates = tuple(train.split.train)
    if not train_dates:
        raise ValueError("train calendar is empty")
    start, end = train_dates[0], train_dates[-1]
    required_indexes = _required_index_ids(train)
    load_stocks = stock_loader or _load_mysql_stock_closes
    load_benchmarks = benchmark_loader or _default_benchmark_loader
    stock_closes = load_stocks(start, end)
    index_closes = (
        load_benchmarks(required_indexes, start, end)
        if required_indexes
        else {}
    )
    review = build_five_day_ranking_v3_attribution_review(
        train,
        research,
        parent_research_identity=parent_identity,
        market_panel=MarketClosePanel(
            train_dates=train_dates,
            stock_closes=stock_closes,
            index_closes=index_closes,
        ),
    )
    return writer(review, args.output_dir)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        path = dispatch_command(build_parser().parse_args(argv))
    except Exception:  # noqa: BLE001 - CLI must not leak provider or URL details
        print("五日排名V3市场归因失败", file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
