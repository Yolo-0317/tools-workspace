#!/usr/bin/env python3
"""Run five-day ranking diagnostics in two explicit manual stages."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from stock_ai.buy_point_selection.five_day_ranking_report import (
    build_five_day_ranking_validation_review,
    load_five_day_ranking_train,
    load_five_day_ranking_validation,
    validation_trial_identity,
    write_five_day_ranking_validation,
    write_five_day_ranking_train,
)
from stock_ai.buy_point_selection.five_day_ranking_research import (
    build_five_day_ranking_train_review,
)
from stock_ai.buy_point_selection.five_day_return_report import (
    five_day_research_payload,
    load_five_day_research,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    diagnose = commands.add_parser("diagnose-train")
    diagnose.add_argument("--research-artifact", type=Path, required=True)
    diagnose.add_argument("--output-dir", type=Path, required=True)

    validate = commands.add_parser("validate-ranking")
    validate.add_argument("--train-artifact", type=Path, required=True)
    validate.add_argument("--research-artifact", type=Path, required=True)
    validate.add_argument("--output-dir", type=Path, required=True)
    return parser


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValueError(f"{label}不存在")
    return path


def dispatch_command(args: argparse.Namespace) -> Path:
    if args.command == "diagnose-train":
        research_path = _require_file(args.research_artifact, "研究产物")
        research = load_five_day_research(research_path)
        if not research.point_in_time_complete or research.test_outcomes_read:
            raise ValueError("研究产物点时覆盖不完整")
        parent_identity = str(
            five_day_research_payload(research)["artifact_identity"]
        )
        review = build_five_day_ranking_train_review(
            research,
            parent_research_identity=parent_identity,
        )
        return write_five_day_ranking_train(review, args.output_dir)

    train_path = _require_file(args.train_artifact, "训练诊断产物")
    train = load_five_day_ranking_train(train_path)
    trial_identity = validation_trial_identity(
        train.artifact_identity,
        train.registered_validation_policy_hash,
    )
    validation_path = (
        Path(args.output_dir)
        / f"ranking-validation-{trial_identity}.json"
    )
    if validation_path.is_file():
        existing = load_five_day_ranking_validation(validation_path)
        if (
            existing.parent_train_identity != train.artifact_identity
            or existing.parent_research_identity
            != train.parent_research_identity
            or existing.registered_validation_policy_hash
            != train.registered_validation_policy_hash
        ):
            raise ValueError("验证产物父链不匹配")
        return validation_path

    research_path = _require_file(args.research_artifact, "研究产物")
    research = load_five_day_research(research_path)
    parent_identity = str(
        five_day_research_payload(research)["artifact_identity"]
    )
    if (
        parent_identity != train.parent_research_identity
        or research.input_fingerprint != train.parent_input_fingerprint
    ):
        raise ValueError("研究产物与训练诊断父链不匹配")
    review = build_five_day_ranking_validation_review(research, train)
    return write_five_day_ranking_validation(review, args.output_dir)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        path = dispatch_command(args)
    except (OSError, RuntimeError, ValueError):
        print("五日排名诊断失败", file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
