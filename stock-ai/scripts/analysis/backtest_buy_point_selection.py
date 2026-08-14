#!/usr/bin/env python3
"""Freeze and evaluate the buy-point selector without test-set tuning."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from stock_ai.buy_point_selection.models import SelectionPolicy, SetupType
from stock_ai.buy_point_selection.validation import (
    TradeObservation,
    ValidationError,
    chronological_split,
    compute_metrics,
    evaluate_promotion,
    metrics_payload,
    policy_hash,
    write_artifact,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--research-train-validation", action="store_true")
    modes.add_argument("--freeze-profile", action="store_true")
    modes.add_argument("--run-test", action="store_true")
    parser.add_argument("--trading-dates", type=Path, required=True)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--profile", type=Path, default=Path("stock-ai/config/buy_point_selection_profile.json"))
    parser.add_argument("--artifact", type=Path, default=Path("stock-ai/config/buy_point_selection_validation.json"))
    parser.add_argument("--write-artifact", action="store_true")
    parser.add_argument("--point-in-time-complete", action="store_true")
    return parser


def _load_dates(path: Path) -> tuple[date, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(date.fromisoformat(str(value)) for value in payload)


def _load_observations(path: Path | None) -> tuple[TradeObservation, ...]:
    if path is None:
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        TradeObservation(
            exit_date=date.fromisoformat(str(value["exit_date"])),
            setup_type=SetupType(str(value["setup_type"])),
            sector_code=str(value["sector_code"]),
            net_return=Decimal(str(value["net_return"])),
            net_pnl=Decimal(str(value["net_pnl"])),
        )
        for value in payload
    )


def _split_bounds(split) -> dict[str, Any]:
    return {
        "train": [split.train[0].isoformat(), split.train[-1].isoformat(), len(split.train)],
        "validation": [
            split.validation[0].isoformat(),
            split.validation[-1].isoformat(),
            len(split.validation),
        ],
        "test": [split.test[0].isoformat(), split.test[-1].isoformat(), len(split.test)],
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    policy = SelectionPolicy()
    try:
        trading_dates = _load_dates(args.trading_dates)
        split = chronological_split(trading_dates)
        current_hash = policy_hash(policy)
        bounds = _split_bounds(split)

        if args.freeze_profile:
            write_artifact(
                args.profile,
                {
                    "schema": "buy-point-selection-frozen-profile-v1",
                    "rule_version": policy.rule_version,
                    "policy_hash": current_hash,
                    "split_bounds": bounds,
                },
            )
            return 0

        observations = _load_observations(args.observations)
        if args.research_train_validation:
            allowed = frozenset((*split.train, *split.validation))
            research = tuple(value for value in observations if value.exit_date in allowed)
            metrics = compute_metrics(
                research,
                test_dates=(),
                trading_dates=(*split.train, *split.validation),
                point_in_time_complete=args.point_in_time_complete,
            )
            _print_json({"technical_core_metrics": metrics_payload(metrics), "split_bounds": bounds})
            return 0

        if not args.profile.exists():
            raise ValidationError("frozen profile is required before --run-test")
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        if profile.get("schema") != "buy-point-selection-frozen-profile-v1":
            raise ValidationError("frozen profile schema mismatch")
        if profile.get("rule_version") != policy.rule_version:
            raise ValidationError("frozen profile rule version mismatch")
        if profile.get("policy_hash") != current_hash:
            raise ValidationError("frozen profile hash mismatch")
        if profile.get("split_bounds") != bounds:
            raise ValidationError("frozen profile split bounds mismatch")
        if args.artifact.exists():
            existing = json.loads(args.artifact.read_text(encoding="utf-8"))
            if (
                existing.get("rule_version") == policy.rule_version
                and existing.get("policy_hash") != current_hash
            ):
                raise ValidationError("a different test hash already exists for this rule version")

        metrics = compute_metrics(
            observations,
            test_dates=split.test,
            trading_dates=trading_dates,
            point_in_time_complete=args.point_in_time_complete,
        )
        decision = evaluate_promotion(metrics)
        payload = {
            "schema": "buy-point-selection-validation-v1",
            "rule_version": policy.rule_version,
            "policy_hash": current_hash,
            "split_bounds": bounds,
            "promoted": decision.promoted,
            "reasons": list(decision.reasons),
            "setup_decisions": {
                key: {"promoted": value.promoted, "reasons": list(value.reasons)}
                for key, value in decision.setup_decisions.items()
            },
            "technical_core_metrics": metrics_payload(metrics),
            "fully_gated_metrics": (
                metrics_payload(metrics) if args.point_in_time_complete else None
            ),
            "costs": {
                "commission_rate": "0.001",
                "minimum_commission": "5",
                "slippage_rate": "0.001",
                "sell_tax_rate": "0.001",
            },
        }
        if args.write_artifact:
            write_artifact(args.artifact, payload)
        else:
            _print_json(payload)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as error:
        print(f"validation error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
