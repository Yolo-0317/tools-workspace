#!/usr/bin/env python3
"""Build one manual train-only score-component diagnosis for ranking V3."""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
from typing import Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis.review_buy_point_case import (  # noqa: E402
    _load_benchmark_index_bars,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (  # noqa: E402
    MarketClosePanel,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution_market import (  # noqa: E402
    load_mysql_stock_closes,
    load_required_benchmark_closes,
    required_index_ids,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution_report import (  # noqa: E402
    load_five_day_ranking_v3_attribution,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_component_attribution import (  # noqa: E402
    build_five_day_ranking_v3_component_attribution_review,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_component_attribution_report import (  # noqa: E402
    write_five_day_ranking_v3_component_attribution,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_report import (  # noqa: E402
    load_five_day_ranking_v3_train,
)
from stock_ai.buy_point_selection.five_day_return_report import (  # noqa: E402
    five_day_research_payload,
    load_five_day_research,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    diagnose = commands.add_parser("diagnose-ranking-components")
    diagnose.add_argument("--train-artifact", type=Path, required=True)
    diagnose.add_argument("--research-artifact", type=Path, required=True)
    diagnose.add_argument(
        "--market-attribution-artifact",
        type=Path,
        required=True,
    )
    diagnose.add_argument("--output-dir", type=Path, required=True)
    return parser


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise ValueError("required artifact does not exist")
    return path


def _default_benchmark_loader(
    index_ids: Sequence[str],
    start: date,
    end: date,
) -> dict[str, dict[date, Decimal]]:
    return load_required_benchmark_closes(
        index_ids,
        start,
        end,
        benchmark_loader=_load_benchmark_index_bars,
    )


def dispatch_command(
    args: argparse.Namespace,
    *,
    stock_loader: Callable[
        [date, date], Mapping[str, Mapping[date, Decimal]]
    ]
    | None = None,
    benchmark_loader: Callable[
        [Sequence[str], date, date],
        Mapping[str, Mapping[date, Decimal]],
    ]
    | None = None,
    writer: Callable[[object, Path], Path] = (
        write_five_day_ranking_v3_component_attribution
    ),
) -> Path:
    if args.command != "diagnose-ranking-components":
        raise ValueError("unsupported command")

    train = load_five_day_ranking_v3_train(
        _require_file(args.train_artifact)
    )
    research = load_five_day_research(
        _require_file(args.research_artifact)
    )
    research_payload = five_day_research_payload(research)
    parent_identity = str(research_payload["artifact_identity"])
    if (
        parent_identity != train.parent_research_identity
        or research.input_fingerprint != train.parent_input_fingerprint
        or research.split != train.split
        or not research.point_in_time_complete
        or research.test_outcomes_read
    ):
        raise ValueError("parent lineage mismatch")

    parent_attribution = load_five_day_ranking_v3_attribution(
        _require_file(args.market_attribution_artifact),
        expected_parent_train_identity=train.artifact_identity,
        expected_parent_research_identity=parent_identity,
    )
    parent_payload = parent_attribution.payload
    if (
        parent_attribution.status != "COMPLETE"
        or parent_attribution.parent_input_fingerprint
        != research.input_fingerprint
        or not isinstance(parent_payload, Mapping)
        or parent_payload.get("split") != train.payload.get("split")
        or parent_payload.get("train_only") is not True
        or parent_payload.get("validation_outcomes_read") is not False
        or parent_payload.get("test_outcomes_read") is not False
        or parent_payload.get("promotion_eligible") is not False
        or parent_payload.get("trade_permission") != "NO-TRADE"
    ):
        raise ValueError("parent attribution is incomplete")

    train_dates = tuple(train.split.train)
    if not train_dates:
        raise ValueError("train calendar is empty")
    start, end = train_dates[0], train_dates[-1]
    required_indexes = required_index_ids(train)
    load_stocks = stock_loader or load_mysql_stock_closes
    load_benchmarks = benchmark_loader or _default_benchmark_loader
    stock_closes = load_stocks(start, end)
    index_closes = (
        load_benchmarks(required_indexes, start, end)
        if required_indexes
        else {}
    )
    review = build_five_day_ranking_v3_component_attribution_review(
        train,
        research,
        parent_attribution,
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
    except Exception:  # noqa: BLE001 - never leak provider or credential data
        print("五日排名V3组件归因失败", file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
