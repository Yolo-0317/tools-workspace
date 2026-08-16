#!/usr/bin/env python3
"""Run the isolated five-day net-return research stages manually."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Callable, Sequence

from scripts.analysis.review_buy_point_case import _load_benchmark_index_bars
from stock_ai.buy_point_selection.five_day_return_report import (
    five_day_research_payload,
    load_five_day_forward_screen,
    load_five_day_freeze,
    load_five_day_research,
    load_five_day_test,
    write_five_day_forward_screen,
    write_five_day_forward_settlement,
    write_five_day_freeze,
    write_five_day_research,
    write_five_day_test_once,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayRuntimeInputs,
    build_five_day_forward_screen,
    build_five_day_forward_settlement,
    build_five_day_research_review,
    build_five_day_test_review,
    load_mysql_five_day_inputs,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    evaluate_validation_freeze,
)
from stock_ai.buy_point_selection.validation import chronological_split


DEFAULT_OUTPUT_DIR = Path("output/research/buy_point_five_day_returns")
RuntimeInputLoader = Callable[[date, date, date], FiveDayRuntimeInputs]


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "日期必须使用 YYYY-MM-DD 格式"
        ) from exc


def _add_output_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
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
    _add_output_dir(test)

    screen = stages.add_parser("forward-screen")
    screen.add_argument("--signal-date", type=_date, required=True)
    screen.add_argument("--freeze-artifact", type=Path, required=True)
    screen.add_argument("--test-artifact", type=Path, required=True)
    _add_output_dir(screen)

    settlement = stages.add_parser("forward-settlement")
    settlement.add_argument("--screen-artifact", type=Path, required=True)
    settlement.add_argument("--outcome-cutoff", type=_date, required=True)
    _add_output_dir(settlement)
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
        values = tuple(_trade_dates(engine, start, end))
    finally:
        engine.dispose()
    if not values:
        raise ValueError("指定区间没有已确认交易日")
    return values


def _load_mysql_research_inputs(
    signal_start: date,
    signal_end: date,
    _available_through: date,
) -> FiveDayRuntimeInputs:
    signal_dates = _mysql_signal_dates(signal_start, signal_end)
    split = chronological_split(signal_dates)
    return load_mysql_five_day_inputs(
        signal_dates,
        split.train[0] - timedelta(days=180),
        split.validation[-1],
        split.test[9],
        benchmark_loader=_load_benchmark_index_bars,
    )


def _load_mysql_range_inputs(
    signal_start: date,
    signal_end: date,
    outcome_cutoff: date,
) -> FiveDayRuntimeInputs:
    signal_dates = _mysql_signal_dates(signal_start, signal_end)
    return load_mysql_five_day_inputs(
        signal_dates,
        signal_start - timedelta(days=180),
        signal_end,
        outcome_cutoff,
        benchmark_loader=_load_benchmark_index_bars,
    )


def _child_inputs(
    inputs: FiveDayRuntimeInputs,
    parent_fingerprint: str,
) -> FiveDayRuntimeInputs:
    prefix = f"{parent_fingerprint}:"
    if inputs.input_fingerprint.startswith(prefix):
        return inputs
    return replace(
        inputs,
        input_fingerprint=f"{prefix}{inputs.input_fingerprint}",
    )


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValueError(f"{label}不存在：{path}")
    return path


def _read_payload(path: Path, label: str) -> dict[str, object]:
    _require_file(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}无法读取：{path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}格式无效：{path}")
    return value


def _resolve_artifact(
    filename: str,
    output_dir: Path,
    *parents: Path,
) -> Path:
    directories = tuple(
        dict.fromkeys((*(value.parent for value in parents), output_dir))
    )
    for directory in directories:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    raise ValueError(f"找不到父产物：{filename}")


def _research_path_for_freeze(
    freeze_path: Path,
    output_dir: Path,
    *parents: Path,
) -> Path:
    payload = _read_payload(freeze_path, "冻结产物")
    identity = str(payload.get("parent_research_identity") or "")
    if len(identity) != 64:
        raise ValueError("冻结产物缺少有效研究父身份")
    return _resolve_artifact(
        f"research-{identity}.json",
        output_dir,
        freeze_path,
        *parents,
    )


def dispatch_stage(
    args: argparse.Namespace,
    research_input_loader: RuntimeInputLoader,
    test_input_loader: RuntimeInputLoader,
    forward_input_loader: RuntimeInputLoader,
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
        review = build_five_day_research_review(
            inputs.signal_dates,
            input_loader=lambda *_: inputs,
        )
        return (write_five_day_research(review, output_dir),)

    if args.stage == "freeze":
        research_path = _require_file(
            args.research_artifact,
            "研究产物",
        )
        research = load_five_day_research(research_path)
        if not research.point_in_time_complete or research.test_outcomes_read:
            raise ValueError("研究产物点时覆盖不完整")
        research_identity = str(
            five_day_research_payload(research)["artifact_identity"]
        )
        freeze = evaluate_validation_freeze(
            research.observations,
            train_dates=research.split.train,
            validation_dates=research.split.validation,
            profile_matrix_hash=research.profile_matrix_hash,
            research_identity=research_identity,
        )
        return (write_five_day_freeze(freeze, output_dir),)

    if args.stage == "test":
        research_path = _require_file(
            args.research_artifact,
            "研究产物",
        )
        freeze_path = _require_file(args.freeze_artifact, "冻结产物")
        research = load_five_day_research(research_path)
        freeze = load_five_day_freeze(freeze_path, research_path)
        raw_inputs = test_input_loader(
            research.split.test[0],
            research.split.test[-1],
            research.split.test[-1] + timedelta(days=30),
        )
        inputs = _child_inputs(raw_inputs, research.input_fingerprint)
        review = build_five_day_test_review(freeze, research, inputs)
        return (write_five_day_test_once(review, output_dir),)

    if args.stage == "forward-screen":
        freeze_path = _require_file(args.freeze_artifact, "冻结产物")
        test_path = _require_file(args.test_artifact, "测试产物")
        research_path = _research_path_for_freeze(
            freeze_path,
            output_dir,
            test_path,
        )
        freeze = load_five_day_freeze(freeze_path, research_path)
        test = load_five_day_test(test_path, freeze_path, research_path)
        raw_inputs = forward_input_loader(
            args.signal_date,
            args.signal_date,
            args.signal_date + timedelta(days=14),
        )
        inputs = _child_inputs(raw_inputs, test.input_fingerprint)
        screen = build_five_day_forward_screen(
            freeze,
            test,
            args.signal_date,
            inputs,
        )
        return (write_five_day_forward_screen(screen, output_dir),)

    screen_path = _require_file(args.screen_artifact, "前向筛选产物")
    screen_payload = _read_payload(screen_path, "前向筛选产物")
    freeze_hash = str(screen_payload.get("parent_freeze_hash") or "")
    if len(freeze_hash) != 64:
        raise ValueError("前向筛选产物缺少有效冻结父身份")
    freeze_path = _resolve_artifact(
        f"freeze-{freeze_hash}.json",
        output_dir,
        screen_path,
    )
    test_path = _resolve_artifact(
        f"test-{freeze_hash}.json",
        output_dir,
        screen_path,
    )
    research_path = _research_path_for_freeze(
        freeze_path,
        output_dir,
        screen_path,
        test_path,
    )
    screen = load_five_day_forward_screen(
        screen_path,
        freeze_path,
        test_path,
        research_path,
    )
    raw_inputs = forward_input_loader(
        screen.signal_date,
        screen.signal_date,
        args.outcome_cutoff,
    )
    inputs = _child_inputs(raw_inputs, screen.input_fingerprint)
    settlement = build_five_day_forward_settlement(
        screen,
        inputs,
        args.outcome_cutoff,
    )
    return (write_five_day_forward_settlement(settlement, output_dir),)


def main(
    argv: Sequence[str] | None = None,
    *,
    research_input_loader: RuntimeInputLoader = _load_mysql_research_inputs,
    test_input_loader: RuntimeInputLoader = _load_mysql_range_inputs,
    forward_input_loader: RuntimeInputLoader = _load_mysql_range_inputs,
) -> int:
    try:
        args = build_parser().parse_args(argv)
        paths = dispatch_stage(
            args,
            research_input_loader,
            test_input_loader,
            forward_input_loader,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"五日净收益影子研究失败：{exc}", file=sys.stderr)
        return 2
    print("\n".join(str(path) for path in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
