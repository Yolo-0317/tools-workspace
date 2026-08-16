#!/usr/bin/env python3
"""Run five-day ranking V2 in two explicit manual stages."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from stock_ai.buy_point_selection.five_day_ranking_v2 import (
    build_five_day_ranking_v2_train_review,
    build_five_day_ranking_v2_validation_review,
    v2_validation_trial_identity,
)
from stock_ai.buy_point_selection.five_day_ranking_v2_report import (
    load_five_day_ranking_v2_train,
    load_five_day_ranking_v2_validation,
    write_five_day_ranking_v2_train,
    write_five_day_ranking_v2_validation,
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


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise ValueError("required artifact does not exist")
    return path


def dispatch_command(args: argparse.Namespace) -> Path:
    if args.command == "diagnose-train":
        research = load_five_day_research(
            _require_file(args.research_artifact)
        )
        if (
            not research.point_in_time_complete
            or research.test_outcomes_read
        ):
            raise ValueError("research artifact is not train-safe")
        parent_identity = str(
            five_day_research_payload(research)["artifact_identity"]
        )
        review = build_five_day_ranking_v2_train_review(
            research,
            parent_research_identity=parent_identity,
        )
        return write_five_day_ranking_v2_train(
            review,
            args.output_dir,
        )

    train = load_five_day_ranking_v2_train(
        _require_file(args.train_artifact)
    )
    if (
        not train.validation_eligible
        or train.winner_policy_id is None
        or train.winner_policy_hash is None
    ):
        raise ValueError("ranking v2 train artifact has no winner")

    trial_identity = v2_validation_trial_identity(
        train.artifact_identity,
        train.winner_policy_hash,
    )
    validation_path = (
        Path(args.output_dir)
        / f"ranking-v2-validation-{trial_identity}.json"
    )
    if validation_path.is_file():
        load_five_day_ranking_v2_validation(
            validation_path,
            expected_train_identity=train.artifact_identity,
            expected_policy_hash=train.winner_policy_hash,
        )
        return validation_path

    research = load_five_day_research(
        _require_file(args.research_artifact)
    )
    parent_identity = str(
        five_day_research_payload(research)["artifact_identity"]
    )
    if (
        parent_identity != train.parent_research_identity
        or research.input_fingerprint
        != train.parent_input_fingerprint
    ):
        raise ValueError("ranking v2 parent lineage mismatch")
    review = build_five_day_ranking_v2_validation_review(
        research,
        train,
        parent_research_identity=parent_identity,
    )
    return write_five_day_ranking_v2_validation(
        review,
        args.output_dir,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        path = dispatch_command(build_parser().parse_args(argv))
    except (OSError, RuntimeError, TypeError, ValueError):
        print("五日排名V2诊断失败", file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
