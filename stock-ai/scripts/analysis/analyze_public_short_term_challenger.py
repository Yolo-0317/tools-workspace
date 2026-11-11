#!/usr/bin/env python3
"""Run the isolated public short-term strategy challenger manually."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Callable, Sequence

from scripts.analysis.review_buy_point_case import _load_benchmark_index_bars
from stock_ai.buy_point_selection.public_challenger_report import (
    load_challenger_freeze,
    load_challenger_research,
    load_challenger_test,
    write_challenger_freeze,
    write_challenger_research,
    write_challenger_test_once,
    write_challenger_validation,
)
from stock_ai.buy_point_selection.public_challenger_runtime import (
    PublicChallengerRuntimeInputs,
    build_public_challenger_research,
    build_public_challenger_test,
    load_mysql_public_challenger_inputs,
)
from stock_ai.buy_point_selection.public_challenger_validation import (
    PublicChallengerFreezeReview,
    PublicChallengerValidationReview,
    V3ComparableArtifact,
    V3ComparableDay,
)


DEFAULT_OUTPUT_DIR = Path("output/research/public_short_term_challenger")
RuntimeInputLoader = Callable[
    [date, date, date],
    PublicChallengerRuntimeInputs,
]


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "日期必须使用 YYYY-MM-DD 格式"
        ) from error


def _add_output_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(description=__doc__)
    stages = parser.add_subparsers(dest="stage", required=True)

    research = stages.add_parser("research")
    research.add_argument("--signal-start", type=_date, required=True)
    research.add_argument("--signal-end", type=_date, required=True)
    _add_output_dir(research)

    freeze = stages.add_parser("freeze")
    freeze.add_argument("--research-artifact", type=Path, required=True)
    _add_output_dir(freeze)

    test = stages.add_parser("test")
    test.add_argument("--freeze-artifact", type=Path, required=True)
    test.add_argument("--research-artifact", type=Path, required=True)
    test.add_argument("--v3-test-artifact", type=Path)
    _add_output_dir(test)
    return parser


def _mysql_signal_dates(start: date, end: date) -> tuple[date, ...]:
    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    from stock_ai.buy_point_selection.historical_replay_runtime import (
        _trade_dates,
    )

    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env", override=False)
    mysql_url = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal",
        "127.0.0.1",
    )
    if not mysql_url:
        raise RuntimeError("MYSQL_URL is not configured")
    engine = create_engine(mysql_url, pool_pre_ping=True)
    try:
        result = tuple(_trade_dates(engine, start, end))
    finally:
        engine.dispose()
    if not result:
        raise ValueError("指定区间没有已确认交易日")
    return result


def _load_mysql_inputs(
    signal_start: date,
    signal_end: date,
    outcome_cutoff: date,
) -> PublicChallengerRuntimeInputs:
    signal_dates = _mysql_signal_dates(signal_start, signal_end)
    return load_mysql_public_challenger_inputs(
        signal_dates,
        signal_start - timedelta(days=180),
        outcome_cutoff,
        benchmark_loader=_load_benchmark_index_bars,
    )


def _failure_reasons(artifact) -> tuple[str, ...]:
    if artifact.validation_eligible:
        return ()
    assessment = artifact.review.validation_assessment
    values = (
        *assessment.reasons,
        *assessment.execution_metrics.reasons,
        *assessment.portfolio_metrics.reasons,
    )
    if not artifact.review.point_in_time_complete:
        values = (*values, "POINT_IN_TIME_INPUT_INCOMPLETE")
    return tuple(dict.fromkeys(values or ("VALIDATION_NOT_ELIGIBLE",)))


def _frozen_rule_hash() -> str:
    rules = {
        "schema": "public-short-term-challenger-frozen-rules-v1",
        "residual_fraction": "0.10",
        "estimation_sessions": 60,
        "signal_sessions": 5,
        "minimum_sector_members": 10,
        "confirmation_sessions": 2,
        "reclaim_close_location": "0.60",
        "chase_cap": "0.03",
        "atr_buffer": "0.2",
        "minimum_risk_fraction": "0.015",
        "maximum_risk_fraction": "0.05",
        "holding_sessions": 5,
    }
    raw = json.dumps(rules, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_v3_comparable(path: Path) -> V3ComparableArtifact:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("V3 comparable artifact invalid") from error
    expected = {
        "schema",
        "artifact_identity",
        "parent_research_identity",
        "input_fingerprint",
        "split_identity",
        "days",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("V3 comparable artifact invalid")
    content = {
        key: value for key, value in payload.items() if key != "artifact_identity"
    }
    raw = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    identity = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if (
        payload["schema"] != "five-day-ranking-v3-comparable-test-v1"
        or payload["artifact_identity"] != identity
        or not isinstance(payload["days"], list)
    ):
        raise ValueError("V3 comparable artifact invalid")
    days: list[V3ComparableDay] = []
    for item in payload["days"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"signal_date", "selected_keys", "net_return"}
            or not isinstance(item["selected_keys"], list)
            or any(not isinstance(value, str) for value in item["selected_keys"])
            or len(item["selected_keys"]) != len(set(item["selected_keys"]))
        ):
            raise ValueError("V3 comparable artifact invalid")
        try:
            signal_date = date.fromisoformat(str(item["signal_date"]))
            net_return = Decimal(str(item["net_return"]))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("V3 comparable artifact invalid") from error
        if not net_return.is_finite():
            raise ValueError("V3 comparable artifact invalid")
        days.append(
            V3ComparableDay(
                signal_date=signal_date,
                selected_keys=frozenset(item["selected_keys"]),
                net_return=net_return,
            )
        )
    return V3ComparableArtifact(
        schema=str(payload["schema"]),
        parent_research_identity=str(payload["parent_research_identity"]),
        input_fingerprint=str(payload["input_fingerprint"]),
        split_identity=str(payload["split_identity"]),
        days=tuple(days),
    )


def dispatch_stage(
    args: argparse.Namespace,
    research_input_loader: RuntimeInputLoader,
    test_input_loader: RuntimeInputLoader,
) -> tuple[Path, ...]:
    output_dir = Path(args.output_dir)
    if args.stage == "research":
        if args.signal_start > args.signal_end:
            raise ValueError("signal-start 不能晚于 signal-end")
        inputs = research_input_loader(
            args.signal_start,
            args.signal_end,
            args.signal_end,
        )
        review = build_public_challenger_research(inputs)
        return (write_challenger_research(review, output_dir),)

    if args.stage == "freeze":
        research = load_challenger_research(Path(args.research_artifact))
        reasons = _failure_reasons(research)
        validation = PublicChallengerValidationReview(
            parent_research_identity=research.artifact_identity,
            input_fingerprint=research.input_fingerprint,
            assessment=research.review.validation_assessment,
            test_eligible=research.validation_eligible,
            reasons=reasons,
        )
        validation_path = write_challenger_validation(validation, output_dir)
        freeze = PublicChallengerFreezeReview(
            parent_research_identity=research.artifact_identity,
            input_fingerprint=research.input_fingerprint,
            split_identity=research.split_identity,
            frozen_rule_hash=_frozen_rule_hash(),
            test_eligible=research.validation_eligible,
            reasons=reasons,
        )
        freeze_path = write_challenger_freeze(freeze, output_dir)
        return validation_path, freeze_path

    freeze = load_challenger_freeze(Path(args.freeze_artifact))
    research = load_challenger_research(Path(args.research_artifact))
    if (
        freeze.parent_research_identity != research.artifact_identity
        or freeze.input_fingerprint != research.input_fingerprint
        or freeze.split_identity != research.split_identity
    ):
        raise ValueError("public challenger parent lineage mismatch")
    if not freeze.test_eligible:
        raise ValueError("freeze is not test eligible")
    existing_path = output_dir / (
        f"public-short-term-challenger-test-{freeze.artifact_identity}.json"
    )
    if existing_path.exists():
        existing = load_challenger_test(existing_path)
        if (
            existing.parent_freeze_identity != freeze.artifact_identity
            or existing.parent_research_identity != research.artifact_identity
            or existing.input_fingerprint != research.input_fingerprint
        ):
            raise ValueError("public challenger test artifact conflict")
        return (existing_path,)
    v3 = (
        _load_v3_comparable(Path(args.v3_test_artifact))
        if args.v3_test_artifact is not None
        else None
    )
    split = research.review.split
    inputs = test_input_loader(
        split.train[0],
        split.test[-1],
        split.test[-1],
    )
    review = build_public_challenger_test(
        freeze,
        research.review,
        inputs,
        v3,
    )
    return (write_challenger_test_once(review, output_dir),)


def main(
    argv: Sequence[str] | None = None,
    *,
    research_input_loader: RuntimeInputLoader = _load_mysql_inputs,
    test_input_loader: RuntimeInputLoader = _load_mysql_inputs,
) -> int:
    try:
        args = build_parser().parse_args(argv)
        paths = dispatch_stage(
            args,
            research_input_loader,
            test_input_loader,
        )
    except (RuntimeError, ValueError):
        print("公开短线策略挑战者执行失败", file=sys.stderr)
        return 2
    print("\n".join(str(path) for path in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
